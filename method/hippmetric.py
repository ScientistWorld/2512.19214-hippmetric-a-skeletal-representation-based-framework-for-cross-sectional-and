#!/usr/bin/env python3
"""HippMetric (scaled reproduction): skeletal-representation hippocampal morphometry.

Pipeline (paper Sections 3.2-3.5, Fig. 1):
  1. Surface extraction and refinement (RBOS, scaled): voxel-boundary surface of
     the segmentation, largest component, Taubin smoothing.
  2. Rigid (similarity) alignment of the template surface to the baseline surface.
  3. Dense diffeomorphic deformation of the template surface onto the subject
     surface with a Gaussian kernel whose width is refined from 7 mm to 3 mm in
     0.5 mm steps until the mean surface distance falls below a threshold. The
     same velocity fields transport the template's internal landmarks (skeletal
     points and implied boundary points) into subject space.
  4. Spoke refinement under the s-rep constraints: per-point case analysis by
     ray/mesh intersection (inside / outside with >=2 intersections / invalid),
     E0 (boundary convergence) and E1 (orthogonality, 0.1 rad steps, <=50
     iterations) for three rounds, E2 (superior/inferior length symmetry) after
     the last round, and a final E0.
  5. Longitudinal processing: follow-ups are rigidly registered to the baseline
     surface; the baseline skeletal points and spoke directions are reused and
     only spoke lengths are re-optimised (E0) on the follow-up surface.

Outputs, per scan and per template skeletal point: refined skeletal point and the
superior/inferior spoke endpoints. Thickness is the sum of the two spoke lengths.
"""

from __future__ import annotations

import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse
import itertools
import multiprocessing as mp
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))
import hippo_io  # noqa: E402


@dataclass
class Config:
    dense: bool = True  # nonlinear template-to-subject deformation (paper: LDDMM)
    widths: tuple = tuple(np.round(np.arange(7.0, 2.99, -0.5), 2))  # kernel widths, mm
    iters_per_width: int = 6
    flow_step: float = 0.5
    match_threshold: float = 0.2  # mm, mean surface distance that stops refinement
    control_cell: float = 1.5  # mm, control-point cell size
    normal_weight: float = 4.0  # mm^2 penalty for normal disagreement in matching
    e_rounds: int = 3  # E0 -> E1 rounds (paper: 2-3)
    angle_step: float = 0.1  # rad (paper)
    angle_iters: int = 50  # (paper)
    e2_threshold: float = 0.6  # rad, "large angular deviation" corrected by E2
    max_ray: float = 10.0  # mm
    anchor_followups: bool = True  # baseline-anchored longitudinal model
    length_smoothing: float = 0.0  # grid units; 0 = paper procedure
    smooth_iterations: int = 20  # Taubin iterations in surface refinement
    workers: int = 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def umeyama(src: np.ndarray, dst: np.ndarray, with_scale: bool = True):
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    xs, xd = src - mu_s, dst - mu_d
    cov = xd.T @ xs / len(src)
    u, sv, vt = np.linalg.svd(cov)
    d = np.ones(3)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        d[2] = -1.0
    rot = u @ np.diag(d) @ vt
    scale = float(np.sum(sv * d) / np.mean(np.sum(xs**2, axis=1))) if with_scale else 1.0
    return scale, rot, mu_d - scale * rot @ mu_s


def apply(tf, x: np.ndarray) -> np.ndarray:
    s, rot, t = tf
    return s * x @ rot.T + t


def _axis_rotation(axis: int, angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    i, j = [a for a in range(3) if a != axis]
    rot = np.eye(3)
    rot[i, i], rot[i, j], rot[j, i], rot[j, j] = c, -s, s, c
    return rot


# Identity plus +-20 degree turns about each axis: starts for the rigid alignment.
INIT_ROTATIONS = [np.eye(3)] + [_axis_rotation(a, sgn * 0.35) for a in range(3) for sgn in (-1.0, 1.0)]


def _alignment_cost(tf, src, src_n, dst, dst_n, dtree):
    x = apply(tf, src)
    d1, j = dtree.query(x)
    d2, _ = cKDTree(x).query(dst)
    agree = np.sum((src_n @ tf[1].T) * dst_n[j], axis=1)
    return 0.5 * (d1.mean() + d2.mean()) + np.mean(1.0 - np.clip(agree, -1.0, 1.0))


def similarity_icp(src, src_n, dst, dst_n, with_scale=True, iters=40, trim=0.9, multistart=True):
    """Rigid/similarity alignment, dst ~ s R src + t, from several initial rotations.

    Each start is refined briefly; the start with the lowest symmetric surface
    distance (plus normal disagreement) is then refined to convergence.
    """
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    s = 1.0
    if with_scale:
        s = float(np.sqrt(np.mean(np.sum((dst - mu_d) ** 2, axis=1)) / np.mean(np.sum((src - mu_s) ** 2, axis=1))))
    dtree = cKDTree(dst)
    if not multistart:
        return _icp_refine((s, np.eye(3), mu_d - s * mu_s), src, src_n, dst, dst_n, dtree, with_scale, iters, trim)
    best, best_cost = None, np.inf
    for rot0 in INIT_ROTATIONS:
        tf = _icp_refine((s, rot0, mu_d - s * rot0 @ mu_s), src, src_n, dst, dst_n, dtree, with_scale, 12, trim)
        cost = _alignment_cost(tf, src, src_n, dst, dst_n, dtree)
        if cost < best_cost:
            best, best_cost = tf, cost
    return _icp_refine(best, src, src_n, dst, dst_n, dtree, with_scale, iters, trim)


def _icp_refine(tf, src, src_n, dst, dst_n, dtree, with_scale, iters, trim):
    for _ in range(iters):
        x = apply(tf, src)
        xn = src_n @ tf[1].T
        d1, j = dtree.query(x)
        ok1 = np.sum(xn * dst_n[j], axis=1) > 0.3
        d2, i = cKDTree(x).query(dst)
        ok2 = np.sum(xn[i] * dst_n, axis=1) > 0.3
        a = np.concatenate([src[ok1], src[i[ok2]]])
        b = np.concatenate([dst[j[ok1]], dst[ok2]])
        dd = np.concatenate([d1[ok1], d2[ok2]])
        if len(dd) < 10:
            break
        if trim < 1.0:
            keep = dd <= np.quantile(dd, trim)
            a, b = a[keep], b[keep]
        new = umeyama(a, b, with_scale)
        change = abs(new[0] - tf[0]) + np.linalg.norm(new[1] - tf[1]) + np.linalg.norm(new[2] - tf[2])
        tf = new
        if change < 1e-6:
            break
    return tf


def _matching_forces(x, xn, dst, dst_n, dtree, normal_weight, k=6):
    d, j = dtree.query(x, k=k)
    cost = d**2 + normal_weight * (1.0 - np.einsum("nd,nkd->nk", xn, dst_n[j]))
    jj = j[np.arange(len(x)), np.argmin(cost, axis=1)]
    fwd = dst[jj] - x
    d2, i = cKDTree(x).query(dst, k=k)
    cost2 = d2**2 + normal_weight * (1.0 - np.einsum("mkd,md->mk", xn[i], dst_n))
    ii = i[np.arange(len(dst)), np.argmin(cost2, axis=1)]
    back = dst - x[ii]
    acc = np.zeros_like(x)
    np.add.at(acc, ii, back)
    cnt = np.bincount(ii, minlength=len(x))
    force = fwd.copy()
    has = cnt > 0
    force[has] = 0.5 * (fwd[has] + acc[has] / cnt[has, None])
    mean_dist = 0.5 * (np.linalg.norm(fwd, axis=1).mean() + np.linalg.norm(back, axis=1).mean())
    return force, float(mean_dist)


def _cell_controls(x, force, cell):
    keys = np.floor(x / cell).astype(np.int64)
    keys -= keys.min(axis=0)
    dims = keys.max(axis=0) + 1
    code = (keys[:, 0] * dims[1] + keys[:, 1]) * dims[2] + keys[:, 2]
    _, inv, cnt = np.unique(code, return_inverse=True, return_counts=True)
    inv = inv.reshape(-1)
    c = np.zeros((len(cnt), 3))
    f = np.zeros((len(cnt), 3))
    np.add.at(c, inv, x)
    np.add.at(f, inv, force)
    return c / cnt[:, None], f / cnt[:, None], cnt.astype(float)


def _kernel_velocity(z, c, f, w, width):
    d2 = np.sum(z**2, axis=1)[:, None] + np.sum(c**2, axis=1)[None, :] - 2.0 * z @ c.T
    k = np.exp(-np.maximum(d2, 0.0) / (2.0 * width * width)) * w[None, :]
    return (k @ f) / np.maximum(k.sum(axis=1, keepdims=True), 1e-12)


def dense_deformation(x, faces, internal, dst, dst_n, cfg: Config):
    """Coarse-to-fine Gaussian-kernel diffeomorphic flow of the template surface.

    Each step is a smooth velocity field (Gaussian kernel of the current width
    acting on symmetric surface-matching forces) applied with a step bounded by
    a quarter of the kernel width, so the composed map stays invertible. The
    same fields move the internal template landmarks.
    """
    x = x.copy()
    internal = internal.copy()
    dtree = cKDTree(dst)
    n_x = len(x)
    used_width = None
    dist = np.inf
    for width in cfg.widths:
        used_width = width
        for _ in range(cfg.iters_per_width):
            xn = hippo_io.vertex_normals(x, faces)
            force, dist = _matching_forces(x, xn, dst, dst_n, dtree, cfg.normal_weight)
            if dist < cfg.match_threshold:
                return x, internal, used_width, dist
            c, f, w = _cell_controls(x, force, cfg.control_cell)
            z = np.vstack([x, internal])
            vel = _kernel_velocity(z, c, f, w, width)
            vmax = float(np.linalg.norm(vel, axis=1).max())
            tau = min(cfg.flow_step, 0.25 * width / max(vmax, 1e-12))
            z = z + tau * vel
            x, internal = z[:n_x], z[n_x:]
    return x, internal, used_width, dist


# ---------------------------------------------------------------------------
# Spoke refinement
# ---------------------------------------------------------------------------


class MeshQuery:
    CHUNK = 400_000

    def __init__(self, vertices, faces, normals):
        self.v = vertices
        self.n = normals
        tri = vertices[faces]
        self.v0 = tri[:, 0]
        self.e1 = tri[:, 1] - tri[:, 0]
        self.e2 = tri[:, 2] - tri[:, 0]
        cent = tri.mean(axis=1)
        self.ctree = cKDTree(cent)
        self.tri_r = float(np.linalg.norm(tri - cent[:, None, :], axis=2).max())
        self.vtree = cKDTree(vertices)

    def cast(self, origins, dirs, max_len):
        """Ray/mesh intersections within max_len: (count, first t, second t)."""
        n = len(origins)
        counts = np.zeros(n, dtype=np.int64)
        first = np.full(n, np.nan)
        second = np.full(n, np.nan)
        if n == 0:
            return counts, first, second
        lists = self.ctree.query_ball_point(origins + 0.5 * max_len * dirs, r=0.5 * max_len + self.tri_r)
        lens = np.fromiter((len(l) for l in lists), dtype=np.int64, count=n)
        total = int(lens.sum())
        if total == 0:
            return counts, first, second
        ray = np.repeat(np.arange(n), lens)
        tri = np.fromiter(itertools.chain.from_iterable(lists), dtype=np.int64, count=total)
        hit_r, hit_t = [], []
        for s in range(0, total, self.CHUNK):
            r = ray[s : s + self.CHUNK]
            tr = tri[s : s + self.CHUNK]
            d = dirs[r]
            e1, e2 = self.e1[tr], self.e2[tr]
            p = np.cross(d, e2)
            det = np.sum(e1 * p, axis=1)
            ok = np.abs(det) > 1e-12
            inv = np.zeros_like(det)
            inv[ok] = 1.0 / det[ok]
            sv = origins[r] - self.v0[tr]
            uu = np.sum(sv * p, axis=1) * inv
            q = np.cross(sv, e1)
            vv = np.sum(d * q, axis=1) * inv
            tt = np.sum(e2 * q, axis=1) * inv
            ok &= (uu >= 0.0) & (uu <= 1.0) & (vv >= 0.0) & (uu + vv <= 1.0) & (tt > 1e-6) & (tt <= max_len)
            hit_r.append(r[ok])
            hit_t.append(tt[ok])
        r = np.concatenate(hit_r)
        t = np.concatenate(hit_t)
        if len(r) == 0:
            return counts, first, second
        order = np.lexsort((t, r))
        r, t = r[order], t[order]
        dup = np.zeros(len(r), dtype=bool)
        dup[1:] = (r[1:] == r[:-1]) & (np.abs(t[1:] - t[:-1]) < 1e-6)
        r, t = r[~dup], t[~dup]
        counts = np.bincount(r, minlength=n)
        starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
        has1 = counts >= 1
        first[has1] = t[starts[has1]]
        has2 = counts >= 2
        second[has2] = t[starts[has2] + 1]
        return counts, first, second

    def inside_by_normal(self, points):
        _, j = self.vtree.query(points)
        return np.sum((points - self.v[j]) * self.n[j], axis=1) < 0.0

    def nearest_normal(self, points):
        _, j = self.vtree.query(points)
        return self.n[j]


def _unit(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-12)


def e0_cases(p, ds, di, mesh: MeshQuery, max_len):
    """Boundary convergence with the paper's three skeletal-point cases (Fig. 3B)."""
    cs, fs, ss = mesh.cast(p, ds, max_len)
    ci, fi, si = mesh.cast(p, di, max_len)
    odd_s, odd_i = cs % 2 == 1, ci % 2 == 1
    inside = odd_s & odd_i
    amb = odd_s ^ odd_i
    if amb.any():
        inside[amb] = mesh.inside_by_normal(p[amb])
    p = p.copy()
    ds, di = ds.copy(), di.copy()
    ls = np.zeros(len(p))
    li = np.zeros(len(p))
    # Case 1: inside -> keep the skeletal point, endpoints at first boundary crossings.
    c1 = inside & (cs >= 1) & (ci >= 1)
    ls[c1], li[c1] = fs[c1], fi[c1]
    # Case 2: outside with >=2 intersections -> skeletal point moves into the object;
    # the two crossings bound the local thickness.
    c2s = ~inside & (cs >= 2)
    c2i = ~inside & ~c2s & (ci >= 2)
    for sel, d, f, s in ((c2s, ds, fs, ss), (c2i, di, fi, si)):
        if sel.any():
            a = p[sel] + d[sel] * f[sel, None]
            b = p[sel] + d[sel] * s[sel, None]
            mid = 0.5 * (a + b)
            half = 0.5 * (s[sel] - f[sel])
            out_dir = d[sel].copy()
            p[sel] = mid
            if d is ds:
                ds[sel], di[sel] = out_dir, -out_dir
            else:
                di[sel], ds[sel] = out_dir, -out_dir
            ls[sel], li[sel] = half, half
    # Case 3: anything else is invalid.
    valid = c1 | c2s | c2i
    return p, ds, di, ls, li, valid


def e1_orthogonality(p, d, length, mesh: MeshQuery, cfg: Config):
    """Rotate spokes toward the boundary normal at their tips (0.1 rad steps)."""
    d = d.copy()
    for _ in range(cfg.angle_iters):
        n = mesh.nearest_normal(p + d * length[:, None])
        cos = np.clip(np.sum(d * n, axis=1), -1.0, 1.0)
        ang = np.arccos(cos)
        active = ang > 0.02
        if not active.any():
            break
        perp = _unit(n - cos[:, None] * d)
        step = np.minimum(cfg.angle_step, ang)
        new = np.cos(step)[:, None] * d + np.sin(step)[:, None] * perp
        d[active] = _unit(new[active])
    return d


def refine_baseline_spokes(p0, ds0, di0, mesh: MeshQuery, cfg: Config):
    p, ds, di = p0.copy(), ds0.copy(), di0.copy()
    for _ in range(cfg.e_rounds):
        p, ds, di, ls, li, valid = e0_cases(p, ds, di, mesh, cfg.max_ray)
        if valid.any():
            ds[valid] = e1_orthogonality(p[valid], ds[valid], ls[valid], mesh, cfg)
            di[valid] = e1_orthogonality(p[valid], di[valid], li[valid], mesh, cfg)
    # E2: spokes that E1 rotated far from the transported (regular) field are reset,
    # then superior/inferior lengths are equalised by recentring the skeletal point.
    p, ds, di, ls, li, valid = e0_cases(p, ds, di, mesh, cfg.max_ray)
    big_s = np.arccos(np.clip(np.sum(ds * ds0, axis=1), -1, 1)) > cfg.e2_threshold
    big_i = np.arccos(np.clip(np.sum(di * di0, axis=1), -1, 1)) > cfg.e2_threshold
    ds[big_s], di[big_i] = ds0[big_s], di0[big_i]
    p, ds, di, ls, li, valid = e0_cases(p, ds, di, mesh, cfg.max_ray)
    medial = _unit(ds - di)
    shift = np.where(valid, 0.5 * (ls - li), 0.0)
    p = p + shift[:, None] * medial
    # Final E0 restores boundary adherence after the orientation/position update.
    return e0_cases(p, ds, di, mesh, cfg.max_ray)


def _smooth_lengths(lengths, valid, grid_shape, sigma):
    if sigma <= 0:
        return lengths
    w = valid.astype(float).reshape(grid_shape)
    num = gaussian_filter(lengths.reshape(grid_shape) * w, sigma, mode="nearest")
    den = gaussian_filter(w, sigma, mode="nearest")
    out = np.where(den > 1e-6, num / np.maximum(den, 1e-6), lengths.reshape(grid_shape)).ravel()
    return np.where(valid, out, lengths)


# ---------------------------------------------------------------------------
# Subject processing
# ---------------------------------------------------------------------------

_STATE: dict = {}


def _surface(row):
    scans = _STATE["scans"]
    return hippo_io.surface_from_mask(
        scans["masks"][row], scans["origins"][row], float(scans["spacing"][row]), _STATE["cfg"].smooth_iterations
    )


def _fit_scan(v, f, vn, cfg: Config):
    """Template -> scan: similarity alignment, dense deformation, spoke refinement."""
    tpl = _STATE["tpl"]
    tf = similarity_icp(tpl["surf_v"], tpl["surf_n"], v, vn, with_scale=True)
    x = apply(tf, tpl["surf_v"])
    internal = apply(tf, tpl["internal"])
    if cfg.dense:
        x, internal, _, _ = dense_deformation(x, tpl["surf_f"], internal, v, vn, cfg)
    n = tpl["n_points"]
    p0, es0, ei0 = internal[:n], internal[n : 2 * n], internal[2 * n :]
    ds0, di0 = _unit(es0 - p0), _unit(ei0 - p0)
    mesh = MeshQuery(v, f, vn)
    p, ds, di, ls, li, valid = refine_baseline_spokes(p0, ds0, di0, mesh, cfg)
    # Invalid spokes keep the deformed template geometry.
    p = np.where(valid[:, None], p, p0)
    ds = np.where(valid[:, None], ds, ds0)
    di = np.where(valid[:, None], di, di0)
    ls = np.where(valid, ls, np.linalg.norm(es0 - p0, axis=1))
    li = np.where(valid, li, np.linalg.norm(ei0 - p0, axis=1))
    return p, ds, di, ls, li, valid


def _emit(p, ds, di, ls, li, valid, cfg):
    shape = tuple(_STATE["tpl"]["grid_shape"])
    ls = _smooth_lengths(ls, valid, shape, cfg.length_smoothing)
    li = _smooth_lengths(li, valid, shape, cfg.length_smoothing)
    return p, p + ds * ls[:, None], p + di * li[:, None]


def process_subject(rows):
    cfg: Config = _STATE["cfg"]
    subjects = _STATE["scans"]["subjects"]
    rows = sorted(rows, key=lambda r: subjects[r, 1])
    out = {}
    base = rows[0]
    vb, fb, nb = _surface(base)
    p, ds, di, ls, li, valid = _fit_scan(vb, fb, nb, cfg)
    out[base] = _emit(p, ds, di, ls, li, valid, cfg)
    for row in rows[1:]:
        vf, ff, nf = _surface(row)
        if not cfg.anchor_followups:
            out[row] = _emit(*_fit_scan(vf, ff, nf, cfg), cfg)
            continue
        # Follow-up -> baseline rigid registration; reuse baseline spokes, re-optimise lengths.
        tf = similarity_icp(vb, nb, vf, nf, with_scale=False, trim=0.8, multistart=False)
        pf = apply(tf, p)
        dsf, dif = ds @ tf[1].T, di @ tf[1].T
        mesh = MeshQuery(vf, ff, nf)
        p2, ds2, di2, ls2, li2, valid2 = e0_cases(pf, dsf, dif, mesh, cfg.max_ray)
        p2 = np.where(valid2[:, None], p2, pf)
        ds2 = np.where(valid2[:, None], ds2, dsf)
        di2 = np.where(valid2[:, None], di2, dif)
        ls2 = np.where(valid2, ls2, ls)
        li2 = np.where(valid2, li2, li)
        out[row] = _emit(p2, ds2, di2, ls2, li2, valid2, cfg)
    return out


def _available_cpus() -> int:
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        return os.cpu_count() or 1


def run(input_path: Path, template_path: Path, output_path: Path, cfg: Config) -> None:
    scans = hippo_io.load_scans(input_path)
    tpl = hippo_io.load_template(template_path)
    sv, sf, sn = hippo_io.surface_from_mask(tpl["mask"], tpl["origin"], tpl["spacing"], cfg.smooth_iterations)
    skel = tpl["skeleton"].astype(float)
    internal = np.concatenate(
        [skel, skel + tpl["sup_dir"] * tpl["sup_len"][:, None], skel + tpl["inf_dir"] * tpl["inf_len"][:, None]]
    )
    _STATE.update(
        scans=scans,
        cfg=cfg,
        tpl={
            "surf_v": sv,
            "surf_f": sf,
            "surf_n": sn,
            "internal": internal,
            "n_points": len(skel),
            "grid_shape": tuple(int(x) for x in tpl["grid_shape"]),
        },
    )
    subjects = scans["subjects"]
    groups: dict[int, list[int]] = {}
    for row, (sid, _) in enumerate(subjects):
        groups.setdefault(int(sid), []).append(row)
    jobs = [groups[k] for k in sorted(groups)]
    workers = cfg.workers or min(_available_cpus(), 16)
    workers = max(1, min(workers, len(jobs)))
    if workers > 1:
        with mp.get_context("fork").Pool(workers) as pool:
            results = pool.map(process_subject, jobs, chunksize=1)
    else:
        results = [process_subject(j) for j in jobs]
    n = len(subjects)
    k = len(skel)
    skeleton = np.zeros((n, k, 3))
    sup_end = np.zeros((n, k, 3))
    inf_end = np.zeros((n, k, 3))
    for res in results:
        for row, (p, s, i) in res.items():
            skeleton[row], sup_end[row], inf_end[row] = p, s, i
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, subjects=subjects, skeleton=skeleton, sup_end=sup_end, inf_end=inf_end)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=ROOT / "data/hippo_train.npz")
    parser.add_argument("--template", type=Path, default=ROOT / "data/hippo_template.npz")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/hippmetric_train.npz")
    parser.add_argument("--no-dense", action="store_true", help="ablation: similarity alignment only")
    parser.add_argument("--independent-followups", action="store_true", help="ablation: refit every scan independently")
    parser.add_argument("--length-smoothing", type=float, default=0.0)
    parser.add_argument("--match-threshold", type=float, default=Config.match_threshold)
    parser.add_argument("--iters-per-width", type=int, default=Config.iters_per_width)
    parser.add_argument("--workers", type=int, default=0)
    args = parser.parse_args()
    cfg = Config(
        dense=not args.no_dense,
        anchor_followups=not args.independent_followups,
        length_smoothing=args.length_smoothing,
        match_threshold=args.match_threshold,
        iters_per_width=args.iters_per_width,
        workers=args.workers,
    )
    run(args.input, args.template, args.output, cfg)


if __name__ == "__main__":
    main()
