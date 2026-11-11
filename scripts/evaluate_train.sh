#!/bin/bash
# Train-split evaluation: runs every scripts/predict_<name>.sh on the visible
# development cohort (data/hippo_train.npz) and scores it against
# data/hippo_train_labels.npz. Writes scoring/scores_train.json.
# No arguments; every predictor on disk is scored.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p scoring
python eval/train/evaluate.py --scores scoring/scores_train.json
