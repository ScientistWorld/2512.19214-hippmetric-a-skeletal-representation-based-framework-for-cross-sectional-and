#!/bin/bash
# Run split evaluation over existing final method outputs.

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh
