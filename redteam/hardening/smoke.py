#!/usr/bin/env python3
"""Fast smoke test of the real-anatomy cohort before the full audit (not part of the gym).

Generates a 3-subject development real cohort, runs the reference, the
boundary baseline and the nonrigid-follow-up variant on it, and scores them
with the development scorer. Fails loudly on any error.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval/train"))
import real_cohort as rc  # noqa: E402


def main() -> None:
    out = ROOT / "tmp/smoke"
    out.mkdir(parents=True, exist_ok=True)
    anatomy = rc.load_anatomy(ROOT / "data/hippo_real_anatomy.npz")[::7][:3]
    t0 = time.time()
    inputs, cohort = rc.make_cohort(anatomy, 12345, 4)
    print(f"[smoke] generated {len(inputs['subjects'])} scans in {time.time() - t0:.1f} s; shapes {inputs['mask_shapes'][:4].tolist()}")
    for i, subj in enumerate(cohort["objects"]):
        print(f"[smoke] subject {i}: bumps {len(subj.bumps)} depth {subj.depth:.2f} warp amps {[float(np.abs(v.amps).max()) if len(v.amps) else 0.0 for v in subj.visits]}")
    np.savez_compressed(out / "real_scans.npz", **inputs)
    with np.load(ROOT / "data/hippo_real_template.npz", allow_pickle=False) as z:
        tpl = {k: np.asarray(z[k]) for k in z.files}
    head = tpl["subfield_id"] == 0
    triv, _ = rc.score(rc.trivial_prediction(tpl, inputs), cohort, head)
    print("[smoke] trivial", json.dumps({k: round(v, 3) for k, v in triv.items()}))
    runs = {
        "hippmetric": ["python", "method/hippmetric.py"],
        "boundary_baseline": ["python", "baseline/boundary_model.py"],
        "hm_nonrigid_followups": ["python", "method/hippmetric.py", "--nonrigid-followups"],
    }
    for name, cmd in runs.items():
        t0 = time.time()
        path = out / f"{name}.npz"
        subprocess.run(cmd + ["--input", str(out / "real_scans.npz"), "--output", str(path)], check=True, cwd=ROOT)
        with np.load(path, allow_pickle=False) as z:
            pred = {k: np.asarray(z[k]) for k in ("skeleton", "sup_end", "inf_end")}
        metrics, _ = rc.score(pred, cohort, head)
        print(f"[smoke] {name} ({time.time() - t0:.1f} s)", json.dumps({k: round(v, 3) for k, v in metrics.items()}))


if __name__ == "__main__":
    main()
