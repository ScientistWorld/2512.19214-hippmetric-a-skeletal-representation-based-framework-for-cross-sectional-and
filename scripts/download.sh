#!/bin/bash
# Download all data and models needed for this environment.
#
# Run on a node with internet access BEFORE building the container
# or submitting compute jobs.
#
# This script is idempotent: the procedural generator is deterministic with
# default arguments, so rerunning it recreates the same benchmark files.
#
# Update the storage estimate below as you add downloads.
#
# Estimated total download size: 0 GB
# Estimated disk usage after generation: <1 MB
#
# No external assets are required. This script regenerates the tracked
# procedural benchmark in a portable workspace-local location.

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python data/synthetic_hippocampus.py \
  --output data/synthetic_hippocampus.npz \
  --labels-output data/synthetic_hippocampus_labels.npz
