#!/bin/bash
# CPU job: reproduce the reference end to end from the committed inputs.
#   HippMetric and the boundary baseline on both development cohorts
#   (procedural + real anatomy), train/full scores, hidden-test scores, then
#   structural validation.
# (The hardening audit of variants and shortcuts is redteam/hardening/job.sh.)
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
bash scripts/reproduce.sh
python validate.py --compare
