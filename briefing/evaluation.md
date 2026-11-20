# Evaluation

## Interface

A method is a script `scripts/predict_<name>.sh INPUT_NPZ OUTPUT_NPZ`. It is called once per cohort (procedural and real anatomy). The input has the format documented in `data/hippo_io.py`; its `cohort` entry (`"procedural"` or `"real"`) says which template applies (`data/hippo_template.npz` or `data/hippo_real_template.npz`; `hippo_io.template_path`). The output must contain, for every input scan (matched by `subjects`):

- `subjects` (N, 2): subject id and timepoint
- `skeleton` (N, 549, 3): the skeletal (internal) point for each template index, in scan coordinates (mm)
- `sup_end`, `inf_end` (N, 549, 3): the superior / inferior boundary point reached from it

Template index k is u-major on the cohort template's 61 x 9 grid. Every score is recomputed by the evaluator from these coordinates; nothing else a method writes is read.

## Metrics

Procedural cohort (ground truth for every template point):

- `thickness_mae_mm`, `thickness_p95_abs_error_mm`: point-wise error of thickness = |sup_end - skeleton| + |inf_end - skeleton|.
- `subfield_mean_thickness_error_mm`: error of the mean thickness within each subfield.
- `longitudinal_thickness_change_error_mm`: error of the measured follow-up-minus-baseline thickness change inside each subject's atrophic region.
- `valid_spoke_fraction`: fraction of spokes whose endpoint is within 1 mm of the true boundary and whose endpoint grid does not reverse the skeletal ordering.
- `cross_sectional_correspondence_error_mm` (+ p95): distance from each submitted endpoint to the true boundary point with the same template index, on baseline scans.
- `longitudinal_correspondence_error_mm` (+ p95): the same inside the atrophic region on follow-up scans.
- `surface_Q_mm`, `surface_HD_mm`, `surface_p95_mm`: RMS, Hausdorff and 95th-percentile distances between the boundary implied by the endpoints (densified on the template grid) and the true, noise-free boundary.

Real-anatomy cohort (ground truth for how the anatomy changes between baseline and follow-ups). Each submitted baseline endpoint is projected onto the true baseline boundary; its true follow-up position is where that anatomical point is after the known change.

- `real_longitudinal_correspondence_error_mm` (+ p95): distance between the submitted follow-up endpoint and the true follow-up position of the same point, for points inside the atrophic region (tissue loss at least 30 % of its peak).
- `real_stable_correspondence_error_mm`: the same for points outside it (less than 5 % of the peak), where only the smooth deformation and pose act.
- `real_thickness_change_error_mm`: error of the measured follow-up-minus-baseline thickness of each spoke against the true change of the same spoke (true follow-up endpoints and skeletal point), inside the atrophic region.
- `real_surface_Q_mm`: RMS distance between the implied boundary and the true noise-free boundary, all real-anatomy scans.
- `real_valid_spoke_fraction`: validity as above, on the real-anatomy scans.

All errors are lower-is-better; validity is higher-is-better. The real-anatomy metrics are filed under the experiment they belong to: thickness change and validity under `subfield_thickness_accuracy`, correspondence under `correspondence_stability`, surface under `surface_robustness`.

## Failure Rule

A run fails if the predictor crashes or times out (2 h per cohort call), writes a malformed, non-finite or absurd output, has validity below 0.5 in either cohort, or does no better than evaluator-side trivial references: thickness (a per-scan constant), thickness change (no change; on the real cohort, no change on the method's own spokes), correspondence (template placed at the segmentation centroid) or surface RMS (the same). A failed run receives the worst value of every scored metric in every experiment.

## Running

- `bash scripts/evaluate_train.sh` runs every predictor on both development cohorts and writes `scoring/scores_train.json` (`scripts/evaluate.sh` writes the same to `scoring/scores.json`).
- `bash scripts/evaluate_test.sh` runs every predictor on both hidden cohorts and writes `scoring/scores_test.json`.

## Paper Context

The paper evaluates on ADNI/GHABS FreeSurfer segmentations with manual landmarks and manual thickness measurements, which are not redistributable. It reports ~1.66 mm cross-sectional and 1.68 mm longitudinal correspondence error for its method versus 3.4-10.6 mm for other shape models (the longitudinal numbers come from simulated anterior atrophy on 15 real baselines, scored against manual landmarks), subfield thickness errors below 0.5 mm, and CI-group Hausdorff distance about 1.8 mm. This benchmark's numbers are not expected to match the paper's.
