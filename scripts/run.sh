#!/bin/bash
# Hardening job: build the real-anatomy files, smoke test, reference run,
# variant/shortcut audit, validation (redteam/hardening/job.sh).
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
bash redteam/hardening/job.sh
