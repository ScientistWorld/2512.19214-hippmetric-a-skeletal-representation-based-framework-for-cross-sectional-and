#!/bin/bash
# Fetch external data for this environment.
#
# Estimated total download size: 0.03 GB (MSD Task04_Hippocampus.tar, 27 MB).
#
# The real hippocampus anatomy comes from the Medical Segmentation Decathlon,
# Task04_Hippocampus (Vanderbilt University Medical Center, CC-BY-SA 4.0), via
# the public MONAI mirror. From it, data/build_real_template.py derives the
# tracked files data/hippo_real_anatomy.npz (development subjects) and
# data/hippo_real_template.npz (real-anatomy template); the held-out subjects
# used by the hidden test are stored only under eval/test/.
# The procedural cohort (data/hippo_template.npz, data/hippo_train*.npz) is
# agent-generated and tracked in git. The clinical cohorts used by the paper
# (ADNI, GHABS) require data-use agreements and are not used.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p data/downloads/msd
TAR=data/downloads/msd/Task04_Hippocampus.tar
if [ ! -s "$TAR" ]; then
  curl -fL --retry 3 -o "$TAR.part" https://msd-for-monai.s3-us-west-2.amazonaws.com/Task04_Hippocampus.tar
  mv "$TAR.part" "$TAR"
fi
echo "9d24dba78a72977dbd1d2e110310f31b  $TAR" | md5sum -c -
# Derived files are tracked; rebuild them only when missing.
if [ ! -s data/hippo_real_anatomy.npz ] || [ ! -s data/hippo_real_template.npz ]; then
  python data/build_real_template.py --archive "$TAR"
fi
for f in data/hippo_template.npz data/hippo_train.npz data/hippo_train_labels.npz; do
  if [ ! -s "$f" ]; then
    echo "missing tracked input $f: restore it with 'git checkout -- $f'" >&2
    exit 1
  fi
done
