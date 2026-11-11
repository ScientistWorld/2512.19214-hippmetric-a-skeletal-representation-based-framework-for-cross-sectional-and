#!/bin/bash
# Hardening-audit predictor (installed into scripts/ only during the audit job).
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python "$ROOT/redteam/hardening/shortcut.py" --mode template_only "$1" "$2"
