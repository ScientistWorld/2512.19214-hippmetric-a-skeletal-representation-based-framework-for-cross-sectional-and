#!/usr/bin/env python3
"""One-off builder for the hidden real-anatomy test files (not run at evaluation time).

  eval/test/real_heldout.npz   the held-out MSD Task04 cases (1 mm whole and head masks)
  eval/test/real_template.npz  fixed copy of data/hippo_real_template.npz, used by the
                               evaluator's trivial reference so that an edited data file
                               cannot move the failure gate

Usage: python eval/test/build_real_heldout.py [--archive data/downloads/msd/Task04_Hippocampus.tar]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "data"))
import msd_hippocampus as msd  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", type=Path, default=ROOT / "data/downloads/msd/Task04_Hippocampus.tar")
    args = parser.parse_args()
    labels = msd.read_labels(args.archive)
    _, held = msd.split_ids(labels)
    np.savez_compressed(HERE / "real_heldout.npz", **msd.anatomy_arrays(labels, held))
    shutil.copyfile(ROOT / "data/hippo_real_template.npz", HERE / "real_template.npz")
    print(f"[heldout] wrote {len(held)} held-out cases and the template copy")


if __name__ == "__main__":
    main()
