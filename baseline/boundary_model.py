#!/usr/bin/env python3
"""Boundary-driven baseline for the synthetic hippocampal morphometry task."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


def run(dataset: Path, output: Path) -> None:
    data = np.load(dataset, allow_pickle=True)
    vertices = data["surface_vertices"]
    subjects = data["subjects"]
    template = data["template_skeleton"]
    landmark_idx = data["landmark_idx"]
    long_idx = data["long_idx"]

    pred_thickness = []
    pred_landmarks = []
    recon_vertices = []
    valid = []
    for surf in vertices:
        # This baseline anchors correspondence to the observed boundary via a
        # global PCA frame. It intentionally lacks an internal lamellar skeleton.
        centered = surf - surf.mean(axis=0, keepdims=True)
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
        coords = centered @ vh.T
        order = np.lexsort((coords[:, 2], coords[:, 1], coords[:, 0]))
        sorted_surf = surf[order]
        tree = cKDTree(sorted_surf)
        _, nn = tree.query(template)
        near = sorted_surf[nn]
        half = len(surf) // 2
        top = sorted_surf[:half]
        bottom = sorted_surf[half:]
        pair_count = min(len(top), len(bottom), len(template))
        thickness = np.full(len(template), np.nan)
        thickness[:pair_count] = np.linalg.norm(top[:pair_count] - bottom[:pair_count], axis=1)
        thickness = np.nan_to_num(thickness, nan=np.nanmedian(thickness[:pair_count]))
        pred_thickness.append(thickness)
        lm_idx = np.concatenate([landmark_idx, landmark_idx, long_idx])
        pred_landmarks.append(near[lm_idx])
        recon = np.concatenate([near, near], axis=0)
        recon_vertices.append(recon)
        valid.append(1.0)

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        method="boundary_baseline",
        subjects=subjects,
        pred_thickness=np.asarray(pred_thickness),
        pred_landmarks=np.asarray(pred_landmarks),
        recon_vertices=np.asarray(recon_vertices),
        valid_spoke_fraction=np.asarray(valid),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/synthetic_hippocampus.npz")
    parser.add_argument("--output", default="checkpoints/boundary_baseline_outputs.npz")
    args = parser.parse_args()
    run(Path(args.dataset), Path(args.output))


if __name__ == "__main__":
    main()
