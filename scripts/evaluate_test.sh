#!/bin/bash
# Held-out test-slice evaluation for precomputed method outputs.
#
# This mirrors scripts/evaluate_train.sh but uses eval/test/ and writes
# scoring/scores_test.json. When train scores exist, the same method entries
# are scored on the held-out slice.

set -e

cd /home/user

mkdir -p scoring

python eval/test/evaluate.py \
  --dataset data/synthetic_hippocampus.npz \
  --labels data/synthetic_hippocampus_labels.npz \
  --outputs-dir "${OUTPUTS_DIR:-checkpoints}" \
  --methods-from scoring/scores_train.json \
  --scores scoring/scores_test.json
