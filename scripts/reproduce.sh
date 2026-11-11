#!/bin/bash
# Reproduce the reference results end-to-end (CPU only, no internet needed).
#   1. baseline and HippMetric on the visible development cohort
#   2. train/full scores (scripts/evaluate_train.sh, scripts/evaluate.sh)
#   3. hidden-test scores (scripts/evaluate_test.sh)
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
bash scripts/download.sh
bash scripts/baseline.sh
bash scripts/method.sh
bash scripts/evaluate_train.sh
bash scripts/evaluate.sh
bash scripts/evaluate_test.sh
