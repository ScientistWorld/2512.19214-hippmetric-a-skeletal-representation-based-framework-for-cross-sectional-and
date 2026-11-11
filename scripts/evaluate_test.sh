#!/bin/bash
# Hidden test evaluation: eval/test/ generates the held-out cohort, runs every
# scripts/predict_<name>.sh on its segmentations only, and scores the outputs.
# Writes scoring/scores_test.json. No arguments; every predictor on disk is scored.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p scoring
python eval/test/evaluate.py --scores scoring/scores_test.json
