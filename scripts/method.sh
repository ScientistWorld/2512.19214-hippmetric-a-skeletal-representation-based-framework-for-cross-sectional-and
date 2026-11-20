#!/bin/bash
# Run the reproduced HippMetric method on both visible development cohorts.
# Usage: bash scripts/method.sh
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p checkpoints
[ -s checkpoints/real_train_scans.npz ] || python eval/train/evaluate.py --export-real-inputs checkpoints/real_train_scans.npz
bash scripts/predict_hippmetric.sh data/hippo_train.npz checkpoints/hippmetric_train.npz
bash scripts/predict_hippmetric.sh checkpoints/real_train_scans.npz checkpoints/hippmetric_real_train.npz
