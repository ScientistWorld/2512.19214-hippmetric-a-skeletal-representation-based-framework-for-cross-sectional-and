#!/bin/bash
# Predictor entry point for the reproduced HippMetric method.
# Usage: bash scripts/predict_hippmetric.sh INPUT_SCANS_NPZ OUTPUT_NPZ
# The evaluators discover every scripts/predict_<name>.sh and score it as <name>.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python "$ROOT/method/hippmetric.py" --input "$1" --output "$2"
