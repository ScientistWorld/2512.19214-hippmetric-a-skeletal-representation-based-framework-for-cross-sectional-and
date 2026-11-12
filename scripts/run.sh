#!/bin/bash
# CPU job: regenerate the public inputs, run the hardening audit, then
# reproduce the reference end to end from the final code and validate.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RES=redteam/hardening/results
mkdir -p "$RES"
python eval/test/hidden_cohort.py --export-public data > "$RES/export.log" 2>&1 || { cat "$RES/export.log"; exit 1; }
ls -la data >> "$RES/export.log"
bash redteam/hardening/run_audit.sh
rm -rf checkpoints/train
bash scripts/reproduce.sh > "$RES/reproduce.log" 2>&1
echo "reproduce rc=$?" | tee -a "$RES/timeline.txt"
python validate.py --compare > "$RES/validate.log" 2>&1
echo "validate rc=$?" | tee -a "$RES/timeline.txt"
tail -30 "$RES/validate.log"
