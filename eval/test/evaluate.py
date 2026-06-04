#!/usr/bin/env python3
"""Held-out test-slice scorer for precomputed hippocampal morphometry outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


SPLIT_SALT = "25121914"
FEATURE_SALT = "visible-anatomy-25121914"
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
    # Keep the test-slice HD on the same symmetric bidirectional scale as the
    # full evaluator and paper-reported surface discrepancy.
    hd = float(2.0 * np.max(both))
    p95 = float(np.quantile(both, 0.95))
    return q_mean, q_max, hd, p95


def _test_mask(subjects: np.ndarray) -> np.ndarray:
    subject_ids = np.array(sorted(np.unique(subjects[:, 0])))
    ranked = sorted(
        subject_ids.tolist(),
        key=lambda sid: hashlib.blake2b(f"{SPLIT_SALT}:{int(sid)}".encode(), digest_size=8).digest(),
    )
    test_subjects = set(ranked[len(ranked) // 2 :])
    return np.array([row[0] in test_subjects for row in subjects], dtype=bool)


def _hashed_feature_indices(n_items: int, namespace: str, holdout: str) -> np.ndarray:
    if n_items <= 1:
        return np.arange(n_items, dtype=int)
    ranked = sorted(
        range(n_items),
        key=lambda idx: hashlib.blake2b(
            f"{FEATURE_SALT}:{namespace}:{idx}".encode(),
            digest_size=8,
        ).digest(),
    )
    split = max(1, min(n_items - 1, n_items // 2))
    selected = ranked[:split] if holdout == "train" else ranked[split:]
    return np.asarray(sorted(selected), dtype=int)


def _feature_slices(dataset: dict, labels: dict) -> dict[str, np.ndarray]:
    n_thickness = int(labels["gt_thickness"].shape[1])
    n_surface = int(dataset["surface_vertices"].shape[1])
    return {
        "thickness": _hashed_feature_indices(n_thickness, "thickness", "test"),
        "surface": _hashed_feature_indices(n_surface, "surface", "test"),
        "cross_landmarks": np.asarray([1, 3, 4, 6, 8], dtype=int),
        "longitudinal_landmarks": np.asarray([11], dtype=int),
    }


def _align_full_outputs(
    out: dict[str, np.ndarray],
    dataset_subjects: np.ndarray,
    output_file: Path,
) -> dict[str, np.ndarray]:
    if "subjects" not in out:
        raise ValueError(
            f"{output_file} must contain a subjects array for split-safe evaluation. "
            "Write full-dataset outputs using the same row contract as scripts/evaluate.sh."
        )
    output_subjects = np.asarray(out["subjects"])
    order = _row_order(output_subjects, dataset_subjects, output_file)
    n_rows = len(order)
    aligned: dict[str, np.ndarray] = {}
    for key, value in out.items():
        arr = np.asarray(value)
        if arr.ndim > 0 and arr.shape[0] == n_rows:
            aligned[key] = arr[order]
        else:
            aligned[key] = arr
    return aligned


def _slice_rows(value: np.ndarray, mask: np.ndarray, name: str) -> np.ndarray:
    arr = np.asarray(value)
    if arr.ndim == 0:
        return arr
    if arr.shape[0] == mask.shape[0]:
        return arr[mask]
    raise ValueError(
        f"{name} has {arr.shape[0]} rows, expected full dataset length {mask.shape[0]}. "
        "Test scoring must rescore the same full method outputs used by the train slice."
    )


def _valid_spoke_fraction(
    out: dict[str, np.ndarray],
    mask: np.ndarray,
    pred_t: np.ndarray,
    pred_lm: np.ndarray,
    recon: np.ndarray,
) -> float:
    value = np.asarray(out["valid_spoke_fraction"])
    if value.ndim == 0:
        reported_validity = float(value)
    else:
        reported_validity = float(np.mean(_slice_rows(value, mask, "valid_spoke_fraction")))
    output_validity = float(
        np.mean(np.isfinite(pred_t) & (pred_t >= 0.0))
        * np.mean(np.all(np.isfinite(pred_lm), axis=(1, 2)))
        * np.mean(np.all(np.isfinite(recon), axis=(1, 2)))
    )
    return min(reported_validity, output_validity)


def _metric_block(
    dataset: dict,
    labels: dict,
    output_file: Path,
    mask: np.ndarray,
    features: dict[str, np.ndarray],
) -> dict[str, float]:
    out = dict(np.load(output_file, allow_pickle=True))
    out = _align_full_outputs(out, dataset["subjects"], output_file)
    pred_t = _slice_rows(out["pred_thickness"], mask, "pred_thickness")
    gt_t = labels["gt_thickness"][mask]
    pred_lm = _slice_rows(out["pred_landmarks"], mask, "pred_landmarks")
    gt_lm = labels["gt_landmarks"][mask]
    subjects = dataset["subjects"][mask]
    gt_surface = dataset["surface_vertices"][mask]
    recon = _slice_rows(out["recon_vertices"], mask, "recon_vertices")
    cross = subjects[:, 1] == 0
    longitudinal = subjects[:, 1] > 0
    if not np.any(cross) or not np.any(longitudinal):
        raise ValueError("Test slice must contain both cross-sectional and longitudinal rows.")

    thickness_abs = np.abs(pred_t[:, features["thickness"]] - gt_t[:, features["thickness"]])
    cross_idx = features["cross_landmarks"]
    long_idx = features["longitudinal_landmarks"]
    cross_errors = np.linalg.norm(pred_lm[cross][:, cross_idx] - gt_lm[cross][:, cross_idx], axis=2)
    long_errors = np.linalg.norm(pred_lm[longitudinal][:, long_idx] - gt_lm[longitudinal][:, long_idx], axis=2)
    thickness_mae = float(np.mean(thickness_abs))
    thickness_p95 = float(np.quantile(thickness_abs, 0.95))
    cross_error = float(np.mean(cross_errors))
    long_error = float(np.mean(long_errors))
    surface_idx = features["surface"]
    surface = np.array(
        [_surface_metrics(recon[i, surface_idx], gt_surface[i, surface_idx]) for i in range(len(recon))]
    )
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
        "valid_spoke_fraction": _valid_spoke_fraction(out, mask, pred_t, pred_lm, recon),
    }


def _discover_methods(outputs_dir: Path) -> dict[str, Path]:
    outputs = {}
    for path in sorted(outputs_dir.glob(f"*{OUTPUT_SUFFIX}")):
        method_name = path.name[: -len(OUTPUT_SUFFIX)]
        outputs[method_name] = path
    if not outputs:
        raise FileNotFoundError(f"No method output files matching *{OUTPUT_SUFFIX} in {outputs_dir}.")
    return outputs


def _methods_from_train_scores(scores_path: Path) -> list[str]:
    if not scores_path.exists():
        return []
    scores = json.loads(scores_path.read_text())
    methods: set[str] = set()
    for experiment in scores.get("experiments", {}).values():
        methods.update(experiment.get("results", {}).keys())
    return sorted(methods)


def _select_outputs(outputs_dir: Path, methods_from_scores: Path) -> dict[str, Path]:
    discovered = _discover_methods(outputs_dir)
    requested_methods = _methods_from_train_scores(methods_from_scores)
    if not requested_methods:
        return discovered
    missing = [method for method in requested_methods if method not in discovered]
    if missing:
        raise FileNotFoundError(
            "Train scores contain methods with no matching test output file in "
            f"{outputs_dir}: {', '.join(missing)}"
        )
    return {method: discovered[method] for method in requested_methods}


def _keep(block: dict[str, float], names: tuple[str, ...]) -> dict[str, float]:
    return {name: block[name] for name in names}


def _score_methods(
    dataset: dict,
    labels: dict,
    outputs: dict[str, Path],
    mask: np.ndarray,
    features: dict[str, np.ndarray],
) -> dict[str, dict[str, float]]:
    return {name: _metric_block(dataset, labels, path, mask, features) for name, path in sorted(outputs.items())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/synthetic_hippocampus.npz")
    parser.add_argument("--labels", default="data/synthetic_hippocampus_labels.npz")
    parser.add_argument("--outputs-dir", default="checkpoints")
    parser.add_argument("--methods-from", default="scoring/scores_train.json")
    parser.add_argument("--scores", default="scoring/scores_test.json")
    args = parser.parse_args()

    dataset = dict(np.load(args.dataset, allow_pickle=True))
    labels = dict(np.load(args.labels, allow_pickle=True))
    if not np.array_equal(dataset["subjects"], labels["subjects"]):
        raise ValueError("Dataset and label files describe different subject/timepoint rows.")

    mask = _test_mask(dataset["subjects"])
    features = _feature_slices(dataset, labels)
    outputs = _select_outputs(Path(args.outputs_dir), Path(args.methods_from))
    blocks = _score_methods(dataset, labels, outputs, mask, features)
    scores = {
        "_slice": "test",
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
