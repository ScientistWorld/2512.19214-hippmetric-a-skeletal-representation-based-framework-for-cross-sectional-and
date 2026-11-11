#!/bin/bash
# Fetch external data and models for this environment.
#
# Estimated total download size: 0 GB.
#
# This benchmark has no external downloads. Its inputs are agent-authored and
# tracked in git under data/:
#   data/hippo_template.npz        public template s-rep and template segmentation
#   data/hippo_train.npz           visible development cohort (segmentations)
#   data/hippo_train_labels.npz    visible development ground truth
# The clinical cohorts used by the paper (ADNI, GHABS) require data-use
# agreements and are not used. The held-out test cohort is generated inside
# eval/test/ at evaluation time and is never written to data/.
#
# The script fails loudly if a tracked input is missing from the checkout.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p data/downloads
for f in data/hippo_template.npz data/hippo_train.npz data/hippo_train_labels.npz; do
  if [ ! -s "$f" ]; then
    echo "missing tracked input $f: restore it with 'git checkout -- $f'" >&2
    exit 1
  fi
done
echo "No external downloads required."
