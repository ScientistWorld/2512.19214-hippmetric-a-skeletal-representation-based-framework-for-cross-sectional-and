#!/bin/bash
# Standard evaluation entry point (self-contained in eval/, never imports method/).
# Runs every scripts/predict_<name>.sh predictor on the visible development
# cohort and writes scoring/scores.json (same scorer as scripts/evaluate_train.sh).
#
# To evaluate a new method, add scripts/predict_<name>.sh that takes
# INPUT_SCANS_NPZ OUTPUT_NPZ and writes subjects/skeleton/sup_end/inf_end
# (see eval/train/evaluate.py and data/hippo_io.py for the format).
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p scoring
python eval/train/evaluate.py --scores scoring/scores.json
