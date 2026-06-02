# Train/Test Evaluation Design Notes

## Checked

- Read `scripts/evaluate_train.sh` and `scripts/evaluate_test.sh` side by side. The train wrapper calls `eval/train/evaluate.py` and writes `scoring/scores_train.json`; the test wrapper calls `eval/test/evaluate.py` and writes `scoring/scores_test.json`.
- Checked for hardcoded method defaults. Both split evaluators discover `checkpoints/*_outputs.npz` artifacts instead of naming a fixed method.
- Checked that split evaluators read method-produced artifacts and do not import from `method/`.
- Grepped for train/test cross-imports and paper-agreement metric names in the split evaluators, wrappers, and `scoring/reference.json`.
- Confirmed no `scoring/scores_train.json` or `scoring/scores_test.json` stubs are present.
- Ran `bash -n` on both train/test wrapper scripts. `jq` is not installed, so JSON parsing was not separately executed in this edit-only pass.

## Changed

- Added explicit `_slice` markers to train and test score outputs so runner artifacts identify whether they came from the visible or held-out scorer.
- Added tail-error metrics to both `eval/train/evaluate.py` and `eval/test/evaluate.py`:
  - `thickness_p95_abs_error_mm`
  - `cross_sectional_p95_correspondence_error_mm`
  - `longitudinal_p95_correspondence_error_mm`
  - `surface_p95_mm`
- Added the new metrics to `scoring/reference.json` with nonzero coefficients.
- Added the required `description` field to every metric in `scoring/reference.json`.

## Design Rationale

The existing subject-level 50/50 split is appropriate for this synthetic hippocampal morphometry benchmark because it keeps train and test difficulty comparable while hiding subject identities. The first-pass metrics were mostly means plus maximum-like surface distances, which left room for methods that optimize average behavior while failing on local subfields, selected landmarks, or a subset of surface points. The added p95 metrics sharpen the anti-shortcut signal without changing the method interface or requiring expensive re-execution.

## Runtime Concerns For Next Iteration

- The split evaluators were not executed in this pass by instruction. The runner should verify that all output arrays have expected shapes and that the added quantile metrics are finite.
- `surface_q_mm` and `surface_HD_mm` are both maximum-style bidirectional distances in the current scorer and may be highly redundant. `surface_p95_mm` was added to provide a less brittle tail metric, but the runner should check whether the two maximum metrics are numerically identical on produced scores.
- Test evaluation optionally reads `scoring/scores_train.json` to restrict test scoring to methods seen during train scoring. If the final workflow runs test without first running train, it falls back to discovered output artifacts, which is intentional.
