#!/bin/bash
# Run the paper's proposed method.
#
# This script trains/runs the paper's method using code in method/.
#
# Usage:
#   bash scripts/method.sh

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p checkpoints
python method/hippmetric.py \
  --dataset data/synthetic_hippocampus.npz \
  --output checkpoints/hippmetric_outputs.npz
