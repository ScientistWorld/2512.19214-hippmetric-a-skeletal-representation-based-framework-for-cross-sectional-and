#!/usr/bin/env python3
"""Scaled HippMetric implementation: skeletal coordinates and spoke refinement."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


def refine_spokes(skeleton: np.ndarray, directions: np.ndarray, vertices: np.ndarray, normals: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    tree = cKDTree(vertices)
    lengths = np.full(skeleton.shape[0], 1.4)
    dirs = directions.copy()
    endpoints = skeleton + dirs * lengths[:, None]
    for _ in range(3):
        _, idx = tree.query(endpoints)
        endpoints = vertices[idx]
        nearest_normals = normals[idx]
        signs = np.sign(np.sum(dirs * nearest_normals, axis=1, keepdims=True))
        target = nearest_normals * np.where(signs == 0, 1.0, signs)
        dirs = dirs + 0.35 * target
        dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
        lengths = np.sum((endpoints - skeleton) * dirs, axis=1)
        lengths = np.maximum(lengths, 0.0)
        endpoints = skeleton + dirs * lengths[:, None]
    _, idx = tree.query(endpoints)
    endpoints = vertices[idx]
    lengths = np.linalg.norm(endpoints - skeleton, axis=1)
    return endpoints, lengths


def run(dataset: Path, output: Path) -> None:
    data = np.load(dataset, allow_pickle=True)
    template_skeleton = data["template_skeleton"]
    sup_dir = data["template_sup_dir"]
    inf_dir = data["template_inf_dir"]
    transforms = data["transforms"]
    surface_vertices = data["surface_vertices"]
    subjects = data["subjects"]
    landmark_idx = data["landmark_idx"]
    long_idx = data["long_idx"]

    pred_thickness = []
    pred_landmarks = []
    recon_vertices = []
    validity = []
    baseline_skeleton_by_subject: dict[int, np.ndarray] = {}

    for row, (sid, tid) in enumerate(subjects):
        packed = transforms[row]
        rot = packed[:9].reshape(3, 3)
        trans = packed[9:12]
        scale = packed[12]
        skeleton = (template_skeleton * scale) @ rot.T + trans
        if tid == 0:
            baseline_skeleton_by_subject[int(sid)] = skeleton
        else:
            # Longitudinal processing keeps the baseline skeleton coordinate
            # system and re-optimizes only spoke lengths against follow-up boundaries.
            skeleton = baseline_skeleton_by_subject[int(sid)]
        sup = sup_dir @ rot.T
        inf = inf_dir @ rot.T
        vertices = surface_vertices[row]
        normals = np.concatenate([sup, inf], axis=0)
        sup_end, sup_len = refine_spokes(skeleton, sup, vertices, normals)
        inf_end, inf_len = refine_spokes(skeleton, inf, vertices, normals)
        thickness = sup_len + inf_len
        pred_thickness.append(thickness)
        pred_landmarks.append(np.concatenate([sup_end[landmark_idx], inf_end[landmark_idx], sup_end[long_idx]]))
        recon_vertices.append(np.concatenate([sup_end, inf_end], axis=0))
        validity.append(np.mean(thickness > 0.02))

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        method="hippmetric",
        subjects=subjects,
        pred_thickness=np.asarray(pred_thickness),
        pred_landmarks=np.asarray(pred_landmarks),
        recon_vertices=np.asarray(recon_vertices),
        valid_spoke_fraction=np.asarray(validity),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/synthetic_hippocampus.npz")
    parser.add_argument("--output", default="checkpoints/hippmetric_outputs.npz")
    args = parser.parse_args()
    run(Path(args.dataset), Path(args.output))


if __name__ == "__main__":
    main()
