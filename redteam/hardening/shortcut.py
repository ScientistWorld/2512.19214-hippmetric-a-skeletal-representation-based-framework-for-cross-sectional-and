#!/usr/bin/env python3
"""Shortcut predictors used to audit the hardened gym (not part of the gym).

Each mode post-processes the reference HippMetric output for the same input
(cached by input hash) or bypasses it, then writes a predictor output file.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data"))
import hippo_io  # noqa: E402


def reference_output(inp: Path) -> dict:
    digest = hashlib.sha256(inp.read_bytes()).hexdigest()[:16]
    cache = ROOT / "tmp" / "hardening_cache" / f"hippmetric_{digest}.npz"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        partial = cache.with_name(cache.stem + f".{os.getpid()}.partial.npz")
        subprocess.run(["bash", str(ROOT / "scripts/predict_hippmetric.sh"), str(inp), str(partial)], check=True, cwd=ROOT)
        os.replace(partial, cache)
    with np.load(cache, allow_pickle=False) as z:
        return {k: np.array(z[k]) for k in z.files}


def save(out: Path, pred: dict) -> None:
    np.savez_compressed(out, **pred)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    mode = args.mode

    if mode == "crash":
        sys.exit(3)
    if mode == "missing_output":
        sys.exit(0)
    if mode == "template_only":
        scans = hippo_io.load_scans(args.input)
        tpl = hippo_io.load_template(ROOT / "data/hippo_template.npz")
        tc = tpl["origin"] + tpl["spacing"] * np.argwhere(tpl["mask"]).mean(axis=0)
        skel = tpl["skeleton"].astype(float)
        sup = skel + tpl["sup_dir"] * tpl["sup_len"][:, None]
        inf = skel + tpl["inf_dir"] * tpl["inf_len"][:, None]
        cents = np.array(
            [o + s * np.argwhere(m).mean(axis=0) for m, o, s in zip(scans["masks"], scans["origins"], scans["spacing"])]
        )
        shift = (cents - tc)[:, None, :]
        save(args.output, {"subjects": scans["subjects"], "skeleton": skel + shift, "sup_end": sup + shift, "inf_end": inf + shift})
        return

    pred = reference_output(args.input)
    subjects = pred["subjects"]
    if mode == "zero_thickness":
        pred["sup_end"] = pred["skeleton"].copy()
        pred["inf_end"] = pred["skeleton"].copy()
    elif mode == "nan_partial":
        pred["sup_end"][:, ::10] = np.nan
    elif mode == "huge_values":
        pred["sup_end"] = pred["sup_end"] * 1e30
    elif mode == "permute_points":
        for k in ("skeleton", "sup_end", "inf_end"):
            pred[k] = pred[k][:, ::-1].copy()
    elif mode == "snap_raw_surface":
        scans = hippo_io.load_scans(args.input)
        for i, (m, o, s) in enumerate(zip(scans["masks"], scans["origins"], scans["spacing"])):
            v, f = hippo_io.largest_component(*hippo_io.mask_to_mesh(m, o, float(s)))
            tree = cKDTree(v)
            pred["sup_end"][i] = v[tree.query(pred["sup_end"][i])[1]]
            pred["inf_end"][i] = v[tree.query(pred["inf_end"][i])[1]]
    elif mode == "template_thickness":
        # Keep the reference correspondence but report the template's spoke lengths,
        # scaled by the scan's size, instead of the measured lengths.
        scans = hippo_io.load_scans(args.input)
        tpl = hippo_io.load_template(ROOT / "data/hippo_template.npz")
        tvol = tpl["mask"].sum() * tpl["spacing"] ** 3
        for i, (m, s) in enumerate(zip(scans["masks"], scans["spacing"])):
            k = float((m.sum() * float(s) ** 3 / tvol) ** (1.0 / 3.0))
            sk = pred["skeleton"][i]
            for key, length in (("sup_end", tpl["sup_len"]), ("inf_end", tpl["inf_len"])):
                d = pred[key][i] - sk
                d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
                pred[key][i] = sk + d * (k * length)[:, None]
    elif mode == "label_drift":
        # The old generator moved longitudinal labels by 0.84 mm per timepoint along the
        # lamellar width direction without changing the anatomy; replay that rule.
        for i, (_, t) in enumerate(subjects):
            if t == 0:
                continue
            grid = pred["skeleton"][i].reshape(61, 9, 3)
            width_dir = np.gradient(grid, axis=1).reshape(-1, 3)
            width_dir /= np.maximum(np.linalg.norm(width_dir, axis=1, keepdims=True), 1e-12)
            for k in ("skeleton", "sup_end", "inf_end"):
                pred[k][i] = pred[k][i] + 0.84 * t * width_dir
    else:
        raise SystemExit(f"unknown mode {mode}")
    save(args.output, pred)


if __name__ == "__main__":
    main()
