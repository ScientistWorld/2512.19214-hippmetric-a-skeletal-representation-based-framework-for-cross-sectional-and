#!/bin/bash
# Run the boundary-driven baseline on the visible development cohort.
# Usage: bash scripts/baseline.sh
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p checkpoints
bash scripts/predict_boundary_baseline.sh data/hippo_train.npz checkpoints/boundary_baseline_train.npz
