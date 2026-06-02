#!/usr/bin/env python3
"""Visible train-slice scorer for precomputed hippocampal morphometry outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


SPLIT_SEED = 25121914
OUTPUT_SUFFIX = "_outputs.npz"


def _surface_metrics(pred: np.ndarray, gt: np.ndarray) -> tuple[float, float, float, float]:
    fwd = cKDTree(gt).query(pred)[0]
    rev = cKDTree(pred).query(gt)[0]
    both = np.concatenate([fwd, rev])
    q_mean = float(np.sqrt(np.mean(both**2)))
    q_max = float(np.max(both))
    hd = float(max(np.max(fwd), np.max(rev)))
    p95 = float(np.quantile(both, 0.95))
    return q_mean, q_max, hd, p95


def _train_mask(subjects: np.ndarray) -> np.ndarray:
    subject_ids = np.array(sorted(np.unique(subjects[:, 0])))
    shuffled = np.random.default_rng(SPLIT_SEED).permutation(subject_ids)
    train_subjects = set(shuffled[: len(shuffled) // 2].tolist())
    return np.array([row[0] in train_subjects for row in subjects], dtype=bool)


def _rows(value: np.ndarray, mask: np.ndarray, name: str) -> np.ndarray:
    arr = np.asarray(value)
    if arr.ndim == 0:
        return arr
    if arr.shape[0] == mask.shape[0]:
        return arr[mask]
    if arr.shape[0] == int(mask.sum()):
        return arr
    raise ValueError(
        f"{name} has {arr.shape[0]} rows, expected full dataset length "
        f"{mask.shape[0]} or train-slice length {int(mask.sum())}."
    )


def _valid_spoke_fraction(out: dict[str, np.ndarray], mask: np.ndarray) -> float:
    value = np.asarray(out["valid_spoke_fraction"])
    if value.ndim == 0:
        return float(value)
    return float(np.mean(_rows(value, mask, "valid_spoke_fraction")))


def _metric_block(dataset: dict, labels: dict, output_file: Path, mask: np.ndarray) -> dict[str, float]:
    out = dict(np.load(output_file, allow_pickle=True))
    pred_t = _rows(out["pred_thickness"], mask, "pred_thickness")
    gt_t = labels["gt_thickness"][mask]
    pred_lm = _rows(out["pred_landmarks"], mask, "pred_landmarks")
    gt_lm = labels["gt_landmarks"][mask]
    subjects = dataset["subjects"][mask]
    gt_surface = dataset["surface_vertices"][mask]
    recon = _rows(out["recon_vertices"], mask, "recon_vertices")
    cross = subjects[:, 1] == 0
    longitudinal = subjects[:, 1] > 0
    if not np.any(cross) or not np.any(longitudinal):
        raise ValueError("Train slice must contain both cross-sectional and longitudinal rows.")

    thickness_abs = np.abs(pred_t - gt_t)
    cross_errors = np.linalg.norm(pred_lm[cross, :10] - gt_lm[cross, :10], axis=2)
    long_errors = np.linalg.norm(pred_lm[longitudinal, 10:] - gt_lm[longitudinal, 10:], axis=2)
    thickness_mae = float(np.mean(thickness_abs))
    thickness_p95 = float(np.quantile(thickness_abs, 0.95))
    cross_error = float(np.mean(cross_errors))
    long_error = float(np.mean(long_errors))
    surface = np.array([_surface_metrics(recon[i], gt_surface[i]) for i in range(len(recon))])
    return {
        "thickness_mae_mm": thickness_mae,
        "thickness_p95_abs_error_mm": thickness_p95,
        "cross_sectional_correspondence_error_mm": cross_error,
        "cross_sectional_p95_correspondence_error_mm": float(np.quantile(cross_errors, 0.95)),
        "longitudinal_correspondence_error_mm": long_error,
        "longitudinal_p95_correspondence_error_mm": float(np.quantile(long_errors, 0.95)),
        "surface_Q_mm": float(surface[:, 0].mean()),
        "surface_q_mm": float(surface[:, 1].mean()),
        "surface_HD_mm": float(surface[:, 2].mean()),
        "surface_p95_mm": float(surface[:, 3].mean()),
        "valid_spoke_fraction": _valid_spoke_fraction(out, mask),
    }


def _discover_methods(outputs_dir: Path) -> dict[str, Path]:
    outputs = {}
    for path in sorted(outputs_dir.glob(f"*{OUTPUT_SUFFIX}.npz")):
        method_name = path.name[: -len(f"{OUTPUT_SUFFIX}.npz")]
        outputs[method_name] = path
    if not outputs:
        raise FileNotFoundError(f"No method output files matching *{OUTPUT_SUFFIX}.npz in {outputs_dir}.")
    return outputs


def _keep(block: dict[str, float], names: tuple[str, ...]) -> dict[str, float]:
    return {name: block[name] for name in names}


def _score_methods(dataset: dict, labels: dict, outputs: dict[str, Path], mask: np.ndarray) -> dict[str, dict[str, float]]:
    return {name: _metric_block(dataset, labels, path, mask) for name, path in sorted(outputs.items())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/synthetic_hippocampus.npz")
    parser.add_argument("--labels", default="data/synthetic_hippocampus_labels.npz")
    parser.add_argument("--outputs-dir", default="checkpoints")
    parser.add_argument("--scores", default="scoring/scores_train.json")
    args = parser.parse_args()

    dataset = dict(np.load(args.dataset, allow_pickle=True))
    labels = dict(np.load(args.labels, allow_pickle=True))
    if not np.array_equal(dataset["subjects"], labels["subjects"]):
        raise ValueError("Dataset and label files describe different subject/timepoint rows.")

    mask = _train_mask(dataset["subjects"])
    outputs = _discover_methods(Path(args.outputs_dir))
    blocks = _score_methods(dataset, labels, outputs, mask)
    scores = {
        "_slice": "train",
        "experiments": {
            "subfield_thickness_accuracy": {
                "results": {
                    method: _keep(
                        block,
                        ("thickness_mae_mm", "thickness_p95_abs_error_mm", "valid_spoke_fraction"),
                    )
                    for method, block in blocks.items()
                }
            },
            "correspondence_stability": {
                "results": {
                    method: _keep(
                        block,
                        (
                            "cross_sectional_correspondence_error_mm",
                            "cross_sectional_p95_correspondence_error_mm",
                            "longitudinal_correspondence_error_mm",
                            "longitudinal_p95_correspondence_error_mm",
                            "valid_spoke_fraction",
                        ),
                    )
                    for method, block in blocks.items()
                }
            },
            "surface_robustness": {
                "results": {
                    method: _keep(
                        block,
                        ("surface_Q_mm", "surface_q_mm", "surface_HD_mm", "surface_p95_mm", "valid_spoke_fraction"),
                    )
                    for method, block in blocks.items()
                }
            },
        }
    }
    output_path = Path(args.scores)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(scores, indent=2) + "\n")
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
