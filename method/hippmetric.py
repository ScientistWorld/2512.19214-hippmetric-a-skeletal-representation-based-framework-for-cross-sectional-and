#!/usr/bin/env python3
"""Scaled HippMetric implementation: skeletal coordinates and spoke refinement."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree


def _similarity_from_pairs(source: np.ndarray, target: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    src_mean = source.mean(axis=0)
    tgt_mean = target.mean(axis=0)
    src0 = source - src_mean
    tgt0 = target - tgt_mean
    cov = src0.T @ tgt0 / len(source)
    u, _, vt = np.linalg.svd(cov)
    rot = u @ vt
    if np.linalg.det(rot) < 0:
        u[:, -1] *= -1
        rot = u @ vt
    scale = float(np.sum((src0 @ rot) * tgt0) / np.sum(src0**2))
    trans = tgt_mean - scale * (src_mean @ rot)
    return scale, rot, trans


def _pca_initial_alignment(source: np.ndarray, target: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    src_center = source.mean(axis=0)
    tgt_center = target.mean(axis=0)
    src0 = source - src_center
    tgt0 = target - tgt_center
    _, src_s, src_vt = np.linalg.svd(src0, full_matrices=False)
    _, tgt_s, tgt_vt = np.linalg.svd(tgt0, full_matrices=False)
    best_rot = np.eye(3)
    best_score = np.inf
    signs = np.array(
        [
            [1, 1, 1],
            [1, -1, -1],
            [-1, 1, -1],
            [-1, -1, 1],
        ],
        dtype=float,
    )
    for sign in signs:
        rot = src_vt.T @ np.diag(sign) @ tgt_vt
        aligned = src0 @ rot
        score = cKDTree(tgt0).query(aligned)[0].mean()
        if score < best_score:
            best_score = score
            best_rot = rot
    scale = float(np.mean(tgt_s[:2]) / np.mean(src_s[:2]))
    trans = tgt_center - scale * (src_center @ best_rot)
    return scale, best_rot, trans


def _assignment_surface_match(source_points: np.ndarray, target_vertices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Bijectively match a deformed template surface to an unordered target surface.

    Nearest-neighbor matching is many-to-one and can collapse nearby anatomical
    locations onto the same observed vertex. The benchmark deliberately shuffles
    mesh rows, so the reduced LDDMM stage needs an order-free but one-to-one
    correspondence estimate.
    """
    diff = source_points[:, None, :] - target_vertices[None, :, :]
    cost = np.sum(diff * diff, axis=2)
    rows, cols = linear_sum_assignment(cost)
    matched = np.empty_like(source_points)
    distances = np.empty(source_points.shape[0], dtype=float)
    matched[rows] = target_vertices[cols]
    distances[rows] = np.sqrt(cost[rows, cols])
    return matched, distances


def estimate_subject_alignment(
    template_boundary: np.ndarray,
    vertices: np.ndarray,
    iterations: int = 4,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Estimate the initial rigid template-to-subject alignment."""
    scale, rot, trans = _pca_initial_alignment(template_boundary, vertices)
    for _ in range(iterations):
        moved = scale * (template_boundary @ rot) + trans
        matched_vertices, _ = _assignment_surface_match(moved, vertices)
        next_scale, next_rot, next_trans = _similarity_from_pairs(template_boundary, matched_vertices)
        if np.linalg.norm(next_trans - trans) < 1e-5 and abs(next_scale - scale) < 1e-5:
            scale, rot, trans = next_scale, next_rot, next_trans
            break
        scale, rot, trans = next_scale, next_rot, next_trans
    return scale, rot, trans


def _kernel_displacement(
    control_points: np.ndarray,
    control_displacements: np.ndarray,
    query_points: np.ndarray,
    width: float,
    ridge: float = 2e-2,
) -> np.ndarray:
    """Smooth dense deformation with the Gaussian kernel used in LDDMM-style matching."""
    diff = control_points[:, None, :] - control_points[None, :, :]
    k_cc = np.exp(-np.sum(diff * diff, axis=2) / (2.0 * width * width))
    k_cc.flat[:: k_cc.shape[0] + 1] += ridge
    weights = np.linalg.solve(k_cc, control_displacements)
    qdiff = query_points[:, None, :] - control_points[None, :, :]
    k_qc = np.exp(-np.sum(qdiff * qdiff, axis=2) / (2.0 * width * width))
    return k_qc @ weights


def dense_surface_deformation(
    template_boundary: np.ndarray,
    vertices: np.ndarray,
    query_points: np.ndarray,
    iterations_per_width: int = 2,
    max_control_points: int = 180,
) -> np.ndarray:
    """Warp template landmarks with a small dense Gaussian-kernel deformation.

    The paper uses Deformetrica dense-mode LDDMM and refines Gaussian kernel
    width from 7 mm to 3 mm. This scaled implementation keeps that computation
    pattern: after rigid alignment it repeatedly matches the deformed template
    boundary to the observed surface and transports the same smoothed
    displacement field to internal skeletal points.
    """
    scale, rot, trans = estimate_subject_alignment(template_boundary, vertices)
    deformed_boundary = scale * (template_boundary @ rot) + trans
    deformed_query = scale * (query_points @ rot) + trans
    if template_boundary.shape[0] > max_control_points:
        control_idx = np.linspace(0, template_boundary.shape[0] - 1, max_control_points, dtype=int)
    else:
        control_idx = np.arange(template_boundary.shape[0])
    for width in np.arange(7.0, 2.99, -0.5):
        for _ in range(iterations_per_width):
            matched_vertices, distances = _assignment_surface_match(deformed_boundary, vertices)
            control_points = deformed_boundary[control_idx]
            displacements = matched_vertices[control_idx] - control_points
            if float(np.mean(distances)) < 0.05:
                return deformed_query
            step_boundary = _kernel_displacement(control_points, displacements, deformed_boundary, width)
            step_query = _kernel_displacement(control_points, displacements, deformed_query, width)
            deformed_boundary = deformed_boundary + 0.7 * step_boundary
            deformed_query = deformed_query + 0.7 * step_query
    return deformed_query


def _project_to_boundary(
    skeleton: np.ndarray,
    directions: np.ndarray,
    vertices: np.ndarray,
    normals: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    endpoints = np.empty_like(skeleton)
    lengths = np.zeros(skeleton.shape[0], dtype=float)
    normal_at_endpoint = np.empty_like(skeleton)
    valid = np.zeros(skeleton.shape[0], dtype=bool)
    for i, (origin, direction) in enumerate(zip(skeleton, directions)):
        offsets = vertices - origin
        axial = offsets @ direction
        side = axial > 0.0
        if not np.any(side):
            endpoints[i] = origin
            normal_at_endpoint[i] = direction
            continue
        perpendicular = offsets - axial[:, None] * direction
        score = np.linalg.norm(perpendicular, axis=1) + 0.04 * np.abs(axial)
        score[~side] = np.inf
        idx = int(np.argmin(score))
        endpoints[i] = vertices[idx]
        lengths[i] = max(float(np.dot(endpoints[i] - origin, direction)), 0.0)
        normal = normals[idx]
        if float(np.dot(normal, direction)) < 0.0:
            normal = -normal
        normal_at_endpoint[i] = normal
        valid[i] = lengths[i] > 0.02
    return endpoints, lengths, normal_at_endpoint, valid


def refine_paired_spokes(
    skeleton: np.ndarray,
    sup_directions: np.ndarray,
    inf_directions: np.ndarray,
    vertices: np.ndarray,
    boundary_normals: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    sup = sup_directions.copy()
    inf = inf_directions.copy()
    sup_end = skeleton + 1.4 * sup
    inf_end = skeleton + 1.4 * inf
    sup_len = np.full(skeleton.shape[0], 1.4)
    inf_len = np.full(skeleton.shape[0], 1.4)
    sup_valid = np.ones(skeleton.shape[0], dtype=bool)
    inf_valid = np.ones(skeleton.shape[0], dtype=bool)

    for _ in range(3):
        # E0: project spoke endpoints to the observed boundary along each side.
        sup_end, sup_len, sup_norm, sup_valid = _project_to_boundary(skeleton, sup, vertices, boundary_normals)
        inf_end, inf_len, inf_norm, inf_valid = _project_to_boundary(skeleton, inf, vertices, boundary_normals)

        # E1: reduce angular deviation between spoke direction and boundary normal.
        sup = sup + 0.35 * sup_norm
        inf = inf + 0.35 * inf_norm
        sup /= np.linalg.norm(sup, axis=1, keepdims=True)
        inf /= np.linalg.norm(inf, axis=1, keepdims=True)

    # E2: enforce paired superior/inferior length symmetry where both spokes
    # are valid, followed by a final E0 projection as in the paper.
    paired_valid = sup_valid & inf_valid
    paired_length = 0.5 * (sup_len + inf_len)
    sup_len[paired_valid] = paired_length[paired_valid]
    inf_len[paired_valid] = paired_length[paired_valid]
    sup_end = skeleton + sup * sup_len[:, None]
    inf_end = skeleton + inf * inf_len[:, None]
    sup_end, sup_len, _, sup_valid = _project_to_boundary(skeleton, sup, vertices, boundary_normals)
    inf_end, inf_len, _, inf_valid = _project_to_boundary(skeleton, inf, vertices, boundary_normals)
    valid = sup_valid & inf_valid
    return sup_end, sup_len, inf_end, inf_len, valid


def _surface_normals_from_skeleton(vertices: np.ndarray, skeleton: np.ndarray) -> np.ndarray:
    _, idx = cKDTree(skeleton).query(vertices)
    normals = vertices - skeleton[idx]
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    fallback = np.tile(np.array([[0.0, 0.0, 1.0]]), (vertices.shape[0], 1))
    return np.where(norms > 1e-8, normals / np.maximum(norms, 1e-8), fallback)


def run(dataset: Path, output: Path) -> None:
    data = np.load(dataset, allow_pickle=True)
    template_skeleton = data["template_skeleton"]
    sup_dir = data["template_sup_dir"]
    inf_dir = data["template_inf_dir"]
    surface_vertices = data["surface_vertices"]
    subjects = data["subjects"]
    landmark_idx = data["landmark_idx"]
    long_idx = data["long_idx"]
    template_boundary = np.concatenate(
        [
            template_skeleton + 1.45 * sup_dir,
            template_skeleton + 1.45 * inf_dir,
        ],
        axis=0,
    )
    template_query = np.concatenate(
        [
            template_skeleton,
            template_skeleton + 1.45 * sup_dir,
            template_skeleton + 1.45 * inf_dir,
        ],
        axis=0,
    )

    pred_thickness: list[np.ndarray | None] = [None] * len(subjects)
    pred_landmarks: list[np.ndarray | None] = [None] * len(subjects)
    recon_vertices: list[np.ndarray | None] = [None] * len(subjects)
    validity: list[float | None] = [None] * len(subjects)
    baseline_skeleton_by_subject: dict[int, np.ndarray] = {}
    baseline_dirs_by_subject: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for row in np.lexsort((subjects[:, 1], subjects[:, 0])):
        sid, tid = subjects[row]
        vertices = surface_vertices[row]
        if tid == 0:
            deformed = dense_surface_deformation(template_boundary, vertices, template_query)
            n = template_skeleton.shape[0]
            skeleton = deformed[:n]
            sup_seed = deformed[n : 2 * n] - skeleton
            inf_seed = deformed[2 * n :] - skeleton
            sup = sup_seed / np.maximum(np.linalg.norm(sup_seed, axis=1, keepdims=True), 1e-8)
            inf = inf_seed / np.maximum(np.linalg.norm(inf_seed, axis=1, keepdims=True), 1e-8)
            baseline_skeleton_by_subject[int(sid)] = skeleton
            baseline_dirs_by_subject[int(sid)] = (sup, inf)
        else:
            # Longitudinal processing keeps the baseline skeleton coordinate
            # system and re-optimizes only spoke lengths against follow-up boundaries.
            skeleton = baseline_skeleton_by_subject[int(sid)]
            sup, inf = baseline_dirs_by_subject[int(sid)]
        normals = _surface_normals_from_skeleton(vertices, skeleton)
        sup_end, sup_len, inf_end, inf_len, valid = refine_paired_spokes(skeleton, sup, inf, vertices, normals)
        thickness = sup_len + inf_len
        pred_thickness[row] = thickness
        pred_landmarks[row] = np.concatenate([sup_end[landmark_idx], inf_end[landmark_idx], sup_end[long_idx]])
        recon_vertices[row] = np.concatenate([sup_end, inf_end], axis=0)
        validity[row] = float(np.mean(valid))

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        method="hippmetric",
        subjects=subjects,
        pred_thickness=np.asarray(pred_thickness),
        pred_landmarks=np.asarray(pred_landmarks),
        recon_vertices=np.asarray(recon_vertices),
        valid_spoke_fraction=np.asarray(validity, dtype=float),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/synthetic_hippocampus.npz")
    parser.add_argument("--output", default="checkpoints/hippmetric_outputs.npz")
    args = parser.parse_args()
    run(Path(args.dataset), Path(args.output))


if __name__ == "__main__":
    main()
