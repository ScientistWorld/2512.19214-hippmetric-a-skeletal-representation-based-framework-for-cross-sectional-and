#!/bin/bash
# Hardening audit (not part of the gym): run the reference, baseline, method
# variants and shortcut predictors through the train and hidden-test
# evaluators, then summarise normalised deltas and paired noise.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
RES=redteam/hardening/results
mkdir -p "$RES"
{ echo "cpus: $(nproc)"; python -c "import numpy, scipy, sys; print(sys.version); print('numpy', numpy.__version__, 'scipy', scipy.__version__)"; } > "$RES/env.txt" 2>&1
start=$(date +%s)
stamp() { echo "[$(( $(date +%s) - start ))s] $*" | tee -a "$RES/timeline.txt"; }

stamp "audit: install variant and shortcut predictors"
cp redteam/hardening/predictors/predict_*.sh scripts/
rm -rf tmp/hardening_cache checkpoints/audit_train
stamp "audit: train split, all predictors"
EVAL_DIAGNOSTICS="$RES/diagnostics_train.json" python eval/train/evaluate.py \
  --outputs-dir checkpoints/audit_train --scores "$RES/scores_train_all.json" > "$RES/train_all.log" 2>&1
stamp "audit: train done (rc=$?)"
mkdir -p "$RES/train_predictor_logs" && cp checkpoints/audit_train/logs/*.log "$RES/train_predictor_logs/" 2>/dev/null
stamp "audit: hidden test, all predictors"
EVAL_DIAGNOSTICS="$RES/diagnostics_test.json" python eval/test/evaluate.py \
  --scores "$RES/scores_test_all.json" > "$RES/test_all.log" 2>&1
stamp "audit: test done (rc=$?)"
rm -f scripts/predict_hm_*.sh scripts/predict_sc_*.sh
python redteam/hardening/analyze.py > "$RES/summary.txt" 2>&1
cat "$RES/summary.txt"
