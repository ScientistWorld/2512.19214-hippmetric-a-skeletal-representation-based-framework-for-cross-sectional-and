#!/usr/bin/env python3
"""Train-split scorer: runs every predictor on the visible development cohort.

A predictor is any ``scripts/predict_<name>.sh`` taking ``INPUT_NPZ OUTPUT_NPZ``.
It reads scans in the format documented in ``data/hippo_io.py`` and writes, per
scan, the skeletal point and superior/inferior spoke endpoints at every template
skeletal point:

    subjects (N, 2), skeleton (N, 549, 3), sup_end (N, 549, 3), inf_end (N, 549, 3)

Every scored number is recomputed here from those raw coordinates. Nothing a
predictor reports about itself is read. A predictor that crashes, writes
malformed / non-finite / absurd coordinates, leaves fewer than half of its
spokes valid, or does worse than a trivial evaluator-side predictor on any
task receives the worst value of every scored metric in every experiment.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
GRID_SHAPE = (61, 9)
N_POINTS = GRID_SHAPE[0] * GRID_SHAPE[1]
ADHERENCE_MM = 1.0
MIN_VALIDITY = 0.5
MAX_ABS_COORD = 1.0e4
EXPERIMENTS = {
    "subfield_thickness_accuracy": (
        "thickness_mae_mm",
        "thickness_p95_abs_error_mm",
        "subfield_mean_thickness_error_mm",
        "valid_spoke_fraction",
    ),
    "correspondence_stability": (
        "cross_sectional_correspondence_error_mm",
        "cross_sectional_p95_correspondence_error_mm",
        "longitudinal_correspondence_error_mm",
        "longitudinal_p95_correspondence_error_mm",
    ),
    "surface_robustness": ("surface_Q_mm", "surface_HD_mm", "surface_p95_mm"),
}
WORST = {
    "thickness_mae_mm": 5.0,
    "thickness_p95_abs_error_mm": 10.0,
    "subfield_mean_thickness_error_mm": 5.0,
    "valid_spoke_fraction": 0.0,
    "cross_sectional_correspondence_error_mm": 20.0,
    "cross_sectional_p95_correspondence_error_mm": 30.0,
    "longitudinal_correspondence_error_mm": 20.0,
    "longitudinal_p95_correspondence_error_mm": 30.0,
    "surface_Q_mm": 10.0,
    "surface_HD_mm": 30.0,
    "surface_p95_mm": 15.0,
}
GATED = {
    "thickness_mae_mm": "trivial_thickness_mae_mm",
    "cross_sectional_correspondence_error_mm": "trivial_cross_sectional_error_mm",
    "longitudinal_correspondence_error_mm": "trivial_longitudinal_error_mm",
    "surface_Q_mm": "trivial_surface_Q_mm",
}


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def _unpack(bits, shape):
    shape = tuple(int(s) for s in shape)
    return np.unpackbits(bits, count=int(np.prod(shape))).astype(bool).reshape(shape)


def _mask_centroid(mask, origin, spacing):
    idx = np.argwhere(mask)
    if len(idx) == 0:
        return np.asarray(origin, dtype=float)
    return np.asarray(origin, dtype=float) + float(spacing) * idx.mean(axis=0)


def scan_centroids(inputs: dict) -> np.ndarray:
    out = []
    for i in range(len(inputs["subjects"])):
        bits = inputs["mask_bits"][inputs["mask_offsets"][i] : inputs["mask_offsets"][i + 1]]
        out.append(_mask_centroid(_unpack(bits, inputs["mask_shapes"][i]), inputs["origins"][i], inputs["spacing"][i]))
    return np.asarray(out)


def trivial_prediction(template: dict, centroids: np.ndarray) -> dict:
    """Template s-rep placed at each scan's segmentation centroid (no fitting)."""
    tpl_c = _mask_centroid(_unpack(template["mask_bits"], template["mask_shape"]), template["origin"], template["spacing"])
    skel = template["skeleton"].astype(float)
    sup = skel + template["sup_dir"] * template["sup_len"][:, None]
    inf = skel + template["inf_dir"] * template["inf_len"][:, None]
    shift = (centroids - tpl_c)[:, None, :]
    return {"skeleton": skel[None] + shift, "sup_end": sup[None] + shift, "inf_end": inf[None] + shift}


# ---------------------------------------------------------------------------
# Predictors
# ---------------------------------------------------------------------------


def discover_predictors() -> dict[str, Path]:
    found = {}
    for path in sorted((ROOT / "scripts").glob("predict_*.sh")):
        found[path.stem[len("predict_") :]] = path
    return found


def run_predictor(script: Path, input_path: Path, output_path: Path, log_path: Path, timeout: float) -> str | None:
    """Run one predictor; return a failure reason or None."""
    if output_path.exists():
        output_path.unlink()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_path, "w") as log:
            proc = subprocess.run(
                ["bash", str(script), str(input_path), str(output_path)],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        return f"timed out after {timeout:.0f} s"
    if proc.returncode != 0:
        return f"exit code {proc.returncode}"
    if not output_path.is_file():
        return "no output file written"
    return None


def load_prediction(path: Path, subjects: np.ndarray) -> dict:
    with np.load(path, allow_pickle=False) as z:
        missing = [k for k in ("subjects", "skeleton", "sup_end", "inf_end") if k not in z.files]
        if missing:
            raise ValueError(f"missing arrays: {', '.join(missing)}")
        out_subjects = np.asarray(z["subjects"])
        arrays = {k: np.asarray(z[k]) for k in ("skeleton", "sup_end", "inf_end")}
    if out_subjects.shape != subjects.shape:
        raise ValueError(f"subjects has shape {out_subjects.shape}, expected {subjects.shape}")
    position = {}
    for idx, row in enumerate(out_subjects.astype(np.int64).tolist()):
        if tuple(row) in position:
            raise ValueError(f"duplicate scan {tuple(row)}")
        position[tuple(row)] = idx
    try:
        order = np.asarray([position[tuple(r)] for r in subjects.astype(np.int64).tolist()], dtype=np.int64)
    except KeyError as exc:
        raise ValueError(f"scan {exc} missing from output") from exc
    pred = {}
    for key, arr in arrays.items():
        if arr.shape != (len(subjects), N_POINTS, 3):
            raise ValueError(f"{key} has shape {arr.shape}, expected {(len(subjects), N_POINTS, 3)}")
        if not np.issubdtype(arr.dtype, np.number):
            raise ValueError(f"{key} is not numeric")
        arr = arr[order].astype(np.float64)
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"{key} contains non-finite values")
        if np.abs(arr).max() > MAX_ABS_COORD:
            raise ValueError(f"{key} contains impossible coordinates (> {MAX_ABS_COORD:g} mm)")
        pred[key] = arr
    return pred


# ---------------------------------------------------------------------------
# Metrics
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
    # A spoke pair crosses when the endpoint order reverses the skeletal order.
    du = np.sum((e[1:] - e[:-1]) * (s[1:] - s[:-1]), axis=-1) >= 0.0
    ok[1:] &= du
    ok[:-1] &= du
    dv = np.sum((e[:, 1:] - e[:, :-1]) * (s[:, 1:] - s[:, :-1]), axis=-1) >= 0.0
    ok[:, 1:] &= dv
    ok[:, :-1] &= dv
    return ok.ravel()


def compute_metrics(pred: dict, labels: dict, subjects: np.ndarray, subfield_id: np.ndarray):
    sk, su, inf = pred["skeleton"], pred["sup_end"], pred["inf_end"]
    gt_t = labels["thickness_gt"].astype(float)
    thick = np.linalg.norm(su - sk, axis=2) + np.linalg.norm(inf - sk, axis=2)
    abs_err = np.abs(thick - gt_t)
    sf_err = np.stack(
        [np.abs(thick[:, subfield_id == k].mean(axis=1) - gt_t[:, subfield_id == k].mean(axis=1)) for k in np.unique(subfield_id)],
        axis=1,
    )
    e_sup = np.linalg.norm(su - labels["sup_gt"].astype(float), axis=2)
    e_inf = np.linalg.norm(inf - labels["inf_gt"].astype(float), axis=2)
    base = subjects[:, 1] == 0
    fol = ~base
    region = labels["atrophy_region"].astype(bool)
    cross_err = np.concatenate([e_sup[base], e_inf[base]], axis=1)
    long_err = np.concatenate([e_sup[fol][region[fol]], e_inf[fol][region[fol]]])
    n = len(subjects)
    q, hd, p95, valid, long_scan = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n), np.full(n, np.nan)
    for i in range(n):
        gt_surface = labels["surface_gt"][i].astype(float)
        gtree = cKDTree(gt_surface)
        recon = np.concatenate([_upsample(su[i].reshape(GRID_SHAPE + (3,))), _upsample(inf[i].reshape(GRID_SHAPE + (3,)))])
        d_rg = gtree.query(recon)[0]
        d_gr = cKDTree(recon).query(gt_surface)[0]
        both = np.concatenate([d_rg, d_gr])
        q[i] = np.sqrt(np.mean(both**2))
        hd[i] = max(d_rg.max(), d_gr.max())
        p95[i] = np.quantile(both, 0.95)
        adherent = gtree.query(np.concatenate([su[i], inf[i]]))[0] <= ADHERENCE_MM
        unfolded = np.concatenate([_no_fold(su[i], sk[i]), _no_fold(inf[i], sk[i])])
        valid[i] = np.mean(adherent & unfolded)
        if fol[i] and region[i].any():
            long_scan[i] = np.concatenate([e_sup[i][region[i]], e_inf[i][region[i]]]).mean()
    metrics = {
        "thickness_mae_mm": float(abs_err.mean()),
        "thickness_p95_abs_error_mm": float(np.quantile(abs_err, 0.95)),
        "subfield_mean_thickness_error_mm": float(sf_err.mean()),
        "valid_spoke_fraction": float(valid.mean()),
        "cross_sectional_correspondence_error_mm": float(cross_err.mean()),
        "cross_sectional_p95_correspondence_error_mm": float(np.quantile(cross_err, 0.95)),
        "longitudinal_correspondence_error_mm": float(long_err.mean()),
        "longitudinal_p95_correspondence_error_mm": float(np.quantile(long_err, 0.95)),
        "surface_Q_mm": float(q.mean()),
        "surface_HD_mm": float(hd.mean()),
        "surface_p95_mm": float(p95.mean()),
    }
    per_subject = {}
    for sid in np.unique(subjects[:, 0]):
        rows = subjects[:, 0] == sid
        per_subject[str(int(sid))] = {
            "thickness_mae_mm": float(abs_err[rows].mean()),
            "cross_sectional_correspondence_error_mm": float(cross_err[rows[base]].mean()) if np.any(rows & base) else None,
            "longitudinal_correspondence_error_mm": float(np.nanmean(long_scan[rows & fol])) if np.any(np.isfinite(long_scan[rows & fol])) else None,
            "surface_Q_mm": float(q[rows].mean()),
            "surface_HD_mm": float(hd[rows].mean()),
            "valid_spoke_fraction": float(valid[rows].mean()),
        }
    return metrics, per_subject


def failure_thresholds(template, centroids, labels, subjects, subfield_id) -> dict:
    trivial, _ = compute_metrics(trivial_prediction(template, centroids), labels, subjects, subfield_id)
    gt_t = labels["thickness_gt"].astype(float)
    constant_mae = float(np.abs(gt_t - gt_t.mean(axis=1, keepdims=True)).mean())
    return {
        "trivial_thickness_mae_mm": constant_mae,
        "trivial_cross_sectional_error_mm": trivial["cross_sectional_correspondence_error_mm"],
        "trivial_longitudinal_error_mm": trivial["longitudinal_correspondence_error_mm"],
        "trivial_surface_Q_mm": trivial["surface_Q_mm"],
        "min_valid_spoke_fraction": MIN_VALIDITY,
    }


def gate(metrics: dict, thresholds: dict) -> str | None:
    reasons = []
    if metrics["valid_spoke_fraction"] < MIN_VALIDITY:
        reasons.append(f"valid_spoke_fraction {metrics['valid_spoke_fraction']:.3f} < {MIN_VALIDITY}")
    for metric, key in GATED.items():
        if not metrics[metric] < thresholds[key]:
            reasons.append(f"{metric} {metrics[metric]:.3f} not better than trivial {thresholds[key]:.3f}")
    return "; ".join(reasons) or None


def finalize(metrics: dict | None) -> dict:
    if metrics is None:
        return dict(WORST)
    out = {}
    for name, worst in WORST.items():
        value = float(metrics[name])
        if not np.isfinite(value):
            out[name] = worst
        else:
            out[name] = max(value, worst) if name == "valid_spoke_fraction" else min(value, worst)
    return out


def write_scores(path: Path, slice_name: str, blocks: dict, status: dict, thresholds: dict) -> dict:
    scores = {
        "_slice": slice_name,
        "_methods": status,
        "_failure_thresholds": thresholds,
        "experiments": {
            exp: {"results": {m: {k: blocks[m][k] for k in names} for m, _ in sorted(blocks.items())}}
            for exp, names in EXPERIMENTS.items()
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(scores, indent=2) + "\n")
    os.replace(tmp, path)
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inputs", type=Path, default=ROOT / "data/hippo_train.npz")
    parser.add_argument("--labels", type=Path, default=ROOT / "data/hippo_train_labels.npz")
    parser.add_argument("--template", type=Path, default=ROOT / "data/hippo_template.npz")
    parser.add_argument("--outputs-dir", type=Path, default=ROOT / "checkpoints/train")
    parser.add_argument("--scores", type=Path, default=ROOT / "scoring/scores_train.json")
    parser.add_argument("--timeout", type=float, default=3600.0)
    args = parser.parse_args()

    with np.load(args.inputs, allow_pickle=False) as z:
        inputs = {k: np.asarray(z[k]) for k in z.files}
    with np.load(args.labels, allow_pickle=False) as z:
        labels = {k: np.asarray(z[k]) for k in z.files}
    with np.load(args.template, allow_pickle=False) as z:
        template = {k: np.asarray(z[k]) for k in z.files}
    subjects = inputs["subjects"].astype(np.int64)
    if not np.array_equal(subjects, labels["subjects"]):
        raise ValueError("inputs and labels describe different scans")
    subfield_id = template["subfield_id"].astype(np.int64)
    thresholds = failure_thresholds(template, scan_centroids(inputs), labels, subjects, subfield_id)

    predictors = discover_predictors()
    if not predictors:
        raise FileNotFoundError("no scripts/predict_*.sh predictors found")
    blocks, status, diagnostics = {}, {}, {}
    for name, script in predictors.items():
        out_path = args.outputs_dir / f"{name}.npz"
        reason = run_predictor(script, args.inputs, out_path, args.outputs_dir / "logs" / f"{name}.log", args.timeout)
        metrics = None
        if reason is None:
            try:
                metrics, diagnostics[name] = compute_metrics(load_prediction(out_path, subjects), labels, subjects, subfield_id)
                reason = gate(metrics, thresholds)
            except Exception as exc:  # malformed output counts as a failed run
                reason = f"invalid output: {exc}"
        status[name] = {"status": "failed" if reason else "ok", "reason": reason, "raw": metrics}
        blocks[name] = finalize(None if reason else metrics)
        print(f"[train] {name}: {'FAILED (' + reason + ')' if reason else 'ok'}", file=sys.stderr)
    scores = write_scores(args.scores, "train", blocks, status, thresholds)
    diag_path = os.environ.get("EVAL_DIAGNOSTICS")
    if diag_path:
        Path(diag_path).write_text(json.dumps(diagnostics, indent=2) + "\n")
    print(json.dumps(scores["experiments"], indent=2))


if __name__ == "__main__":
    main()
