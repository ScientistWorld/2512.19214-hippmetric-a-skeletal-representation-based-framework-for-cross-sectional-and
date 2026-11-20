#!/bin/bash
# Reproduce the reference results end-to-end (CPU only, no internet needed;
# all inputs are tracked in git, see scripts/download.sh for their sources).
#   1. train/full scores: every predictor (HippMetric, boundary baseline) on the
#      procedural and real-anatomy development cohorts (scripts/evaluate_train.sh,
#      scripts/evaluate.sh)
#   2. hidden-test scores (scripts/evaluate_test.sh)
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
for f in data/hippo_template.npz data/hippo_train.npz data/hippo_train_labels.npz data/hippo_real_anatomy.npz data/hippo_real_template.npz; do
  [ -s "$f" ] || { echo "missing tracked input $f (git checkout -- $f, or bash scripts/download.sh)" >&2; exit 1; }
done
bash scripts/evaluate_train.sh
bash scripts/evaluate.sh
bash scripts/evaluate_test.sh
