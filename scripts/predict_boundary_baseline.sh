#!/bin/bash
# Predictor entry point for the boundary-driven baseline.
# Usage: bash scripts/predict_boundary_baseline.sh INPUT_SCANS_NPZ OUTPUT_NPZ
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python "$ROOT/baseline/boundary_model.py" --input "$1" --output "$2"
