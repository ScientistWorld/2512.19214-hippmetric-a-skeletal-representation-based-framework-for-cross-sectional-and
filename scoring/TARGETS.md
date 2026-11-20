# Evaluation Targets

All experiments are scored by `bash scripts/evaluate_test.sh` (hidden cohorts) and `bash scripts/evaluate_train.sh` (development cohorts) from predictor outputs; see `briefing/evaluation.md` for the interface. Metrics prefixed `real_` come from the real-anatomy cohort, the others from the procedural cohort.

## Primary: correspondence_stability (weight 0.50)

- **Metrics**: `longitudinal_correspondence_error_mm` (primary), `longitudinal_p95_correspondence_error_mm`, `cross_sectional_correspondence_error_mm`, `cross_sectional_p95_correspondence_error_mm`, `real_longitudinal_correspondence_error_mm`, `real_longitudinal_p95_correspondence_error_mm`, `real_stable_correspondence_error_mm` (lower is better)
- **Paper direction**: the skeletal method beats boundary-driven shape models cross-sectionally and longitudinally (paper: 1.66 / 1.68 mm vs 3.4-10.6 mm). Reproduced on both cohorts: the reference beats the boundary-driven baseline on every correspondence metric.

## Primary: subfield_thickness_accuracy (weight 0.25)

- **Metrics**: `thickness_mae_mm` (primary), `thickness_p95_abs_error_mm`, `subfield_mean_thickness_error_mm`, `longitudinal_thickness_change_error_mm`, `real_thickness_change_error_mm` (lower is better)
- **Constraints**: `valid_spoke_fraction`, `real_valid_spoke_fraction` (higher is better; below 0.5 fails the run); thickness change must beat reporting no change.

## Constraint: surface_robustness (weight 0.25)

- **Metrics**: `surface_HD_mm` (primary), `surface_Q_mm`, `surface_p95_mm`, `real_surface_Q_mm` (lower is better)
- **Purpose**: the implied boundary must stay on the true anatomy for baseline, atrophied and real scans.

## Failure constraint (all experiments)

A run that crashes, writes invalid output, has validity below 0.5 in either cohort, or is no better than the evaluator's trivial references on thickness, thickness change, correspondence or surface RMS (in either cohort) receives the worst value in every metric.
