#!/usr/bin/env python3
"""Evaluate morphometry outputs without importing method code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


def _surface_metrics(pred: np.ndarray, gt: np.ndarray) -> tuple[float, float, float]:
    fwd = cKDTree(gt).query(pred)[0]
    rev = cKDTree(pred).query(gt)[0]
    both = np.concatenate([fwd, rev])
    q_mean = float(np.sqrt(np.mean(both**2)))
    q_max = float(np.max(both))
    hd = float(max(np.max(fwd), np.max(rev)))
    return q_mean, q_max, hd


def _metric_block(dataset: dict, output_file: Path) -> dict[str, float]:
    out = np.load(output_file, allow_pickle=True)
    pred_t = out["pred_thickness"]
    gt_t = dataset["gt_thickness"]
    pred_lm = out["pred_landmarks"]
    gt_lm = dataset["gt_landmarks"]
    subjects = dataset["subjects"]
    gt_surface = dataset["surface_vertices"]
    recon = out["recon_vertices"]
    cross = subjects[:, 1] == 0
    longitudinal = subjects[:, 1] > 0
    thickness_mae = float(np.mean(np.abs(pred_t - gt_t)))
    cross_error = float(np.mean(np.linalg.norm(pred_lm[cross, :10] - gt_lm[cross, :10], axis=2)))
    long_error = float(np.mean(np.linalg.norm(pred_lm[longitudinal, 10:] - gt_lm[longitudinal, 10:], axis=2)))
    surface = np.array([_surface_metrics(recon[i], gt_surface[i]) for i in range(len(recon))])
    return {
        "thickness_mae_mm": thickness_mae,
        "cross_sectional_correspondence_error_mm": cross_error,
        "longitudinal_correspondence_error_mm": long_error,
        "surface_Q_mm": float(surface[:, 0].mean()),
        "surface_q_mm": float(surface[:, 1].mean()),
        "surface_HD_mm": float(surface[:, 2].mean()),
        "valid_spoke_fraction": float(np.mean(out["valid_spoke_fraction"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/synthetic_hippocampus.npz")
    parser.add_argument("--hippmetric", default="checkpoints/hippmetric_outputs.npz")
    parser.add_argument("--baseline", default="checkpoints/boundary_baseline_outputs.npz")
    parser.add_argument("--scores", default="scoring/scores.json")
    args = parser.parse_args()
    dataset = dict(np.load(args.dataset, allow_pickle=True))
    baseline = _metric_block(dataset, Path(args.baseline))
    hippmetric = _metric_block(dataset, Path(args.hippmetric))

    def keep(block: dict[str, float], names: tuple[str, ...]) -> dict[str, float]:
        return {name: block[name] for name in names}

    scores = {
        "experiments": {
            "synthetic_subfield_thickness": {
                "results": {
                    "boundary_baseline": keep(baseline, ("thickness_mae_mm", "valid_spoke_fraction")),
                    "hippmetric": keep(hippmetric, ("thickness_mae_mm", "valid_spoke_fraction")),
                }
            },
            "synthetic_correspondence": {
                "results": {
                    "boundary_baseline": keep(
                        baseline,
                        (
                            "cross_sectional_correspondence_error_mm",
                            "longitudinal_correspondence_error_mm",
                            "valid_spoke_fraction",
                        ),
                    ),
                    "hippmetric": keep(
                        hippmetric,
                        (
                            "cross_sectional_correspondence_error_mm",
                            "longitudinal_correspondence_error_mm",
                            "valid_spoke_fraction",
                        ),
                    ),
                }
            },
            "synthetic_surface_robustness": {
                "results": {
                    "boundary_baseline": keep(
                        baseline,
                        ("surface_Q_mm", "surface_q_mm", "surface_HD_mm", "valid_spoke_fraction"),
                    ),
                    "hippmetric": keep(
                        hippmetric,
                        ("surface_Q_mm", "surface_q_mm", "surface_HD_mm", "valid_spoke_fraction"),
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
