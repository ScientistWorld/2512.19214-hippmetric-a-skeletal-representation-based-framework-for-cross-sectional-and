#!/usr/bin/env python3
"""Real-anatomy longitudinal cohort: generation and scoring (evaluation side).

Baseline anatomy is a real hippocampus: a manual MSD Task04 label (1 mm), turned
into a smooth signed distance field on a 0.5 mm grid. Each subject then gets
three follow-ups made here with hidden, known changes:

* tissue loss: the boundary is moved inwards along its true normal by an
  erosion field made of one or two anisotropic bumps centred on the head
  (MSD label 1, the paper's "anterior region"), growing over time, plus a
  small uniform thinning;
* a smooth random warp (sum of Gaussian displacement fields at several
  scales), drawn independently for every follow-up;
* a new scanner pose.

A method sees only 0.5 mm binary segmentations with boundary perturbations and
voxel label noise, in the same format as the procedural cohort.

Scoring follows each method's own baseline measurements forward through the
known change. Every baseline spoke endpoint is projected onto the true baseline
boundary; its true follow-up position is that point moved along the true
normal by the erosion at that point, then warped and posed. The true follow-up
skeletal point is the baseline skeletal point warped and posed (tissue is lost
at the boundary, not inside). From these:

* longitudinal correspondence error: distance between the submitted follow-up
  endpoint and the true follow-up position of the same anatomical point,
  inside the atrophic region (erosion >= 30 % of its peak), and outside it
  (< 5 %, the stable region);
* thickness-change error: submitted follow-up-minus-baseline thickness against
  the true change of the same spoke, inside the atrophic region;
* implied-surface RMS distance to the true clean boundary of every scan, and
  validity (endpoint within 1 mm of the true boundary, no fold-over).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates
from scipy.spatial import cKDTree

H = 0.5  # mm
GRID_SHAPE = (61, 9)
N_POINTS = GRID_SHAPE[0] * GRID_SHAPE[1]
REGION_REL = 0.3
STABLE_REL = 0.05
ADHERENCE_MM = 1.0
GLOBAL_THINNING = 0.03  # mm per timepoint, everywhere


# ---------------------------------------------------------------------------
# Anatomy
# ---------------------------------------------------------------------------


def _unpack(bits, shape):
    shape = tuple(int(s) for s in shape)
    return np.unpackbits(bits, count=int(np.prod(shape))).astype(bool).reshape(shape)


def load_anatomy(path) -> list[dict]:
    with np.load(path, allow_pickle=False) as z:
        a = {k: np.asarray(z[k]) for k in z.files}
    out = []
    for i, cid in enumerate(a["ids"]):
        shape = a["mask_shapes"][i]
        out.append(
            {
                "id": int(cid),
                "mask": _unpack(a["mask_bits"][a["mask_offsets"][i] : a["mask_offsets"][i + 1]], shape),
                "anterior": _unpack(a["anterior_bits"][a["anterior_offsets"][i] : a["anterior_offsets"][i + 1]], shape),
                "spacing": float(a["spacing"][i]),
            }
        )
    return out


def _sdf(mask: np.ndarray, h: float) -> np.ndarray:
    din = distance_transform_edt(mask) * h
    dout = distance_transform_edt(~mask) * h
    return np.where(mask, -(din - 0.5 * h), dout - 0.5 * h).astype(np.float32)


def _largest_filled(mask: np.ndarray) -> np.ndarray:
    mask = ndimage.binary_fill_holes(mask)
    lab, n = ndimage.label(mask)
    if n > 1:
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        mask = lab == int(np.argmax(sizes))
    return mask


def _unit(x):
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12)


class Anatomy:
    """Smooth signed distance field of one real hippocampus, centred on its centroid."""

    def __init__(self, mask1: np.ndarray, ant1: np.ndarray, sp1: float, pad_mm: float = 6.0):
        pad = int(np.ceil(pad_mm / sp1))
        m = np.pad(mask1.astype(bool), pad)
        a = np.pad(ant1.astype(bool), pad)
        sdf1 = gaussian_filter(_sdf(m, sp1), 0.7 / sp1)
        ratio = sp1 / H
        n05 = tuple(int(x) for x in (np.array(m.shape) - 1) * ratio + 1)
        idx = np.indices(n05, dtype=np.float32).reshape(3, -1) / ratio
        s05 = map_coordinates(sdf1, idx, order=1, mode="nearest").reshape(n05)
        m05 = _largest_filled(s05 < 0)
        self.phi = gaussian_filter(_sdf(m05, H), 1.0).astype(np.float32)
        self.ant = map_coordinates(a.astype(np.float32), idx, order=1, mode="constant", cval=0.0).reshape(n05)
        origin = np.full(3, -pad * sp1)
        inside = np.argwhere(self.phi < 0)
        self.origin = origin - (origin + H * inside.mean(axis=0))  # centroid at 0

    @property
    def grid_points(self) -> np.ndarray:
        return self.origin + H * np.indices(self.phi.shape, dtype=np.float32).reshape(3, -1).T

    def phi_at(self, y: np.ndarray) -> np.ndarray:
        return map_coordinates(self.phi, ((y - self.origin) / H).T, order=1, mode="nearest")

    def ant_at(self, y: np.ndarray) -> np.ndarray:
        return map_coordinates(self.ant, ((y - self.origin) / H).T, order=1, mode="constant", cval=0.0)


def _num_grad(fun, y: np.ndarray, eps: float = 0.2) -> np.ndarray:
    g = np.empty_like(y)
    for k in range(3):
        e = np.zeros(3)
        e[k] = eps
        g[:, k] = (fun(y + e) - fun(y - e)) / (2.0 * eps)
    return g


def _project(fun, y: np.ndarray, iters: int = 6, max_step: float = 3.0):
    """Newton projection onto the zero level set of ``fun``; returns points and unit gradients."""
    y = y.astype(float).copy()
    for _ in range(iters):
        f = fun(y)
        g = _num_grad(fun, y)
        gn2 = np.sum(g * g, axis=1)
        ok = gn2 > 0.01
        step = np.zeros_like(y)
        step[ok] = (f[ok] / gn2[ok])[:, None] * g[ok]
        nrm = np.linalg.norm(step, axis=1, keepdims=True)
        y = y - step * np.minimum(1.0, max_step / np.maximum(nrm, 1e-12))
    return y, _unit(_num_grad(fun, y))


# ---------------------------------------------------------------------------
# Hidden longitudinal change
# ---------------------------------------------------------------------------


def _rotvec(r: np.ndarray) -> np.ndarray:
    theta = float(np.linalg.norm(r))
    if theta < 1e-12:
        return np.eye(3)
    k = r / theta
    kx = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    return np.eye(3) + np.sin(theta) * kx + (1.0 - np.cos(theta)) * kx @ kx


def _random_rotation(rng) -> np.ndarray:
    q, r = np.linalg.qr(rng.standard_normal((3, 3)))
    q = q * np.sign(np.diag(r))
    if np.linalg.det(q) < 0:
        q[:, 0] = -q[:, 0]
    return q


class Visit:
    """Scan geometry of one timepoint: anatomy frame -> warp -> pose -> scanner frame."""

    def __init__(self, rot, trans, centers=None, amps=None, widths=None):
        self.rot, self.trans = rot, trans
        self.centers = np.zeros((0, 3)) if centers is None else centers
        self.amps = np.zeros((0, 3)) if amps is None else amps
        self.widths = np.zeros(0) if widths is None else widths

    def disp(self, y: np.ndarray) -> np.ndarray:
        if len(self.centers) == 0:
            return np.zeros_like(y)
        d2 = np.sum(y * y, axis=1)[:, None] + np.sum(self.centers**2, axis=1)[None, :] - 2.0 * y @ self.centers.T
        return np.exp(-np.maximum(d2, 0.0) / (2.0 * self.widths[None, :] ** 2)) @ self.amps

    def to_scan(self, y: np.ndarray) -> np.ndarray:
        return (y + self.disp(y)) @ self.rot.T + self.trans

    def to_anat(self, x: np.ndarray) -> np.ndarray:
        yp = (x - self.trans) @ self.rot
        y = yp.copy()
        for _ in range(12):
            y = yp - self.disp(y)
        return y


class Subject:
    def __init__(self, anat: Anatomy, rng: np.random.Generator, n_timepoints: int):
        self.anat = anat
        self.n_timepoints = n_timepoints
        # Erosion: one or two anisotropic bumps centred on head boundary points with enough tissue below.
        pts = anat.grid_points
        phi = anat.phi.ravel()
        band = np.abs(phi) < 0.25
        cand = pts[band & (anat.ant.ravel() > 0.5)]
        if len(cand) == 0:
            cand = pts[band]
        _, n = _project(anat.phi_at, cand, iters=1)
        deep = anat.phi_at(cand - 3.0 * n) < -1.2
        if deep.sum() > 10:
            cand = cand[deep]
        n_bumps = int(rng.integers(1, 3))
        self.bumps = []
        first = cand[int(rng.integers(len(cand)))]
        for b in range(n_bumps):
            c = first if b == 0 else cand[int(rng.integers(len(cand)))]
            q = _random_rotation(rng)
            sig = rng.uniform(3.0, 5.5, 3)
            prec = q @ np.diag(1.0 / sig**2) @ q.T
            weight = 1.0 if b == 0 else float(rng.uniform(0.4, 0.8))
            self.bumps.append((c, prec, weight))
        self.depth = float(rng.uniform(1.0, 1.7))
        self.gamma = float(rng.uniform(0.8, 1.3))
        # Poses and per-follow-up warps.
        inside = pts[phi < 0]
        lo, hi = inside.min(axis=0) - 4.0, inside.max(axis=0) + 4.0
        rot0 = _rotvec(np.clip(rng.normal(0.0, 0.15, 3), -0.3, 0.3))
        trans0 = np.array([25.0, -18.0, 12.0]) + rng.normal(0.0, 3.0, 3)
        self.visits = [Visit(rot0, trans0)]
        probe = inside[rng.choice(len(inside), size=min(1500, len(inside)), replace=False)]
        for _ in range(1, n_timepoints):
            rot = _rotvec(np.clip(rng.normal(0.0, 0.04, 3), -0.1, 0.1)) @ rot0
            trans = trans0 + rng.normal(0.0, 1.0, 3)
            k = int(rng.integers(8, 15))
            centers = rng.uniform(lo, hi, (k, 3))
            widths = rng.uniform(10.0, 18.0, k)
            amps = np.clip(rng.normal(0.0, 0.45, (k, 3)), -1.0, 1.0)
            visit = Visit(rot, trans, centers, amps, widths)
            jac = np.stack([_num_grad(lambda y, j=j: visit.disp(y)[:, j], probe) for j in range(3)], axis=1)
            worst = float(np.max(np.linalg.norm(jac, ord=2, axis=(1, 2))))
            if worst > 0.12:
                visit.amps = amps * (0.12 / worst)
            self.visits.append(visit)

    def profile(self, y: np.ndarray) -> np.ndarray:
        out = np.zeros(len(y))
        for c, prec, weight in self.bumps:
            d = y - c
            out += weight * np.exp(-0.5 * np.einsum("ni,ij,nj->n", d, prec, d))
        return out

    def erosion(self, y: np.ndarray, t: int) -> np.ndarray:
        if t == 0:
            return np.zeros(len(y))
        frac = (t / (self.n_timepoints - 1)) ** self.gamma
        return self.depth * frac * self.profile(y) + GLOBAL_THINNING * t

    def level(self, t: int):
        return lambda y: self.anat.phi_at(y) + self.erosion(y, t)

    def boundary(self, t: int) -> np.ndarray:
        """Dense sample of the true (noise-free) boundary at timepoint t, anatomy frame."""
        grid = self.anat.grid_points
        f = self.anat.phi.ravel() + self.erosion(grid, t)
        y, _ = _project(self.level(t), grid[np.abs(f) < 0.4].astype(float), iters=3)
        return y

    def eroded(self, p: np.ndarray, n: np.ndarray, t: int) -> np.ndarray:
        """True position at timepoint t of baseline boundary points p (unit outward normals n)."""
        if t == 0:
            return p.copy()
        level = self.level(t)
        s = np.zeros(len(p))
        for _ in range(10):
            s = np.clip(s + level(p - s[:, None] * n), 0.0, 4.0)
        return p - s[:, None] * n


def voxelise(subject: Subject, t: int, rng: np.random.Generator):
    """Noisy 0.5 mm segmentation of timepoint t in scanner coordinates, plus the clean boundary."""
    visit = subject.visits[t]
    bnd = visit.to_scan(subject.boundary(t))
    offset = rng.uniform(0.0, H, 3)
    lo = np.floor((bnd.min(axis=0) - 2.0 - offset) / H) * H + offset
    shape = tuple(int(s) for s in np.ceil((bnd.max(axis=0) + 2.0 - lo) / H).astype(int) + 1)
    pts = lo + H * np.indices(shape, dtype=np.float32).reshape(3, -1).T
    f = subject.level(t)(visit.to_anat(pts))
    near = np.abs(f) < 1.5
    centers = bnd[rng.choice(len(bnd), 40, replace=False)]
    amps = rng.normal(0.0, 0.2, 40)
    q = pts[near]
    eta = np.zeros(len(q))
    for c, a in zip(centers, amps):
        eta += a * np.exp(-np.sum((q - c) ** 2, axis=1) / (2.0 * 2.0**2))
    f[near] += eta
    lab = f < 0.0
    flip = (np.abs(f) < 0.35) & (rng.random(len(f)) < 0.03)
    lab[flip] = ~lab[flip]
    return lab.reshape(shape), lo, bnd.astype(np.float32)


def _pack(masks):
    packed = [np.packbits(m.ravel().astype(np.uint8)) for m in masks]
    offsets = np.concatenate([[0], np.cumsum([len(b) for b in packed])]).astype(np.int64)
    shapes = np.asarray([m.shape for m in masks], dtype=np.int64)
    return np.concatenate(packed).astype(np.uint8), offsets, shapes


def make_cohort(anatomy: list[dict], seed: int, n_timepoints: int = 4):
    """(method-visible inputs, evaluation-side cohort) for the given anatomies."""
    children = np.random.SeedSequence(seed).spawn(len(anatomy))
    subjects, masks, origins, bounds, objs = [], [], [], [], []
    for sid, (a, child) in enumerate(zip(anatomy, children)):
        rng = np.random.default_rng(child)
        subj = Subject(Anatomy(a["mask"], a["anterior"], a["spacing"]), rng, n_timepoints)
        objs.append(subj)
        for t in range(n_timepoints):
            mask, origin, bnd = voxelise(subj, t, rng)
            subjects.append([sid, t])
            masks.append(mask)
            origins.append(origin)
            bounds.append(bnd)
    bits, offsets, shapes = _pack(masks)
    subjects_arr = np.asarray(subjects, dtype=np.int64)
    inputs = {
        "cohort": np.asarray("real"),
        "subjects": subjects_arr,
        "mask_bits": bits,
        "mask_offsets": offsets,
        "mask_shapes": shapes,
        "origins": np.asarray(origins, dtype=np.float64),
        "spacing": np.full(len(subjects), H, dtype=np.float64),
    }
    cohort = {"subjects": subjects_arr, "objects": objs, "boundaries": bounds, "n_timepoints": n_timepoints}
    return inputs, cohort


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _upsample(grid: np.ndarray) -> np.ndarray:
    nu, nv = grid.shape[:2]
    a = np.empty((2 * nu - 1, nv, 3))
    a[0::2] = grid
    a[1::2] = 0.5 * (grid[1:] + grid[:-1])
    b = np.empty((2 * nu - 1, 2 * nv - 1, 3))
    b[:, 0::2] = a
    b[:, 1::2] = 0.5 * (a[:, 1:] + a[:, :-1])
    return b.reshape(-1, 3)


def _no_fold(ends: np.ndarray, skel: np.ndarray) -> np.ndarray:
    e = ends.reshape(GRID_SHAPE + (3,))
    s = skel.reshape(GRID_SHAPE + (3,))
    ok = np.ones(GRID_SHAPE, dtype=bool)
    du = np.sum((e[1:] - e[:-1]) * (s[1:] - s[:-1]), axis=-1) >= 0.0
    ok[1:] &= du
    ok[:-1] &= du
    dv = np.sum((e[:, 1:] - e[:, :-1]) * (s[:, 1:] - s[:, :-1]), axis=-1) >= 0.0
    ok[:, 1:] &= dv
    ok[:, :-1] &= dv
    return ok.ravel()


def _nanmean(parts) -> float:
    parts = [p for p in parts if len(p)]
    return float(np.concatenate(parts).mean()) if parts else float("nan")


def _nanq(parts, q) -> float:
    parts = [p for p in parts if len(p)]
    return float(np.quantile(np.concatenate(parts), q)) if parts else float("nan")


def score(pred: dict, cohort: dict, head_ids: np.ndarray | None = None):
    """Metrics of a prediction (skeleton / sup_end / inf_end, rows aligned with cohort['subjects'])."""
    subjects = cohort["subjects"]
    sk_all, su_all, in_all = pred["skeleton"], pred["sup_end"], pred["inf_end"]
    rows: dict[int, dict[int, int]] = {}
    for i, (sid, t) in enumerate(subjects.tolist()):
        rows.setdefault(int(sid), {})[int(t)] = i
    long_e, stable_e, change_e, nochange_e, head_mis = [], [], [], [], []
    q = np.zeros(len(subjects))
    p95 = np.zeros(len(subjects))
    hd = np.zeros(len(subjects))
    valid = np.zeros(len(subjects))
    per_subject = {}
    for i in range(len(subjects)):
        bnd = cohort["boundaries"][i].astype(float)
        tree = cKDTree(bnd)
        recon = np.concatenate([_upsample(su_all[i].reshape(GRID_SHAPE + (3,))), _upsample(in_all[i].reshape(GRID_SHAPE + (3,)))])
        d_rg = tree.query(recon)[0]
        d_gr = cKDTree(recon).query(bnd)[0]
        both = np.concatenate([d_rg, d_gr])
        q[i] = np.sqrt(np.mean(both**2))
        p95[i] = np.quantile(both, 0.95)
        hd[i] = max(d_rg.max(), d_gr.max())
        adherent = tree.query(np.concatenate([su_all[i], in_all[i]]))[0] <= ADHERENCE_MM
        unfolded = np.concatenate([_no_fold(su_all[i], sk_all[i]), _no_fold(in_all[i], sk_all[i])])
        valid[i] = np.mean(adherent & unfolded)
    for sid in sorted(rows):
        r = rows[sid]
        subj: Subject = cohort["objects"][sid]
        if 0 not in r:
            continue
        b = r[0]
        v0 = subj.visits[0]
        y_sk = v0.to_anat(sk_all[b])
        p_su, n_su = _project(subj.anat.phi_at, v0.to_anat(su_all[b]))
        p_in, n_in = _project(subj.anat.phi_at, v0.to_anat(in_all[b]))
        rel_su, rel_in = subj.profile(p_su), subj.profile(p_in)
        reg_su, reg_in = rel_su >= REGION_REL, rel_in >= REGION_REL
        st_su, st_in = rel_su < STABLE_REL, rel_in < STABLE_REL
        spoke_reg = reg_su | reg_in
        thick0 = np.linalg.norm(su_all[b] - sk_all[b], axis=1) + np.linalg.norm(in_all[b] - sk_all[b], axis=1)
        true0 = np.linalg.norm(p_su - y_sk, axis=1) + np.linalg.norm(p_in - y_sk, axis=1)
        if head_ids is not None:
            inside = subj.anat.phi_at(y_sk) < 0
            true_head = subj.anat.ant_at(y_sk) >= 0.5
            head_mis.append((true_head != head_ids)[inside].astype(float))
        s_long, s_stable, s_change = [], [], []
        for t in sorted(r):
            if t == 0:
                continue
            i = r[t]
            vt = subj.visits[t]
            a_su = vt.to_scan(subj.eroded(p_su, n_su, t))
            a_in = vt.to_scan(subj.eroded(p_in, n_in, t))
            s_t = vt.to_scan(y_sk)
            e_su = np.linalg.norm(su_all[i] - a_su, axis=1)
            e_in = np.linalg.norm(in_all[i] - a_in, axis=1)
            s_long += [e_su[reg_su], e_in[reg_in]]
            s_stable += [e_su[st_su], e_in[st_in]]
            d_true = np.linalg.norm(a_su - s_t, axis=1) + np.linalg.norm(a_in - s_t, axis=1) - true0
            thick_t = np.linalg.norm(su_all[i] - sk_all[i], axis=1) + np.linalg.norm(in_all[i] - sk_all[i], axis=1)
            s_change.append(np.abs((thick_t - thick0) - d_true)[spoke_reg])
            nochange_e.append(np.abs(d_true)[spoke_reg])
        long_e += s_long
        stable_e += s_stable
        change_e += s_change
        srows = list(r.values())
        per_subject[str(sid)] = {
            "real_longitudinal_correspondence_error_mm": _nanmean(s_long),
            "real_stable_correspondence_error_mm": _nanmean(s_stable),
            "real_thickness_change_error_mm": _nanmean(s_change),
            "real_surface_Q_mm": float(q[srows].mean()),
            "real_valid_spoke_fraction": float(valid[srows].mean()),
            "real_region_endpoints": int(reg_su.sum() + reg_in.sum()),
        }
    metrics = {
        "real_longitudinal_correspondence_error_mm": _nanmean(long_e),
        "real_longitudinal_p95_correspondence_error_mm": _nanq(long_e, 0.95),
        "real_stable_correspondence_error_mm": _nanmean(stable_e),
        "real_thickness_change_error_mm": _nanmean(change_e),
        "real_surface_Q_mm": float(q.mean()),
        "real_valid_spoke_fraction": float(valid.mean()),
        # diagnostics (not scored)
        "real_nochange_thickness_change_error_mm": _nanmean(nochange_e),
        "real_surface_p95_mm": float(p95.mean()),
        "real_surface_HD_mm": float(hd.mean()),
        "real_region_endpoints": int(sum(len(x) for x in long_e)),
        "real_head_label_mismatch": _nanmean(head_mis) if head_ids is not None else float("nan"),
    }
    return metrics, per_subject


def scan_centroids(inputs: dict) -> np.ndarray:
    out = []
    for i in range(len(inputs["subjects"])):
        bits = inputs["mask_bits"][inputs["mask_offsets"][i] : inputs["mask_offsets"][i + 1]]
        idx = np.argwhere(_unpack(bits, inputs["mask_shapes"][i]))
        out.append(np.asarray(inputs["origins"][i], dtype=float) + float(inputs["spacing"][i]) * idx.mean(axis=0))
    return np.asarray(out)


def trivial_prediction(template: dict, inputs: dict) -> dict:
    """Template s-rep placed at each scan's segmentation centroid (no fitting)."""
    mask = _unpack(template["mask_bits"], template["mask_shape"])
    tpl_c = np.asarray(template["origin"], dtype=float) + float(template["spacing"]) * np.argwhere(mask).mean(axis=0)
    skel = template["skeleton"].astype(float)
    sup = skel + template["sup_dir"] * template["sup_len"][:, None]
    inf = skel + template["inf_dir"] * template["inf_len"][:, None]
    shift = (scan_centroids(inputs) - tpl_c)[:, None, :]
    return {"skeleton": skel[None] + shift, "sup_end": sup[None] + shift, "inf_end": inf[None] + shift}
