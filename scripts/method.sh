#!/bin/bash
# Run the reproduced HippMetric method on the visible development cohort.
# Usage: bash scripts/method.sh
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p checkpoints
bash scripts/predict_hippmetric.sh data/hippo_train.npz checkpoints/hippmetric_train.npz
