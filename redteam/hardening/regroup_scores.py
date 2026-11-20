#!/usr/bin/env python3
"""Rescore saved score files after the experiment regrouping (no predictor reruns).

The final evaluator files the real-anatomy metrics under the three existing
experiments instead of a separate one. Metric values are unchanged (the
evaluator is deterministic and only its EXPERIMENTS mapping changed), so a saved
score file is regrouped by moving each method's metric values to the
experiment that now owns them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ref = json.loads((ROOT / "scoring/reference.json").read_text())["experiments"]
MAPPING = {exp: list(d["metrics"]) for exp, d in ref.items()}

for name in sys.argv[1:]:
    path = Path(name)
    scores = json.loads(path.read_text())
    values: dict[str, dict] = {}
    for block in scores["experiments"].values():
        for method, mets in block["results"].items():
            values.setdefault(method, {}).update(mets)
    scores["experiments"] = {
        exp: {"results": {m: {k: values[m][k] for k in names} for m in sorted(values)}} for exp, names in MAPPING.items()
    }
    path.write_text(json.dumps(scores, indent=2) + "\n")
    print(f"regrouped {path}")
