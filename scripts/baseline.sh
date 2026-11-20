#!/bin/bash
# Run the boundary-driven baseline on both visible development cohorts.
# Usage: bash scripts/baseline.sh
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p checkpoints
[ -s checkpoints/real_train_scans.npz ] || python eval/train/evaluate.py --export-real-inputs checkpoints/real_train_scans.npz
bash scripts/predict_boundary_baseline.sh data/hippo_train.npz checkpoints/boundary_baseline_train.npz
bash scripts/predict_boundary_baseline.sh checkpoints/real_train_scans.npz checkpoints/boundary_baseline_real_train.npz
