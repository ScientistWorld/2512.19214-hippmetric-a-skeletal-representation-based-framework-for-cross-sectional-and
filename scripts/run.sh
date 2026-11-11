#!/bin/bash
set -euo pipefail
cd /home/user
# CPU geometry, bundled reference reruns and audit variants; no installation.
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
python redteam/harness.py all
