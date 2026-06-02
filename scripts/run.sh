#!/bin/bash
# Run visible and held-out split scoring over existing method outputs.

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh
