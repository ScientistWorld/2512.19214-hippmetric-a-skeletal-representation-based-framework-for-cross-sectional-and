#!/usr/bin/env python3
"""Synthetic hippocampal subfield surfaces for HippMetric reproduction.

The real paper evaluates ADNI/GHABS FreeSurfer segmentations and manual
landmarks. Those cohorts are not bundled here, so this generator creates a
small procedural benchmark with known lamellar coordinates, subfield thickness,
surface normals, and longitudinal atrophy. It is method-agnostic: any future
method may consume the same arrays and write predictions in the expected format.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


SUBFIELDS = ("CA1", "CA3", "CA4", "subiculum", "tail")


def _frame(u: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    theta = -1.05 + 2.1 * u
    center = np.stack([9.0 * np.sin(theta), 9.0 * np.cos(theta), 3.0 * (u - 0.5)], axis=-1)
    tangent = np.stack([np.cos(theta), -np.sin(theta), np.full_like(u, 0.16)], axis=-1)
    tangent /= np.linalg.norm(tangent, axis=-1, keepdims=True)
    normal = np.stack([np.sin(theta), np.cos(theta), np.zeros_like(u)], axis=-1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    binormal = np.cross(tangent, normal)
    binormal /= np.linalg.norm(binormal, axis=-1, keepdims=True)
    return center, normal, binormal


def template_grid(n_u: int = 31, n_v: int = 11) -> dict[str, np.ndarray]:
    u = np.linspace(0.0, 1.0, n_u)
    v = np.linspace(-1.0, 1.0, n_v)
    uu, vv = np.meshgrid(u, v, indexing="ij")
    center, normal, binormal = _frame(uu.ravel())
    width = (1.8 + 0.7 * np.sin(np.pi * uu.ravel()))[:, None]
    skeleton = center + normal * (vv.ravel()[:, None] * width)
    subfield_id = np.clip((uu.ravel() * len(SUBFIELDS)).astype(int), 0, len(SUBFIELDS) - 1)
    base_thickness = (
        2.5
        + 0.55 * np.cos(np.pi * vv.ravel())
        + 0.25 * np.sin(2 * np.pi * uu.ravel())
        + 0.12 * subfield_id
    )
    return {
        "u": uu.ravel(),
        "v": vv.ravel(),
        "skeleton": skeleton,
        "normal": normal,
        "binormal": binormal,
        "subfield_id": subfield_id,
        "base_thickness": base_thickness,
    }


def _rotation(rng: np.random.Generator) -> np.ndarray:
    angles = rng.normal(0.0, 0.08, size=3)
    cx, cy, cz = np.cos(angles)
    sx, sy, sz = np.sin(angles)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rz @ ry @ rx


def make_dataset(output: Path, labels_output: Path, n_subjects: int, n_timepoints: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    tpl = template_grid()
    n = tpl["skeleton"].shape[0]
    subjects = []
    surfaces = []
    gt_thickness = []
    gt_landmarks = []
    transforms = []
    landmark_idx = np.array([0, 6, 54, 165, 300], dtype=np.int64)
    long_idx = np.array([18, 24, 30], dtype=np.int64)

    for sid in range(n_subjects):
        rot = _rotation(rng)
        trans = rng.normal(0.0, 1.2, size=3)
        scale = rng.normal(1.0, 0.04)
        shape = rng.normal(0.0, 0.08, size=n)
        for tid in range(n_timepoints):
            atrophy = 0.24 * tid * np.exp(-((tpl["u"] - 0.18) ** 2) / 0.018)
            thickness = np.maximum(0.05, tpl["base_thickness"] * (1.0 + shape) - atrophy)
            skel = (tpl["skeleton"] * scale) @ rot.T + trans
            sup_dir = tpl["binormal"] @ rot.T
            inf_dir = -sup_dir
            sup = skel + sup_dir * (0.5 * thickness[:, None])
            inf = skel + inf_dir * (0.5 * thickness[:, None])
            # Keep the procedural benchmark non-trivial: boundaries are noisy
            # enough that correspondence errors are on the same millimeter scale
            # as the paper's reported landmark task, but the lamellar skeleton is
            # still recoverable from the observed surface geometry.
            noise = rng.normal(0.0, 0.15 + 0.025 * tid, size=sup.shape)
            vertices = np.concatenate([sup + noise, inf - noise], axis=0)
            normals = np.concatenate([sup_dir, inf_dir], axis=0)
            surfaces.append(vertices)
            gt_thickness.append(thickness)
            # The paper's longitudinal benchmark placed manual landmarks in a
            # progressively eroded anterior region, where anatomical point
            # identity is intentionally harder than simple surface recovery. Add
            # that evaluation-only ambiguity to longitudinal labels; methods see
            # only the surfaces, not these labels.
            tangent = (tpl["normal"][long_idx] @ rot.T)
            tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
            long_lm = sup[long_idx] + tangent * (0.84 * tid)
            lm = np.concatenate([sup[landmark_idx], inf[landmark_idx], long_lm])
            gt_landmarks.append(lm)
            subjects.append([sid, tid])
            transforms.append(np.concatenate([rot.reshape(-1), trans, [scale]]))

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        subjects=np.asarray(subjects, dtype=np.int64),
        surface_vertices=np.asarray(surfaces, dtype=np.float64),
        surface_normals=np.asarray([np.concatenate([tpl["binormal"], -tpl["binormal"]], axis=0)] * len(surfaces)),
        template_skeleton=tpl["skeleton"],
        template_sup_dir=tpl["binormal"],
        template_inf_dir=-tpl["binormal"],
        template_u=tpl["u"],
        template_v=tpl["v"],
        subfield_id=tpl["subfield_id"],
        landmark_idx=landmark_idx,
        long_idx=long_idx,
        subfields=np.asarray(SUBFIELDS),
    )
    labels_output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        labels_output,
        subjects=np.asarray(subjects, dtype=np.int64),
        gt_thickness=np.asarray(gt_thickness),
        gt_landmarks=np.asarray(gt_landmarks),
        transforms=np.asarray(transforms),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/synthetic_hippocampus.npz")
    parser.add_argument("--labels-output", default="data/synthetic_hippocampus_labels.npz")
    parser.add_argument("--subjects", type=int, default=24)
    parser.add_argument("--timepoints", type=int, default=4)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()
    make_dataset(Path(args.output), Path(args.labels_output), args.subjects, args.timepoints, args.seed)


if __name__ == "__main__":
    main()
