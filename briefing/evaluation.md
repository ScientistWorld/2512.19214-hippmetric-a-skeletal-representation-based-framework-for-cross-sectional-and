# Evaluation

## Interface

A method is a script `scripts/predict_<name>.sh INPUT_NPZ OUTPUT_NPZ`. The input has the format documented in `data/hippo_io.py`. The output must contain, for every input scan (matched by `subjects`):

- `subjects` (N, 2): subject id and timepoint
- `skeleton` (N, 549, 3): the skeletal (internal) point for each template index, in scan coordinates (mm)
- `sup_end`, `inf_end` (N, 549, 3): the superior / inferior boundary point reached from it

Template index k is u-major on the 61 x 9 grid of `data/hippo_template.npz`. Every score is recomputed by the evaluator from these coordinates; nothing else a method writes is read.

## Metrics

- `thickness_mae_mm`, `thickness_p95_abs_error_mm`: point-wise error of thickness = |sup_end - skeleton| + |inf_end - skeleton|.
- `subfield_mean_thickness_error_mm`: error of the mean thickness within each subfield.
- `longitudinal_thickness_change_error_mm`: error of the measured follow-up-minus-baseline thickness change inside each subject's atrophic region.
- `valid_spoke_fraction`: fraction of spokes whose endpoint is within 1 mm of the true boundary and whose endpoint grid does not reverse the skeletal ordering.
- `cross_sectional_correspondence_error_mm` (+ p95): distance from each submitted endpoint to the true boundary point with the same template index, on baseline scans.
- `longitudinal_correspondence_error_mm` (+ p95): the same inside the atrophic region on follow-up scans.
- `surface_Q_mm`, `surface_HD_mm`, `surface_p95_mm`: RMS, Hausdorff and 95th-percentile distances between the boundary implied by the endpoints (densified on the template grid) and the true, noise-free boundary.

All errors are lower-is-better; validity is higher-is-better.

## Failure Rule

A run fails if the predictor crashes or times out, writes a malformed, non-finite or absurd output, has validity below 0.5, or does no better than evaluator-side trivial references on thickness (a per-scan constant), thickness change (no change), correspondence (template placed at the segmentation centroid) or surface RMS (the same). A failed run receives the worst value of every scored metric in every experiment.

## Running

- `bash scripts/evaluate_train.sh` runs every predictor on the development cohort and writes `scoring/scores_train.json` (`scripts/evaluate.sh` writes the same to `scoring/scores.json`).
- `bash scripts/evaluate_test.sh` runs every predictor on the hidden cohort and writes `scoring/scores_test.json`.

## Paper Context

The paper evaluates on ADNI/GHABS FreeSurfer segmentations with manual landmarks and manual thickness measurements, which are not redistributable. It reports ~1.66 mm cross-sectional and 1.68 mm longitudinal correspondence error for its method versus 3.4-10.6 mm for other shape models, subfield thickness errors below 0.5 mm, and CI-group Hausdorff distance about 1.8 mm. This benchmark is a procedural substitute; its numbers are not expected to match the paper's.
