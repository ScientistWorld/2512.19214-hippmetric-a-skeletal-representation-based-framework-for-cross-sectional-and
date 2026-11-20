# Scientist Constraints

## Data

Predictors may read the scans they are given, the two templates (`data/hippo_template.npz`, `data/hippo_real_template.npz`), and the development data (`data/hippo_train.npz`, `data/hippo_train_labels.npz`, `data/hippo_real_anatomy.npz`, the real-anatomy development scans and truth produced by `eval/train/`) for design and fitting. They must not read anything under `eval/test/`, must not try to reconstruct the hidden test cohorts, and must not look up held-out cases in the public MSD archive (`data/downloads/`) to recover their clean labels.

## Output Interface

Add `scripts/predict_<name>.sh INPUT_NPZ OUTPUT_NPZ`. It is called once per cohort; the input's `cohort` entry says which template applies. The output holds `subjects`, `skeleton`, `sup_end`, `inf_end` as documented in `briefing/evaluation.md`, indexed by that template's 61 x 9 skeletal grid. All metrics are recomputed from these coordinates.

## Resources

CPU only. A predictor must finish each hidden cohort (128 scans) within two hours. The evaluation never retrains; any fitting happens on the development data before evaluation.

## Compliance Checklist

- [ ] The predictor does not import from or read `eval/test/`, and does not read the MSD archive at prediction time.
- [ ] Outputs are in scan coordinates and indexed by the cohort template's grid.
- [ ] Scores come from `scripts/evaluate_train.sh` / `scripts/evaluate_test.sh`, not self-reported.
