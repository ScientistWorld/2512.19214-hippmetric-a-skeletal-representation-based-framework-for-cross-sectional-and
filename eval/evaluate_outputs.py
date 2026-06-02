#!/usr/bin/env python3
"""Evaluate morphometry outputs without importing method code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


def _surface_metrics(pred: np.ndarray, gt: np.ndarray) -> tuple[float, float, float, float]:
    fwd = cKDTree(gt).query(pred)[0]
    rev = cKDTree(pred).query(gt)[0]
    both = np.concatenate([fwd, rev])
    q_mean = float(np.sqrt(np.mean(both**2)))
    q_max = float(np.max(both))
    hd = float(max(np.max(fwd), np.max(rev)))
    p95 = float(np.quantile(both, 0.95))
    return q_mean, q_max, hd, p95


def _metric_block(dataset: dict, labels: dict, output_file: Path) -> dict[str, float]:
    out = np.load(output_file, allow_pickle=True)
    pred_t = out["pred_thickness"]
    gt_t = labels["gt_thickness"]
    pred_lm = out["pred_landmarks"]
    gt_lm = labels["gt_landmarks"]
    subjects = dataset["subjects"]
    gt_surface = dataset["surface_vertices"]
    recon = out["recon_vertices"]
    cross = subjects[:, 1] == 0
    longitudinal = subjects[:, 1] > 0
    thickness_abs = np.abs(pred_t - gt_t)
    cross_errors = np.linalg.norm(pred_lm[cross, :10] - gt_lm[cross, :10], axis=2)
    long_errors = np.linalg.norm(pred_lm[longitudinal, 10:] - gt_lm[longitudinal, 10:], axis=2)
    thickness_mae = float(np.mean(thickness_abs))
    cross_error = float(np.mean(cross_errors))
    long_error = float(np.mean(long_errors))
    surface = np.array([_surface_metrics(recon[i], gt_surface[i]) for i in range(len(recon))])
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
        "valid_spoke_fraction": float(np.mean(out["valid_spoke_fraction"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/synthetic_hippocampus.npz")
    parser.add_argument("--labels", default="data/synthetic_hippocampus_labels.npz")
    parser.add_argument("--hippmetric", default="checkpoints/hippmetric_outputs.npz")
    parser.add_argument("--baseline", default="checkpoints/boundary_baseline_outputs.npz")
    parser.add_argument("--scores", default="scoring/scores.json")
    args = parser.parse_args()
    dataset = dict(np.load(args.dataset, allow_pickle=True))
    labels = dict(np.load(args.labels, allow_pickle=True))
    if not np.array_equal(dataset["subjects"], labels["subjects"]):
        raise ValueError("Dataset and label files describe different subject/timepoint rows.")
    baseline = _metric_block(dataset, labels, Path(args.baseline))
    hippmetric = _metric_block(dataset, labels, Path(args.hippmetric))

    def keep(block: dict[str, float], names: tuple[str, ...]) -> dict[str, float]:
        return {name: block[name] for name in names}

    scores = {
        "experiments": {
            "subfield_thickness_accuracy": {
                "results": {
                    "boundary_baseline": keep(
                        baseline,
                        ("thickness_mae_mm", "thickness_p95_abs_error_mm", "valid_spoke_fraction"),
                    ),
                    "hippmetric": keep(
                        hippmetric,
                        ("thickness_mae_mm", "thickness_p95_abs_error_mm", "valid_spoke_fraction"),
                    ),
                }
            },
            "correspondence_stability": {
                "results": {
                    "boundary_baseline": keep(
                        baseline,
                        (
                            "cross_sectional_correspondence_error_mm",
                            "cross_sectional_p95_correspondence_error_mm",
                            "longitudinal_correspondence_error_mm",
                            "longitudinal_p95_correspondence_error_mm",
                            "valid_spoke_fraction",
                        ),
                    ),
                    "hippmetric": keep(
                        hippmetric,
                        (
                            "cross_sectional_correspondence_error_mm",
                            "cross_sectional_p95_correspondence_error_mm",
                            "longitudinal_correspondence_error_mm",
                            "longitudinal_p95_correspondence_error_mm",
                            "valid_spoke_fraction",
                        ),
                    ),
                }
            },
            "surface_robustness": {
                "results": {
                    "boundary_baseline": keep(
                        baseline,
                        ("surface_Q_mm", "surface_q_mm", "surface_HD_mm", "surface_p95_mm", "valid_spoke_fraction"),
                    ),
                    "hippmetric": keep(
                        hippmetric,
                        ("surface_Q_mm", "surface_q_mm", "surface_HD_mm", "surface_p95_mm", "valid_spoke_fraction"),
                    ),
                }
            },
        }
    }
    Path(args.scores).parent.mkdir(parents=True, exist_ok=True)
    Path(args.scores).write_text(json.dumps(scores, indent=2) + "\n")
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
