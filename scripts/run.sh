#!/bin/bash
set -euo pipefail
cd /home/user
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
# One additional finite-output test of additive compensation for failed thickness.
bash redteam/shortcut_zero_thickness/run.sh
python redteam/analyze.py
