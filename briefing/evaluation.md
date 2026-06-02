# Evaluation

## Metrics

The evaluation uses millimeter-scale geometric errors and a validity constraint:

- `thickness_mae_mm`: mean absolute error between predicted and reference local subfield thickness. Lower is better.
- `cross_sectional_correspondence_error_mm`: Euclidean error between predicted and reference landmarks for baseline scans. Lower is better.
- `longitudinal_correspondence_error_mm`: Euclidean error between predicted and reference landmarks under follow-up atrophy. Lower is better.
- `surface_Q_mm`, `surface_q_mm`, `surface_HD_mm`: mean, maximum, and Hausdorff nearest-surface distances between reconstructed and observed surfaces. Lower is better.
- `valid_spoke_fraction`: fraction of local measurements that remain geometrically valid. Higher is better.

## Baselines and Targets

The paper reports HippMetric correspondence errors of about `1.66 mm` cross-sectionally and `1.68 mm` longitudinally, with competing shape models ranging from `3.41 mm` to `9.97 mm` cross-sectionally and `3.56 mm` to `10.57 mm` longitudinally. It also reports subfield thickness errors below `0.5 mm` and robust reconstruction under pathology, with HippMetric CI `HD` around `1.809 mm`.

This workspace uses a small procedural benchmark because the clinical ADNI/GHABS labels, manual landmarks, and supplemental tables are not packaged. The same metric definitions are retained, and the evaluator compares method outputs against known procedural ground truth.

## Evaluation Protocol

Run `bash scripts/reproduce.sh` to generate the benchmark data, run the boundary baseline, run the reproduced method, and write `scoring/scores.json`. `scripts/evaluate.sh` is method-independent: it reads output files from `checkpoints/` and only imports code from `eval/`.
