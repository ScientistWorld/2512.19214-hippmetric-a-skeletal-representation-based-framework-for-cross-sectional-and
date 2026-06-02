# Evaluation Targets

## Primary: subfield_thickness_accuracy

Tests whether local hippocampal subfield thickness can be estimated accurately from 3D surfaces.

- **Metric**: `thickness_mae_mm` (lower is better)
- **Constraint**: `valid_spoke_fraction` (higher is better)
- **How to run**: `bash scripts/evaluate.sh` after producing outputs in `checkpoints/`.

## Primary: correspondence_stability

Tests whether anatomical landmarks remain consistently localized across baseline subjects and longitudinal atrophy-like follow-ups.

- **Metric**: `longitudinal_correspondence_error_mm` (lower is better)
- **Secondary metric**: `cross_sectional_correspondence_error_mm` (lower is better)
- **Constraint**: `valid_spoke_fraction` (higher is better)
- **How to run**: `bash scripts/evaluate.sh` after producing outputs in `checkpoints/`.

## Constraint: surface_robustness

Tests whether improved correspondence is achieved while maintaining geometric agreement with the observed surface.

- **Metric**: `surface_HD_mm` (lower is better)
- **Secondary metrics**: `surface_Q_mm`, `surface_q_mm` (lower is better)
- **Constraint**: `valid_spoke_fraction` (higher is better)
- **How to run**: `bash scripts/evaluate.sh` after producing outputs in `checkpoints/`.
