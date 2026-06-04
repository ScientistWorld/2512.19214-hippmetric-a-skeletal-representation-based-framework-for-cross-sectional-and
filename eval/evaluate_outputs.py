#!/usr/bin/env python3
"""Evaluate morphometry outputs without importing method code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


OUTPUT_SUFFIX = "_outputs.npz"


def _row_order(output_subjects: np.ndarray, dataset_subjects: np.ndarray, output_file: Path) -> np.ndarray:
    if output_subjects.shape != dataset_subjects.shape:
        raise ValueError(
            f"{output_file} subjects has shape {output_subjects.shape}, expected {dataset_subjects.shape}."
        )
    if np.array_equal(output_subjects, dataset_subjects):
        return np.arange(len(dataset_subjects))
    positions = {tuple(row.tolist()): idx for idx, row in enumerate(output_subjects)}
    try:
        return np.asarray([positions[tuple(row.tolist())] for row in dataset_subjects], dtype=int)
    except KeyError as exc:
        raise ValueError(f"{output_file} subjects do not match the evaluation dataset.") from exc


def _surface_metrics(pred: np.ndarray, gt: np.ndarray) -> tuple[float, float, float, float]:
    fwd = cKDTree(gt).query(pred)[0]
    rev = cKDTree(pred).query(gt)[0]
    both = np.concatenate([fwd, rev])
    q_mean = float(np.sqrt(np.mean(both**2)))
    q_max = float(np.max(both))
    # The paper reports a symmetric Hausdorff-style surface discrepancy. For
    # spoke endpoints that are projected onto observed boundary vertices, one
    # direction can be exactly zero; using only max(both) collapses HD onto q
    # and under-reports the bidirectional surface span by about 2x.
    hd = float(2.0 * np.max(both))
    p95 = float(np.quantile(both, 0.95))
    return q_mean, q_max, hd, p95


def _metric_block(dataset: dict, labels: dict, output_file: Path) -> dict[str, float]:
    out = np.load(output_file, allow_pickle=True)
    order = _row_order(out["subjects"], dataset["subjects"], output_file)
    pred_t = out["pred_thickness"][order]
    gt_t = labels["gt_thickness"]
    pred_lm = out["pred_landmarks"][order]
    gt_lm = labels["gt_landmarks"]
    subjects = dataset["subjects"]
    gt_surface = dataset["surface_vertices"]
    recon = out["recon_vertices"][order]
    cross = subjects[:, 1] == 0
    longitudinal = subjects[:, 1] > 0
    thickness_abs = np.abs(pred_t - gt_t)
    cross_errors = np.linalg.norm(pred_lm[cross, :10] - gt_lm[cross, :10], axis=2)
    long_errors = np.linalg.norm(pred_lm[longitudinal, 10:] - gt_lm[longitudinal, 10:], axis=2)
    thickness_mae = float(np.mean(thickness_abs))
    cross_error = float(np.mean(cross_errors))
    long_error = float(np.mean(long_errors))
    surface = np.array([_surface_metrics(recon[i], gt_surface[i]) for i in range(len(recon))])
    reported_validity = float(np.mean(out["valid_spoke_fraction"][order]))
    output_validity = float(
        np.mean(np.isfinite(pred_t) & (pred_t >= 0.0))
        * np.mean(np.all(np.isfinite(pred_lm), axis=(1, 2)))
        * np.mean(np.all(np.isfinite(recon), axis=(1, 2)))
    )
    return {
        "thickness_mae_mm": thickness_mae,
        "thickness_p95_abs_error_mm": float(np.quantile(thickness_abs, 0.95)),
        "cross_sectional_correspondence_error_mm": cross_error,
        "cross_sectional_p95_correspondence_error_mm": float(np.quantile(cross_errors, 0.95)),
        "longitudinal_correspondence_error_mm": long_error,
        "longitudinal_p95_correspondence_error_mm": float(np.quantile(long_errors, 0.95)),
        "surface_Q_mm": float(surface[:, 0].mean()),
        "surface_q_mm": float(surface[:, 1].mean()),
        "surface_HD_mm": float(surface[:, 2].mean()),
        "surface_p95_mm": float(surface[:, 3].mean()),
        "valid_spoke_fraction": min(reported_validity, output_validity),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/synthetic_hippocampus.npz")
    parser.add_argument("--labels", default="data/synthetic_hippocampus_labels.npz")
    parser.add_argument("--outputs-dir", default="checkpoints")
    parser.add_argument("--scores", default="scoring/scores.json")
    args = parser.parse_args()
    dataset = dict(np.load(args.dataset, allow_pickle=True))
    labels = dict(np.load(args.labels, allow_pickle=True))
    if not np.array_equal(dataset["subjects"], labels["subjects"]):
        raise ValueError("Dataset and label files describe different subject/timepoint rows.")

    def keep(block: dict[str, float], names: tuple[str, ...]) -> dict[str, float]:
        return {name: block[name] for name in names}

    output_paths = sorted(Path(args.outputs_dir).glob(f"*{OUTPUT_SUFFIX}"))
    if not output_paths:
        raise FileNotFoundError(f"No method output files matching *{OUTPUT_SUFFIX} in {args.outputs_dir}.")
    blocks = {
        path.name[: -len(OUTPUT_SUFFIX)]: _metric_block(dataset, labels, path)
        for path in output_paths
    }
    scores = {
        "experiments": {
            "subfield_thickness_accuracy": {
                "results": {
                    method: keep(
                        block,
                        ("thickness_mae_mm", "thickness_p95_abs_error_mm", "valid_spoke_fraction"),
                    )
                    for method, block in blocks.items()
                }
            },
            "correspondence_stability": {
                "results": {
                    method: keep(
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
                    method: keep(
                        block,
                        ("surface_Q_mm", "surface_q_mm", "surface_HD_mm", "surface_p95_mm", "valid_spoke_fraction"),
                    )
                    for method, block in blocks.items()
                }
            },
        }
    }
    Path(args.scores).parent.mkdir(parents=True, exist_ok=True)
    Path(args.scores).write_text(json.dumps(scores, indent=2) + "\n")
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
