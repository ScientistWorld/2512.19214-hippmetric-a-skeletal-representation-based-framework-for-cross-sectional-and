#!/bin/bash
# CPU job: reproduce the reference end to end from the committed inputs.
#   baseline + HippMetric on the development cohort, train/full scores,
#   hidden-test scores, then structural validation.
# (The hardening audit of variants and shortcuts is redteam/hardening/run_audit.sh.)
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
bash scripts/reproduce.sh
python validate.py --compare
