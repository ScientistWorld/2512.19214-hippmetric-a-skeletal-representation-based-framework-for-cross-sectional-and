# Train/Test Evaluation Design Notes

## Checked

- Read `scripts/evaluate_train.sh` and `scripts/evaluate_test.sh` side by side. The train wrapper calls `eval/train/evaluate.py` and writes `scoring/scores_train.json`; the test wrapper calls `eval/test/evaluate.py` and writes `scoring/scores_test.json`.
- Checked for hardcoded method defaults. Both split evaluators discover `checkpoints/*_outputs.npz` artifacts instead of naming a fixed method.
- Checked that split evaluators read method-produced artifacts and do not import from `method/`.
- Grepped the split evaluators, wrappers, and `scoring/reference.json` for train/test cross-imports and paper-agreement metric names.
- Confirmed no `scoring/scores_train.json` or `scoring/scores_test.json` stubs are present.
- Ran `bash -n` on both train/test wrapper scripts.

## Changed

- Strengthened the split from subject-only holdout to subject plus anatomical-feature holdout:
  - `eval/train/evaluate.py` scores the visible subject half and visible subsets of thickness positions, surface positions, cross-sectional landmarks, and longitudinal landmarks.
  - `eval/test/evaluate.py` scores the held-out subject half and complementary hidden anatomical feature subsets through the same method-output contract.
- Kept all scoring artifact requirements method-agnostic: both split evaluators still consume full-dataset `checkpoints/*_outputs.npz` files and do not call method code or regenerate method outputs.
- Preserved the first-pass `_slice` markers and p95 tail metrics.
- Updated `scoring/reference.json` metric descriptions to clarify that split metrics are computed on the scored anatomical positions.

## Design Rationale

The first-pass subject-level 50/50 split was useful but still vulnerable to a method that optimizes only the visible anatomical positions while preserving plausible outputs elsewhere. The new feature-level holdout adds an orthogonal shortcut check: a genuine HippMetric-style method should generalize across subjects and anatomical locations, while a method tuned narrowly to the visible thickness coordinates, landmarks, or surface vertices should show a train/test gap. This still avoids rerunning inference because both slices rescore the same full output artifact.

## Runtime Concerns For Next Iteration

- The split evaluators were not executed in this edit-only pass. The runner should verify that all added feature-index selections are nonempty and that all metrics are finite for each method artifact.
- The surface feature holdout assumes `recon_vertices` follows the benchmark's ordered surface-position contract, as produced by the packaged method and baseline. A future method that emits unordered surface point clouds may need to reorder outputs before evaluation.
- `surface_q_mm` and `surface_HD_mm` remain maximum-style diagnostics and may be highly redundant. `surface_p95_mm` provides the less brittle tail metric.
- Test evaluation optionally reads `scoring/scores_train.json` to restrict test scoring to methods seen during train scoring. If test runs without train scores, it falls back to discovered output artifacts, which is intentional.
