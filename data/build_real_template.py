#!/usr/bin/env python3
"""Build the public real-anatomy files from the MSD Task04 hippocampus labels.

Writes
  data/hippo_real_anatomy.npz   development subjects' 1 mm label masks (format in
                                data/msd_hippocampus.py); the held-out cases are
                                excluded and never written to data/.
  data/hippo_real_template.npz  template for the real-anatomy cohort, in the same
                                format as data/hippo_template.npz (61 x 9 skeletal
                                grid, superior/inferior spokes, subfield ids,
                                template segmentation on a 0.5 mm grid).

Template construction (agent-authored, deterministic):
  1. Each development label is turned into a smooth signed distance field on a
     0.5 mm grid.
  2. Subjects are rigidly aligned (ICP) to the median-volume subject, the
     signed distance fields are averaged; the subjects are re-aligned to that
     mean and averaged again. The mean shape is the zero level set.
  3. The long axis is a smooth curve through the centroids of cross-sections
     along the first principal axis, from the head (label 1) to the tail. 61
     lamellae are placed perpendicular to it at equal arc length; in each, 9
     positions span the cross-section along a common width axis, and the
     superior/inferior spokes are the chord of the mean shape through each
     position along the lamellar normal (skeletal point = chord midpoint).
  4. Subfield ids: head where the averaged head label is >= 0.5, otherwise body
     (u <= 0.8) or tail.

Usage: python data/build_real_template.py [--archive data/downloads/msd/Task04_Hippocampus.tar]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import msd_hippocampus as msd  # noqa: E402

H = 0.5  # mm, working resolution (the paper resamples segmentations to 0.5 mm)
GRID_NU, GRID_NV = 61, 9
U_LO, U_HI = 0.04, 0.96  # arc-length fraction covered by the lamellae
V_EXT = 0.9  # fraction of the half-width covered across a lamella
SUBFIELDS = ("head", "body", "tail")


# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------


def sdf_from_mask(mask: np.ndarray, h: float) -> np.ndarray:
    din = distance_transform_edt(mask) * h
    dout = distance_transform_edt(~mask) * h
    return np.where(mask, -(din - 0.5 * h), dout - 0.5 * h).astype(np.float32)


def largest_filled(mask: np.ndarray) -> np.ndarray:
    mask = ndimage.binary_fill_holes(mask)
    lab, n = ndimage.label(mask)
    if n > 1:
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        mask = lab == int(np.argmax(sizes))
    return mask


def fields_05(mask1: np.ndarray, ant1: np.ndarray, sp1: float, pad_mm: float = 5.0):
    """Smooth signed distance field (and head fraction) on a 0.5 mm grid.

    Coordinates: voxel (0, 0, 0) of the given 1 mm crop is at the origin.
    """
    pad = int(np.ceil(pad_mm / sp1))
    m = np.pad(mask1.astype(bool), pad)
    a = np.pad(ant1.astype(bool), pad)
    sdf1 = gaussian_filter(sdf_from_mask(m, sp1), 0.7 / sp1)
    ratio = sp1 / H
    n05 = tuple(int(x) for x in (np.array(m.shape) - 1) * ratio + 1)
    idx = np.indices(n05, dtype=np.float32).reshape(3, -1) / ratio
    s05 = map_coordinates(sdf1, idx, order=1, mode="nearest").reshape(n05)
    m05 = largest_filled(s05 < 0)
    phi = gaussian_filter(sdf_from_mask(m05, H), 1.0)
    ant = map_coordinates(a.astype(np.float32), idx, order=1, mode="constant", cval=0.0).reshape(n05)
    origin = np.full(3, -pad * sp1)
    return phi.astype(np.float32), ant.astype(np.float32), origin


def level_points(phi: np.ndarray, origin: np.ndarray, h: float = H, band: float = 0.35):
    """Points on the zero level set (projected band voxels) and unit outward normals."""
    sel = np.abs(phi) < band
    grads = np.gradient(phi.astype(np.float32), h)
    g = np.stack([gr[sel] for gr in grads], axis=1).astype(float)
    idx = np.argwhere(sel)
    p = origin + h * idx
    nrm = np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
    p = p - phi[sel].astype(float)[:, None] * g / nrm**2
    return p, g / nrm


def sample(field: np.ndarray, origin: np.ndarray, pts: np.ndarray, h: float = H, cval: float | None = None):
    idx = ((pts - origin) / h).T
    if cval is None:
        return map_coordinates(field, idx, order=1, mode="nearest")
    return map_coordinates(field, idx, order=1, mode="constant", cval=cval)


# ---------------------------------------------------------------------------
# Rigid alignment
# ---------------------------------------------------------------------------


def kabsch(a: np.ndarray, b: np.ndarray):
    ma, mb = a.mean(axis=0), b.mean(axis=0)
    u, _, vt = np.linalg.svd((b - mb).T @ (a - ma))
    d = np.ones(3)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        d[2] = -1.0
    rot = u @ np.diag(d) @ vt
    return rot, mb - rot @ ma


def rigid_icp(src, src_n, dst, dst_n, iters: int = 40):
    """dst ~ R src + t (point-to-point, normal-compatible, trimmed)."""
    tree = cKDTree(dst)
    rot, t = np.eye(3), dst.mean(axis=0) - src.mean(axis=0)
    for _ in range(iters):
        x = src @ rot.T + t
        d, j = tree.query(x)
        ok = np.sum((src_n @ rot.T) * dst_n[j], axis=1) > 0.3
        if ok.sum() < 20:
            break
        keep = ok & (d <= np.quantile(d[ok], 0.9))
        r2, t2 = kabsch(src[keep], dst[j[keep]])
        change = np.linalg.norm(r2 - rot) + np.linalg.norm(t2 - t)
        rot, t = r2, t2
        if change < 1e-6:
            break
    return rot, t


# ---------------------------------------------------------------------------
# Mean shape
# ---------------------------------------------------------------------------


def mean_shape(subjects: list[dict], log=print):
    rng = np.random.default_rng(0)
    prepared = []
    for s in subjects:
        phi, ant, origin = fields_05(s["mask"], s["anterior"], s["spacing"])
        pts, nrm = level_points(phi, origin)
        pick = rng.choice(len(pts), size=min(3000, len(pts)), replace=False)
        prepared.append({"phi": phi.astype(np.float16), "ant": ant.astype(np.float16), "origin": origin, "pts": pts[pick], "nrm": nrm[pick], "vol": float((phi < 0).sum()) * H**3})
    vols = np.array([p["vol"] for p in prepared])
    ref = prepared[int(np.argsort(vols)[len(vols) // 2])]
    # Mean grid: the reference subject's grid padded by 6 mm.
    pad = int(round(6.0 / H))
    shape = tuple(int(x) + 2 * pad for x in ref["phi"].shape)
    origin_m = ref["origin"] - pad * H
    grid = origin_m + H * np.indices(shape, dtype=np.float32).reshape(3, -1).T
    target_p, target_n = level_points(ref["phi"].astype(np.float32), ref["origin"])
    mean_phi = mean_ant = None
    for rnd in range(2):
        acc_phi = np.zeros(len(grid))
        acc_ant = np.zeros(len(grid))
        resid = []
        for p in prepared:
            rot, t = rigid_icp(p["pts"], p["nrm"], target_p, target_n)
            resid.append(float(cKDTree(target_p).query(p["pts"] @ rot.T + t)[0].mean()))
            y = (grid - t) @ rot  # subject coordinates of the mean-grid points
            acc_phi += sample(p["phi"].astype(np.float32), p["origin"], y, cval=8.0)
            acc_ant += sample(p["ant"].astype(np.float32), p["origin"], y, cval=0.0)
        mean_phi = (acc_phi / len(prepared)).reshape(shape).astype(np.float32)
        mean_ant = (acc_ant / len(prepared)).reshape(shape).astype(np.float32)
        log(f"[template] round {rnd}: mean alignment residual {np.mean(resid):.3f} mm over {len(prepared)} subjects")
        target_p, target_n = level_points(mean_phi, origin_m)
    mask = largest_filled(mean_phi < 0)
    phi = gaussian_filter(sdf_from_mask(mask, H), 1.0).astype(np.float32)
    # Crop to the shape + 5 mm.
    idx = np.argwhere(phi < 0)
    lo = np.maximum(idx.min(axis=0) - 10, 0)
    hi = np.minimum(idx.max(axis=0) + 11, phi.shape)
    sl = tuple(slice(a, b) for a, b in zip(lo, hi))
    return phi[sl], mean_ant[sl], origin_m + H * lo


# ---------------------------------------------------------------------------
# Skeletal grid
# ---------------------------------------------------------------------------


def _unit(x):
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12)


def build_srep(phi: np.ndarray, origin: np.ndarray, head: np.ndarray):
    pts = origin + H * np.argwhere(phi < 0)
    c0 = pts.mean(axis=0)
    x = pts - c0
    evals, evecs = np.linalg.eigh(x.T @ x / len(x))
    e1 = evecs[:, 2]
    hp = sample(head, origin, pts)
    if np.dot(pts[hp < 0.5].mean(axis=0) - pts[hp >= 0.5].mean(axis=0), e1) < 0:
        e1 = -e1  # e1 runs from the head (u = 0) to the tail (u = 1)
    e2 = evecs[:, 1]
    e3 = np.cross(e1, e2)
    tau = x @ e1
    lo, hi = np.percentile(tau, [0.5, 99.5])
    centers, c2, c3, wts = [], [], [], []
    for b in np.arange(lo, hi, 1.0):
        sel = (tau >= b) & (tau < b + 1.0)
        if sel.sum() >= 20:
            centers.append(b + 0.5)
            c2.append(float((x[sel] @ e2).mean()))
            c3.append(float((x[sel] @ e3).mean()))
            wts.append(np.sqrt(sel.sum()))
    p2 = np.polyfit(centers, c2, 4, w=wts)
    p3 = np.polyfit(centers, c3, 4, w=wts)

    def curve(tt):
        tt = np.asarray(tt, dtype=float)
        return c0 + tt[:, None] * e1 + np.polyval(p2, tt)[:, None] * e2 + np.polyval(p3, tt)[:, None] * e3

    tf = np.linspace(lo, hi, 4001)
    cf = curve(tf)
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(cf, axis=0), axis=1))])
    u = np.linspace(0.0, 1.0, GRID_NU)
    tk = np.interp((U_LO + (U_HI - U_LO) * u) * arc[-1], arc, tf)
    ck = curve(tk)
    tan = _unit(curve(tk + 1e-3) - curve(tk - 1e-3))
    # Common width axis: dominant cross-sectional spread around the curve.
    resid = pts - curve(tau)
    rv, rvec = np.linalg.eigh(resid.T @ resid / len(resid))
    g = rvec[:, 2]
    w = _unit(g[None, :] - np.sum(g * tan, axis=1, keepdims=True) * tan)
    n = _unit(np.cross(tan, w))
    if np.mean(n[:, 2]) < 0:  # superior = +z in the MSD orientation
        w, n = -w, -n
    mids, halfs = np.full(GRID_NU, np.nan), np.full(GRID_NU, np.nan)
    for k in range(GRID_NU):
        d = pts - ck[k]
        sel = (np.abs(d @ tan[k]) < 0.6) & (np.linalg.norm(d, axis=1) < 15.0)
        if sel.sum() < 8:
            continue
        proj = d[sel] @ w[k]
        a, b = np.percentile(proj, [1.0, 99.0])
        mids[k], halfs[k] = 0.5 * (a + b), 0.5 * (b - a)
    good = np.isfinite(mids)
    mids = np.interp(np.arange(GRID_NU), np.flatnonzero(good), mids[good])
    halfs = np.interp(np.arange(GRID_NU), np.flatnonzero(good), halfs[good])
    mids = ndimage.gaussian_filter1d(mids, 1.5, mode="nearest")
    halfs = ndimage.gaussian_filter1d(halfs, 1.5, mode="nearest")
    v = np.linspace(-V_EXT, V_EXT, GRID_NV)
    q = (ck[:, None, :] + (mids[:, None] + v[None, :] * halfs[:, None])[..., None] * w[:, None, :]).reshape(-1, 3)
    nn = np.repeat(n, GRID_NV, axis=0)
    s = np.arange(-14.0, 14.0001, 0.05)
    vals = sample(phi, origin, (q[:, None, :] + s[None, :, None] * nn[:, None, :]).reshape(-1, 3), cval=10.0).reshape(len(q), len(s))
    i0 = int(np.argmin(np.abs(s)))
    skel, half_len = np.zeros_like(q), np.zeros(len(q))
    for r in range(len(q)):
        inside = vals[r] < 0
        if not inside.any():
            skel[r], half_len[r] = q[r], 0.25
            continue
        edges = np.flatnonzero(np.diff(np.concatenate([[0], inside.astype(np.int8), [0]])))
        runs = edges.reshape(-1, 2)  # [start, stop)
        dist = np.where((runs[:, 0] <= i0) & (runs[:, 1] > i0), 0, np.minimum(np.abs(runs[:, 0] - i0), np.abs(runs[:, 1] - 1 - i0)))
        a, b = runs[int(np.argmin(dist))]
        b = b - 1

        def cross(i, j):
            fi, fj = vals[r, i], vals[r, j]
            return s[i] + (s[j] - s[i]) * fi / (fi - fj) if fi != fj else s[i]

        s_lo = cross(a - 1, a) if a > 0 else s[a]
        s_hi = cross(b, b + 1) if b + 1 < len(s) else s[b]
        skel[r] = q[r] + 0.5 * (s_hi + s_lo) * nn[r]
        half_len[r] = max(0.5 * (s_hi - s_lo), 0.05)
    uu = np.repeat(u, GRID_NV)
    vv = np.tile(v, GRID_NU)
    sf = np.where(sample(head, origin, skel) >= 0.5, 0, np.where(uu <= 0.8, 1, 2)).astype(np.int64)
    return {
        "skeleton": skel,
        "sup_dir": nn.copy(),
        "inf_dir": -nn,
        "sup_len": half_len.copy(),
        "inf_len": half_len.copy(),
        "grid_shape": np.array([GRID_NU, GRID_NV], dtype=np.int64),
        "u": uu,
        "v": vv,
        "subfield_id": sf,
        "subfield_names": np.asarray(SUBFIELDS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", type=Path, default=HERE / "downloads/msd/Task04_Hippocampus.tar")
    parser.add_argument("--out-dir", type=Path, default=HERE)
    args = parser.parse_args()
    labels = msd.read_labels(args.archive)
    dev_ids, held_ids = msd.split_ids(labels)
    print(f"[template] {len(labels)} labelled cases: {len(dev_ids)} development, {len(held_ids)} held out")
    anat = msd.anatomy_arrays(labels, dev_ids)
    np.savez_compressed(args.out_dir / "hippo_real_anatomy.npz", **anat)
    subjects = msd.load_anatomy(args.out_dir / "hippo_real_anatomy.npz")
    phi, head, origin = mean_shape(subjects)
    tpl = build_srep(phi, origin, head)
    mask = phi < 0
    bits, _, shapes = msd.pack([mask])
    tpl.update(mask_bits=bits, mask_shape=shapes[0], origin=origin, spacing=np.float64(H))
    np.savez_compressed(args.out_dir / "hippo_real_template.npz", **tpl)
    ends = np.concatenate([tpl["skeleton"] + tpl["sup_dir"] * tpl["sup_len"][:, None], tpl["skeleton"] + tpl["inf_dir"] * tpl["inf_len"][:, None]])
    print(
        f"[template] mean shape volume {mask.sum() * H**3:.0f} mm^3; thickness "
        f"{np.percentile(2 * tpl['sup_len'], [5, 50, 95]).round(2).tolist()} mm; skeleton inside "
        f"{np.mean(sample(phi, origin, tpl['skeleton']) < 0):.3f}; |phi| at spoke ends "
        f"{np.abs(sample(phi, origin, ends)).mean():.3f} mm; subfields {np.bincount(tpl['subfield_id']).tolist()}"
    )


if __name__ == "__main__":
    main()
