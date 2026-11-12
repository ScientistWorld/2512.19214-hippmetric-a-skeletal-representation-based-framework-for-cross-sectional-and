# Evaluation Targets

All experiments are scored by `bash scripts/evaluate_test.sh` (hidden cohort) and `bash scripts/evaluate_train.sh` (development cohort) from predictor outputs; see `briefing/evaluation.md` for the interface.

## Primary: correspondence_stability (weight 0.50)

- **Metrics**: `longitudinal_correspondence_error_mm` (primary), `longitudinal_p95_correspondence_error_mm`, `cross_sectional_correspondence_error_mm`, `cross_sectional_p95_correspondence_error_mm` (lower is better)
- **Paper direction**: the skeletal method beats boundary-driven shape models cross-sectionally and longitudinally (paper: 1.66 / 1.68 mm vs 3.4-10.6 mm).

## Primary: subfield_thickness_accuracy (weight 0.25)

- **Metrics**: `thickness_mae_mm` (primary), `thickness_p95_abs_error_mm`, `subfield_mean_thickness_error_mm`, `longitudinal_thickness_change_error_mm` (lower is better)
- **Constraint**: `valid_spoke_fraction` (higher is better; below 0.5 fails the run)

## Constraint: surface_robustness (weight 0.25)

- **Metrics**: `surface_HD_mm` (primary), `surface_Q_mm`, `surface_p95_mm` (lower is better)
- **Purpose**: the implied boundary must stay on the true anatomy for baseline and atrophied scans.

## Failure constraint (all experiments)

A run that crashes, writes invalid output, has validity below 0.5, or is no better than the evaluator's trivial references on thickness, thickness change, correspondence or surface RMS receives the worst value in every metric.
