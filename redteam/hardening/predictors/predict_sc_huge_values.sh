#!/bin/bash
# Hardening-audit predictor (installed into scripts/ only during the audit job).
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python "$ROOT/redteam/hardening/shortcut.py" --mode huge_values "$1" "$2"
