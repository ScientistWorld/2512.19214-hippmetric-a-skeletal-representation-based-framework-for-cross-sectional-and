#!/bin/bash
# Hardening-audit predictor (installed into scripts/ only during the audit job).
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python "$ROOT/method/hippmetric.py" --input "$1" --output "$2" --independent-followups
