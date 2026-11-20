#!/bin/bash
# Final hardening job (not part of the gym; scripts/run.sh is the gym's reference run).
#   1. build the real-anatomy files from the MSD archive (public dev set + template,
#      hidden held-out set + template copy)
#   2. smoke test of the real cohort
#   3. reference run (scripts/reproduce.sh): baseline + HippMetric, train/full/test scores
#   4. audit of variants and shortcuts (redteam/hardening/run_audit.sh)
#   5. python validate.py --compare
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
RES=redteam/hardening/results
mkdir -p "$RES"
start=$(date +%s)
stamp() { echo "[job $(( $(date +%s) - start ))s] $*" | tee -a "$RES/timeline.txt"; }

if [ ! -s data/hippo_real_template.npz ] || [ ! -s eval/test/real_heldout.npz ]; then
  stamp "build real-anatomy files"
  python data/build_real_template.py > "$RES/build_template.log" 2>&1 || { stamp "build_real_template FAILED"; cat "$RES/build_template.log"; exit 1; }
  python eval/test/build_real_heldout.py > "$RES/build_heldout.log" 2>&1 || { stamp "build_real_heldout FAILED"; cat "$RES/build_heldout.log"; exit 1; }
fi
cat "$RES/build_template.log" "$RES/build_heldout.log" 2>/dev/null

if [ ! -s "$RES/smoke.log" ] || ! grep -q "hm_nonrigid_followups" "$RES/smoke.log"; then
  stamp "smoke test"
  python redteam/hardening/smoke.py > "$RES/smoke.log" 2>&1 || { stamp "smoke FAILED"; cat "$RES/smoke.log"; exit 1; }
fi
cat "$RES/smoke.log"

if [ ! -s "$RES/reproduce.done" ]; then
  stamp "reference run (scripts/reproduce.sh)"
  bash scripts/reproduce.sh > "$RES/reproduce.log" 2>&1
  rc=$?
  stamp "reference run rc=$rc"
  [ $rc -eq 0 ] && echo ok > "$RES/reproduce.done"
  tail -40 "$RES/reproduce.log"
fi

stamp "audit"
bash redteam/hardening/run_audit.sh
stamp "audit done"

python validate.py --compare > "$RES/validate.log" 2>&1
stamp "validate rc=$?"
tail -30 "$RES/validate.log"
