# Scientist Constraints

## Data

Predictors may read the scans they are given, `data/hippo_template.npz`, and the development cohort (`data/hippo_train.npz`, `data/hippo_train_labels.npz`) for design and fitting. They must not read evaluation code or anything under `eval/`, and must not try to reconstruct the hidden test cohort.

## Output Interface

Add `scripts/predict_<name>.sh INPUT_NPZ OUTPUT_NPZ`. The output holds `subjects`, `skeleton`, `sup_end`, `inf_end` as documented in `briefing/evaluation.md`, indexed by the template's 61 x 9 skeletal grid. All metrics are recomputed from these coordinates.

## Resources

CPU only. A predictor must finish the hidden cohort (128 scans) within one hour. The evaluation never retrains; any fitting happens on the development cohort before evaluation.

## Compliance Checklist

- [ ] The predictor does not import from or read `eval/`.
- [ ] Outputs are in scan coordinates and indexed by the template grid.
- [ ] Scores come from `scripts/evaluate_train.sh` / `scripts/evaluate_test.sh`, not self-reported.
