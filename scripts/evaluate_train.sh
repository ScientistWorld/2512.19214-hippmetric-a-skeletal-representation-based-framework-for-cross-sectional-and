#!/bin/bash
# Visible train-slice evaluation for precomputed method outputs.
#
# Positional arguments are accepted for compatibility with scripts/evaluate.sh,
# but scoring is intentionally method-agnostic: every checkpoints/*_outputs.npz
# artifact is evaluated and written under its filename-derived method name.

set -e

cd /home/user

mkdir -p scoring

python eval/train/evaluate.py \
  --dataset data/synthetic_hippocampus.npz \
  --labels data/synthetic_hippocampus_labels.npz \
  --outputs-dir "${OUTPUTS_DIR:-checkpoints}" \
  --scores scoring/scores_train.json
