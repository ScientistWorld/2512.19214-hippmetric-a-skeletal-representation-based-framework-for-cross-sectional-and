#!/usr/bin/env python3
"""Evaluation-side procedural hippocampal cohort (kept out of the scientist's view).

Each subject is a curved, cupped, twisted lamellar sheet (the skeletal surface)
with superior/inferior half-thickness fields. Subjects differ from the public
template by nonlinear shape changes (arc geometry, width profile, head position,
cupping, thickness modes, head digitations and a random smooth 3D warp), by
global scale and by scanner pose; about half carry regional disease-like thinning
at baseline. Follow-up scans erode a subject-specific
anterior region by shortening the superior/inferior extent along the true
skeletal normals; the skeletal sheet itself is unchanged, so anatomical point
identity across time is well defined.

What a method receives is only a binary segmentation on a 0.5 mm grid, produced
from the anatomy with smooth boundary perturbations and voxel-level label noise.
Ground truth (skeletal points, boundary points, thickness, the atrophic region
and a dense clean boundary sample) is returned separately and never written
next to the inputs given to a method.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

GRID_NU, GRID_NV = 61, 9  # 549 skeletal points, 1,098 spokes (paper template size)
SURF_NU, SURF_NV = 101, 25  # dense clean boundary sample per side for surface scoring
DENSE_NU, DENSE_NV = 260, 76  # dense sheet sampling used for voxelisation
U_EXT, V_EXT = 0.08, 0.45  # rounded caps beyond the skeletal grid
SPACING = 0.5  # mm, the paper's resampling resolution
H_MIN = 0.45  # mm, minimum half-thickness after atrophy
R0 = 0.3  # mm, tangential tolerance when voxelising the sheet
SUBFIELDS = ("head", "subiculum", "CA_DG", "CA1", "tail")


# ---------------------------------------------------------------------------
# Shape model
# ---------------------------------------------------------------------------


def _z(rng: np.random.Generator, size=None, lim: float = 2.5):
    return np.clip(rng.standard_normal(size), -lim, lim)


def mean_params() -> dict:
    return {
        "R": 18.0,
        "span": 0.9,
        "zrise": 4.0,
        "xbow": 0.6,
        "twist": 0.35,
        "ws": 1.0,
        "m1": 0.0,
        "m2": 0.0,
        "head_u": 0.12,
        "cs": 1.0,
        "ts": 1.0,
        "scale": 1.0,
        "modes": np.zeros((0, 4)),
        "digits": np.zeros((0, 3)),
        "rbf_c": np.zeros((0, 3)),
        "rbf_d": np.zeros((0, 3)),
        "rbf_w": 6.0,
        "disease": np.zeros((0, 5)),
    }


def center_curve(u: np.ndarray, p: dict) -> np.ndarray:
    th = p["span"] * (2.0 * u - 1.0)
    x = p["xbow"] * p["R"] * (1.0 - np.cos(th))
    y = -p["R"] * np.sin(th)
    z = p["zrise"] * u**2
    return np.stack([x, y, z], axis=-1)


def _frame(u: np.ndarray, p: dict) -> tuple[np.ndarray, np.ndarray]:
    eps = 1e-4
    t = center_curve(u + eps, p) - center_curve(u - eps, p)
    t /= np.linalg.norm(t, axis=-1, keepdims=True)
    ew0 = np.cross(t, np.array([0.0, 0.0, 1.0]))
    ew0 /= np.linalg.norm(ew0, axis=-1, keepdims=True)
    en0 = np.cross(ew0, t)
    en0 /= np.linalg.norm(en0, axis=-1, keepdims=True)
    tau = p["twist"] * (u - 0.5)
    c, s = np.cos(tau)[:, None], np.sin(tau)[:, None]
    return c * ew0 + s * en0, -s * ew0 + c * en0


def _width(u: np.ndarray, p: dict) -> np.ndarray:
    base = 2.6 + 3.4 * np.exp(-(((u - p["head_u"]) / 0.16) ** 2)) + 0.6 * (1.0 - u)
    return p["ws"] * base * (1.0 + p["m1"] * np.sin(np.pi * u) + p["m2"] * np.cos(2.0 * np.pi * u))


def _cup(u: np.ndarray, p: dict) -> np.ndarray:
    return p["cs"] * (1.2 + 0.8 * np.exp(-(((u - 0.15) / 0.15) ** 2)))


def _skeleton_raw(u: np.ndarray, v: np.ndarray, p: dict) -> np.ndarray:
    ew, en = _frame(u, p)
    s = center_curve(u, p) + (_width(u, p) * v)[:, None] * ew + (_cup(u, p) * (v**2 - 1.0 / 3.0))[:, None] * en
    if len(p["rbf_c"]):
        d2 = np.sum((s[:, None, :] - p["rbf_c"][None, :, :]) ** 2, axis=2)
        s = s + np.exp(-d2 / (2.0 * p["rbf_w"] ** 2)) @ p["rbf_d"]
    return s


def skeleton_and_normal(u: np.ndarray, v: np.ndarray, p: dict) -> tuple[np.ndarray, np.ndarray]:
    s = _skeleton_raw(u, v, p)
    eps = 1e-3
    su = _skeleton_raw(u + eps, v, p) - _skeleton_raw(u - eps, v, p)
    sv = _skeleton_raw(u, v + eps, p) - _skeleton_raw(u, v - eps, p)
    n = np.cross(su, sv)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    _, en = _frame(u, p)
    sign = np.sign(np.sum(n * en, axis=1))
    sign[sign == 0] = 1.0
    return s, n * sign[:, None]


def atrophy_weight(u: np.ndarray, v: np.ndarray, a: dict) -> np.ndarray:
    uc, vc = np.clip(u, 0.0, 1.0), np.clip(v, -1.0, 1.0)
    return np.exp(-(((uc - a["ua"]) / a["su"]) ** 2) - (((vc - a["va"]) / a["sv"]) ** 2))


def half_thickness(u: np.ndarray, v: np.ndarray, p: dict, atrophy: dict | None = None, t: int = 0):
    uc, vc = np.clip(u, 0.0, 1.0), np.clip(v, -1.0, 1.0)
    t0 = 3.2 + 2.2 * np.exp(-(((uc - 0.15) / 0.16) ** 2)) - 0.6 * uc
    thick = p["ts"] * t0 * (1.0 - 0.35 * vc**2) * (1.0 + 0.08 * np.sin(3.0 * np.pi * vc + 2.0 * np.pi * uc))
    for amp, fu, fv, ph in p["modes"]:
        thick = thick * (1.0 + amp * np.sin(fu * np.pi * uc + fv * np.pi * vc + ph))
    # Disease-related (A+/CI-like) regional thinning present already at baseline.
    for depth, du, dv, su, sv in p["disease"]:
        thick = thick * (1.0 - depth * np.exp(-(((uc - du) / su) ** 2) - (((vc - dv) / sv) ** 2)))
    hs = thick * (0.5 + 0.06 * vc)
    hi = thick * (0.5 - 0.06 * vc)
    for du, dv, amp in p["digits"]:
        hs = hs + amp * np.exp(-(((uc - du) / 0.035) ** 2) - (((vc - dv) / 0.22) ** 2))
    hs = np.maximum(H_MIN, hs)
    hi = np.maximum(H_MIN, hi)
    if atrophy is not None and t > 0:
        g = atrophy_weight(u, v, atrophy)
        loss = atrophy["sev"] * (t / 3.0) * g * thick
        glob = 0.012 * t * thick
        hs = np.maximum(H_MIN, hs - atrophy["alpha"] * loss - 0.5 * glob)
        hi = np.maximum(H_MIN, hi - (1.0 - atrophy["alpha"]) * loss - 0.5 * glob)
    eu = np.maximum(0.0, np.maximum(-u, u - 1.0)) / U_EXT
    ev = np.maximum(0.0, np.abs(v) - 1.0) / V_EXT
    rho = np.sqrt(np.clip(1.0 - eu**2 - ev**2, 0.0, 1.0))
    return hs * rho, hi * rho


def sample_params(rng: np.random.Generator) -> dict:
    p = mean_params()
    p.update(
        R=18.0 * (1.0 + 0.10 * _z(rng)),
        span=0.9 * (1.0 + 0.06 * _z(rng)),
        zrise=4.0 * (1.0 + 0.4 * _z(rng)),
        xbow=0.6 * (1.0 + 0.35 * _z(rng)),
        twist=0.35 + 0.18 * _z(rng),
        ws=1.0 + 0.14 * _z(rng),
        m1=0.10 * _z(rng),
        m2=0.08 * _z(rng),
        head_u=0.12 + 0.04 * _z(rng),
        cs=1.0 + 0.3 * _z(rng),
        ts=max(0.75, 1.0 + 0.15 * _z(rng)),
        scale=1.0 + 0.07 * _z(rng),
    )
    n_modes = 4
    p["modes"] = np.column_stack(
        [
            0.07 * _z(rng, n_modes),
            rng.integers(1, 4, n_modes),
            rng.integers(1, 3, n_modes),
            rng.uniform(0.0, 2.0 * np.pi, n_modes),
        ]
    ).astype(float)
    n_dig = int(rng.integers(2, 5))
    p["digits"] = np.column_stack(
        [rng.uniform(0.03, 0.22, n_dig), rng.uniform(-0.7, 0.7, n_dig), rng.uniform(0.4, 0.9, n_dig)]
    )
    n_rbf = 12
    p["rbf_c"] = center_curve(rng.uniform(0.0, 1.0, n_rbf), p) + 2.0 * rng.standard_normal((n_rbf, 3))
    p["rbf_d"] = 1.5 * _z(rng, (n_rbf, 3))
    if rng.random() < 0.5:  # cognitively-impaired-like subject
        p["disease"] = np.array(
            [[rng.uniform(0.15, 0.35), rng.uniform(0.2, 0.8), rng.uniform(-0.7, 0.7), rng.uniform(0.12, 0.25), rng.uniform(0.4, 0.8)]]
        )
    return p


def sample_atrophy(rng: np.random.Generator) -> dict:
    return {
        "ua": rng.uniform(0.08, 0.28),
        "va": rng.uniform(-0.5, 0.5),
        "su": rng.uniform(0.10, 0.18),
        "sv": rng.uniform(0.5, 0.9),
        "sev": rng.uniform(0.45, 0.75),
        "alpha": rng.uniform(0.3, 0.7),
    }


def _rotvec(r: np.ndarray) -> np.ndarray:
    theta = float(np.linalg.norm(r))
    if theta < 1e-12:
        return np.eye(3)
    k = r / theta
    kx = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    return np.eye(3) + np.sin(theta) * kx + (1.0 - np.cos(theta)) * kx @ kx


def sample_pose(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    rot = _rotvec(np.clip(rng.normal(0.0, 0.15, 3), -0.3, 0.3))
    trans = np.array([25.0, -18.0, 12.0]) + rng.normal(0.0, 3.0, 3)
    return rot, trans


def followup_pose(rng: np.random.Generator, base: tuple[np.ndarray, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    rot = _rotvec(np.clip(rng.normal(0.0, 0.04, 3), -0.1, 0.1)) @ base[0]
    return rot, base[1] + rng.normal(0.0, 1.0, 3)


# ---------------------------------------------------------------------------
# Observation model (segmentation) and ground truth
# ---------------------------------------------------------------------------


def _grid(nu: int, nv: int, u_lo=0.0, u_hi=1.0, v_lo=-1.0, v_hi=1.0) -> tuple[np.ndarray, np.ndarray]:
    uu, vv = np.meshgrid(np.linspace(u_lo, u_hi, nu), np.linspace(v_lo, v_hi, nv), indexing="ij")
    return uu.ravel(), vv.ravel()


def _world(p: dict, pose, u, v, atrophy, t):
    rot, trans = pose
    sk, n = skeleton_and_normal(u, v, p)
    hs, hi = half_thickness(u, v, p, atrophy, t)
    s = p["scale"]
    return s * sk @ rot.T + trans, n @ rot.T, s * hs, s * hi


def voxelise(p: dict, pose, atrophy, t: int, rng: np.random.Generator | None):
    """Binary segmentation of the anatomy; rng=None gives a clean, unperturbed mask."""
    u, v = _grid(DENSE_NU, DENSE_NV, -U_EXT, 1.0 + U_EXT, -1.0 - V_EXT, 1.0 + V_EXT)
    sk, n, hs, hi = _world(p, pose, u, v, atrophy, t)
    bnd = np.concatenate([sk + n * hs[:, None], sk - n * hi[:, None]])
    offset = rng.uniform(0.0, SPACING, 3) if rng is not None else np.zeros(3)
    lo = np.floor((bnd.min(axis=0) - 2.0 - offset) / SPACING) * SPACING + offset
    hi_corner = bnd.max(axis=0) + 2.0
    shape = (np.ceil((hi_corner - lo) / SPACING).astype(int) + 1).astype(int)
    idx = np.indices(tuple(shape)).reshape(3, -1).T
    pts = lo + SPACING * idx
    tree = cKDTree(sk)
    dist, near = tree.query(pts, distance_upper_bound=float(max(hs.max(), hi.max())) + 1.5)
    inside = np.zeros(len(pts), dtype=bool)
    ok = np.isfinite(dist)
    q = pts[ok]
    j = near[ok]
    d = q - sk[j]
    sn = np.sum(d * n[j], axis=1)
    r = np.linalg.norm(d - sn[:, None] * n[j], axis=1)
    f = np.maximum(np.maximum(sn - hs[j], -hi[j] - sn), r - R0)
    if rng is not None:
        # Smooth boundary perturbation (segmentation inconsistency).
        centers = bnd[rng.choice(len(bnd), 40, replace=False)]
        amps = rng.normal(0.0, 0.2, 40)
        eta = np.zeros(len(q))
        for c, a in zip(centers, amps):
            eta += a * np.exp(-np.sum((q - c) ** 2, axis=1) / (2.0 * 2.0**2))
        f = f + eta
        # Voxel-wise label flips near the boundary (islands and pits).
        near_bnd = np.abs(f) < 0.35
        flip = near_bnd & (rng.random(len(q)) < 0.03)
        lab = f < 0.0
        lab[flip] = ~lab[flip]
        inside[ok] = lab
    else:
        inside[ok] = f < 0.0
    return inside.reshape(tuple(shape)), lo


def ground_truth(p: dict, pose, atrophy, t: int) -> dict:
    u, v = _grid(GRID_NU, GRID_NV)
    sk, n, hs, hi = _world(p, pose, u, v, atrophy, t)
    us, vs = _grid(SURF_NU, SURF_NV)
    sks, ns, hss, his = _world(p, pose, us, vs, atrophy, t)
    surface = np.concatenate([sks + ns * hss[:, None], sks - ns * his[:, None]])
    return {
        "skeleton_gt": sk,
        "sup_gt": sk + n * hs[:, None],
        "inf_gt": sk - n * hi[:, None],
        "thickness_gt": hs + hi,
        "atrophy_region": atrophy_weight(u, v, atrophy) >= 0.3,
        "surface_gt": surface,
    }


def subfield_ids() -> np.ndarray:
    u, v = _grid(GRID_NU, GRID_NV)
    sf = np.full(len(u), 2, dtype=np.int64)  # CA_DG (central band)
    sf[v < -0.35] = 1  # subiculum
    sf[v > 0.35] = 3  # CA1
    sf[u < 0.2] = 0  # head
    sf[u > 0.85] = 4  # tail
    return sf


def pack_masks(masks: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    packed = [np.packbits(m.ravel().astype(np.uint8)) for m in masks]
    offsets = np.concatenate([[0], np.cumsum([len(b) for b in packed])]).astype(np.int64)
    shapes = np.asarray([m.shape for m in masks], dtype=np.int64)
    return np.concatenate(packed).astype(np.uint8), offsets, shapes


def make_cohort(seed: int, n_subjects: int, n_timepoints: int = 4) -> tuple[dict, dict]:
    """Return (method-visible inputs, evaluation labels) for a cohort."""
    children = np.random.SeedSequence(seed).spawn(n_subjects)
    subjects, masks, origins = [], [], []
    labels: dict[str, list] = {k: [] for k in ("skeleton_gt", "sup_gt", "inf_gt", "thickness_gt", "atrophy_region", "surface_gt")}
    for sid, child in enumerate(children):
        rng = np.random.default_rng(child)
        p = sample_params(rng)
        atrophy = sample_atrophy(rng)
        pose0 = sample_pose(rng)
        for t in range(n_timepoints):
            pose = pose0 if t == 0 else followup_pose(rng, pose0)
            mask, origin = voxelise(p, pose, atrophy, t, rng)
            gt = ground_truth(p, pose, atrophy, t)
            subjects.append([sid, t])
            masks.append(mask)
            origins.append(origin)
            for k in labels:
                labels[k].append(gt[k])
    bits, offsets, shapes = pack_masks(masks)
    subjects_arr = np.asarray(subjects, dtype=np.int64)
    inputs = {
        "subjects": subjects_arr,
        "mask_bits": bits,
        "mask_offsets": offsets,
        "mask_shapes": shapes,
        "origins": np.asarray(origins, dtype=np.float64),
        "spacing": np.full(len(subjects), SPACING, dtype=np.float64),
    }
    out_labels = {"subjects": subjects_arr}
    for k, vals in labels.items():
        arr = np.asarray(vals)
        out_labels[k] = arr if arr.dtype == bool else arr.astype(np.float32)
    return inputs, out_labels


def make_template() -> dict:
    p = mean_params()
    pose = (np.eye(3), np.zeros(3))
    u, v = _grid(GRID_NU, GRID_NV)
    sk, n = skeleton_and_normal(u, v, p)
    hs, hi = half_thickness(u, v, p)
    mask, origin = voxelise(p, pose, None, 0, None)
    bits, offsets, shapes = pack_masks([mask])
    return {
        "skeleton": sk,
        "sup_dir": n,
        "inf_dir": -n,
        "sup_len": hs,
        "inf_len": hi,
        "grid_shape": np.array([GRID_NU, GRID_NV], dtype=np.int64),
        "u": u,
        "v": v,
        "subfield_id": subfield_ids(),
        "subfield_names": np.asarray(SUBFIELDS),
        "mask_bits": bits,
        "mask_shape": shapes[0],
        "origin": origin,
        "spacing": np.float64(SPACING),
    }


def export_public(out_dir: Path, train_seed: int, n_train: int) -> None:
    """Write the public template and the visible development (train) cohort."""
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / "hippo_template.npz", **make_template())
    inputs, labels = make_cohort(train_seed, n_train)
    np.savez_compressed(out_dir / "hippo_train.npz", **inputs)
    np.savez_compressed(out_dir / "hippo_train_labels.npz", subfield_id=subfield_ids(), **labels)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-public", type=Path, required=True)
    parser.add_argument("--train-seed", type=int, default=20251219)
    parser.add_argument("--train-subjects", type=int, default=16)
    args = parser.parse_args()
    export_public(args.export_public, args.train_seed, args.train_subjects)


if __name__ == "__main__":
    main()
