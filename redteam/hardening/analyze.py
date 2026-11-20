#!/usr/bin/env python3
"""Summarise the hardening audit: normalised score deltas and paired noise.

Delta follows the gym's ranking rule: for every scored metric (non-zero
coefficient in scoring/reference.json), weight[e] * |coef| * improvement over
the reference (taken in the metric's better direction) / population SD of the
metric across the audited attempts. Two populations are reported: successful
attempts only, and all attempts (failed attempts carry worst values).
Paired noise: per-subject differences against the reference on the same hidden
subjects, standard error = sd / sqrt(n).
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REFERENCE = "hippmetric"


def delta_table(scores: dict, coeff: dict, population: list[str]) -> dict:
    exps = scores["experiments"]
    sds = {}
    for exp, ed in coeff.items():
        for met, md in ed["metrics"].items():
            vals = [exps[exp]["results"][m][met] for m in population if met in exps[exp]["results"].get(m, {})]
            sds[(exp, met)] = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    out = {}
    for method in sorted(exps[next(iter(exps))]["results"]):
        total = 0.0
        for exp, ed in coeff.items():
            ref = exps[exp]["results"][REFERENCE]
            val = exps[exp]["results"][method]
            for met, md in ed["metrics"].items():
                if not md["coefficient"] or met not in val:
                    continue
                imp = (val[met] - ref[met]) * (1.0 if md["higher_is_better"] else -1.0)
                sd = sds[(exp, met)]
                if sd > 0:
                    total += ed["weight"] * abs(md["coefficient"]) * imp / sd
        out[method] = total
    return out


PAIRED = {
    "procedural": ("thickness_mae_mm", "longitudinal_thickness_change_error_mm", "cross_sectional_correspondence_error_mm", "longitudinal_correspondence_error_mm", "surface_Q_mm", "surface_HD_mm"),
    "real": ("real_longitudinal_correspondence_error_mm", "real_stable_correspondence_error_mm", "real_thickness_change_error_mm", "real_surface_Q_mm", "real_valid_spoke_fraction"),
}


def _ok(x) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def paired(diag: dict, method: str) -> dict:
    """Per-subject paired differences (method - reference) on the same subjects."""
    res = {}
    if method not in diag or REFERENCE not in diag:
        return res
    for cohort, mets in PAIRED.items():
        ref, alt = diag[REFERENCE].get(cohort, {}), diag[method].get(cohort, {})
        for met in mets:
            diffs = [alt[s][met] - ref[s][met] for s in ref if s in alt and _ok(ref[s].get(met)) and _ok(alt[s].get(met))]
            if len(diffs) > 1:
                mean = statistics.fmean(diffs)
                se = statistics.stdev(diffs) / math.sqrt(len(diffs))
                res[met] = {"mean_diff": mean, "se": se, "z": mean / se if se > 0 else float("inf"), "n": len(diffs)}
    return res


def main() -> None:
    results = HERE / "results"
    ref_json = json.loads((ROOT / "scoring/reference.json").read_text())["experiments"]
    coeff = {e: {"weight": d["weight"], "metrics": d["metrics"]} for e, d in ref_json.items()}
    summary = {}
    for split in ("train", "test"):
        path = results / f"scores_{split}_all.json"
        if not path.exists():
            continue
        scores = json.loads(path.read_text())
        status = scores["_methods"]
        ok = [m for m, s in status.items() if s["status"] == "ok"]
        summary[split] = {
            "status": {m: s["status"] + ("" if not s["reason"] else f": {s['reason']}") for m, s in status.items()},
            "delta_successful_population": delta_table(scores, coeff, ok),
            "delta_all_population": delta_table(scores, coeff, list(status)),
            "metrics": {m: {met: v for e in scores["experiments"].values() for met, v in e["results"][m].items()} for m in status},
            "failure_thresholds": scores.get("_failure_thresholds"),
        }
        diag_path = results / f"diagnostics_{split}.json"
        if diag_path.exists():
            diag = json.loads(diag_path.read_text())
            summary[split]["paired_vs_reference"] = {m: paired(diag, m) for m in diag if m != REFERENCE}
    (results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for split, block in summary.items():
        print(f"== {split} ==")
        for m, d in sorted(block["delta_successful_population"].items(), key=lambda kv: -kv[1]):
            mt = block["metrics"][m]
            print(
                f"{m:26s} d_ok={d:+8.3f} d_all={block['delta_all_population'][m]:+8.3f} "
                f"thk={mt['thickness_mae_mm']:.3f} dthk={mt['longitudinal_thickness_change_error_mm']:.3f} "
                f"cross={mt['cross_sectional_correspondence_error_mm']:.3f} long={mt['longitudinal_correspondence_error_mm']:.3f} "
                f"Q={mt['surface_Q_mm']:.3f} HD={mt['surface_HD_mm']:.3f} val={mt['valid_spoke_fraction']:.3f} | "
                f"R:long={mt['real_longitudinal_correspondence_error_mm']:.3f} p95={mt['real_longitudinal_p95_correspondence_error_mm']:.3f} "
                f"stab={mt['real_stable_correspondence_error_mm']:.3f} dthk={mt['real_thickness_change_error_mm']:.3f} "
                f"Q={mt['real_surface_Q_mm']:.3f} val={mt['real_valid_spoke_fraction']:.3f}  {block['status'][m]}"
            )
        for m, pr in sorted(block.get("paired_vs_reference", {}).items()):
            if pr:
                print(f"   paired {m:24s} " + " ".join(f"{k.replace('_error_mm', '').replace('_mm', '')}={v['mean_diff']:+.3f}+-{v['se']:.3f}" for k, v in pr.items()))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
