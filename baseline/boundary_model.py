#!/usr/bin/env python3
"""Boundary-driven baseline: per-scan linear template fit + nearest-boundary projection.

Every scan (baseline or follow-up) is processed independently, the way
boundary-anchored shape models re-parameterise each surface. The template
surface is aligned to the scan surface with a similarity ICP; each template
implied boundary point is then projected onto the nearest scan-surface vertex
with a compatible normal. There is no interior skeletal coordinate system, no
nonlinear deformation and no baseline anchoring of follow-ups. The skeletal
point is reported as the midpoint of the projected superior/inferior points.
"""

from __future__ import annotations

import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))
import hippo_io  # noqa: E402

_STATE: dict = {}


def _umeyama(src, dst):
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    xs, xd = src - mu_s, dst - mu_d
    u, sv, vt = np.linalg.svd(xd.T @ xs / len(src))
    d = np.ones(3)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        d[2] = -1.0
    rot = u @ np.diag(d) @ vt
    scale = float(np.sum(sv * d) / np.mean(np.sum(xs**2, axis=1)))
    return scale, rot, mu_d - scale * rot @ mu_s


def _icp(src, src_n, dst, dst_n, iters=40):
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    s = float(np.sqrt(np.mean(np.sum((dst - mu_d) ** 2, axis=1)) / np.mean(np.sum((src - mu_s) ** 2, axis=1))))
    s, rot, t = s, np.eye(3), mu_d - s * mu_s
    tree = cKDTree(dst)
    for _ in range(iters):
        x = s * src @ rot.T + t
        xn = src_n @ rot.T
        _, j = tree.query(x)
        ok = np.sum(xn * dst_n[j], axis=1) > 0.3
        if ok.sum() < 10:
            break
        s2, r2, t2 = _umeyama(src[ok], dst[j[ok]])
        change = abs(s2 - s) + np.linalg.norm(r2 - rot) + np.linalg.norm(t2 - t)
        s, rot, t = s2, r2, t2
        if change < 1e-6:
            break
    return s, rot, t


def _scan(row):
    scans, tpl = _STATE["scans"], _STATE["tpl"]
    v, _, vn = hippo_io.surface_from_mask(scans["masks"][row], scans["origins"][row], float(scans["spacing"][row]))
    s, rot, t = _icp(tpl["surf_v"], tpl["surf_n"], v, vn)
    tree = cKDTree(v)

    def project(points, dirs):
        q = s * points @ rot.T + t
        qn = dirs @ rot.T
        d, j = tree.query(q, k=8)
        cost = d**2 + 4.0 * (1.0 - np.einsum("nkd,nd->nk", vn[j], qn))
        return v[j[np.arange(len(q)), np.argmin(cost, axis=1)]]

    sup = project(tpl["sup_pts"], tpl["sup_dir"])
    inf = project(tpl["inf_pts"], tpl["inf_dir"])
    return row, 0.5 * (sup + inf), sup, inf


def run(input_path: Path, template_path: Path, output_path: Path, workers: int = 0) -> None:
    scans = hippo_io.load_scans(input_path)
    tpl = hippo_io.load_template(template_path)
    sv, _, sn = hippo_io.surface_from_mask(tpl["mask"], tpl["origin"], tpl["spacing"])
    skel = tpl["skeleton"].astype(float)
    _STATE.update(
        scans=scans,
        tpl={
            "surf_v": sv,
            "surf_n": sn,
            "sup_pts": skel + tpl["sup_dir"] * tpl["sup_len"][:, None],
            "inf_pts": skel + tpl["inf_dir"] * tpl["inf_len"][:, None],
            "sup_dir": tpl["sup_dir"],
            "inf_dir": tpl["inf_dir"],
        },
    )
    n = len(scans["subjects"])
    try:
        cpus = len(os.sched_getaffinity(0))
    except AttributeError:
        cpus = os.cpu_count() or 1
    workers = max(1, min(workers or min(cpus, 16), n))
    if workers > 1:
        with mp.get_context("fork").Pool(workers) as pool:
            results = pool.map(_scan, range(n), chunksize=4)
    else:
        results = [_scan(r) for r in range(n)]
    k = len(skel)
    skeleton, sup_end, inf_end = np.zeros((n, k, 3)), np.zeros((n, k, 3)), np.zeros((n, k, 3))
    for row, p, s_, i_ in results:
        skeleton[row], sup_end[row], inf_end[row] = p, s_, i_
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, subjects=scans["subjects"], skeleton=skeleton, sup_end=sup_end, inf_end=inf_end)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/hippo_train.npz")
    parser.add_argument("--template", type=Path, default=ROOT / "data/hippo_template.npz")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/boundary_baseline_train.npz")
    parser.add_argument("--workers", type=int, default=0)
    args = parser.parse_args()
    run(args.input, args.template, args.output, args.workers)


if __name__ == "__main__":
    main()
