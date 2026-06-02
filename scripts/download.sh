#!/bin/bash
# Download all data and models needed for this environment.
#
# Run on a node with internet access BEFORE building the container
# or submitting compute jobs.
#
# This script should be idempotent — safe to run multiple times.
# It should skip files that already exist.
#
# Update the storage estimate below as you add downloads.
#
# Estimated total download size: 0 GB
# Estimated disk usage after generation: <1 MB
#
# No external assets are required. This script regenerates the tracked
# procedural benchmark in a portable workspace-local location.

set -e

cd /home/user

if [ ! -e data/synthetic_hippocampus.npz ] || \
   [ ! -e data/synthetic_hippocampus_labels.npz ] || \
   [ data/synthetic_hippocampus.py -nt data/synthetic_hippocampus.npz ] || \
   [ data/synthetic_hippocampus.py -nt data/synthetic_hippocampus_labels.npz ]; then
  python data/synthetic_hippocampus.py \
    --output data/synthetic_hippocampus.npz \
    --labels-output data/synthetic_hippocampus_labels.npz
fi
