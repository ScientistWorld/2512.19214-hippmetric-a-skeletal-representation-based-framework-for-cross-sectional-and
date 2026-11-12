# Train/Test Evaluation Design Notes

Current design (hardening iteration; see `HARDENING.md` for the audit).

- **Interface.** Every `scripts/predict_<name>.sh INPUT_NPZ OUTPUT_NPZ` on disk is a method. Inputs are binary segmentations (format in `data/hippo_io.py`); outputs are, per scan and per template skeletal point (61 x 9 grid), the skeletal point and the superior/inferior spoke endpoints. Nothing else a method writes is read.
- **Train.** `eval/train/evaluate.py` runs all predictors on `data/hippo_train.npz` (32 subjects x 4 timepoints) and scores against `data/hippo_train_labels.npz`.
- **Test.** `eval/test/evaluate.py` generates the hidden cohort (32 subjects x 4 timepoints, fixed seed) with `eval/test/hidden_cohort.py` at evaluation time, writes only the segmentations to a temporary file, runs all predictors on it, and scores in memory. The public template used for the failure gate is regenerated inside `eval/test/`, not read from editable data files. `eval/train` and `eval/test` share no code.
- **Recomputed metrics.** Thickness (sum of spoke lengths), thickness change, subfield means, correspondence (endpoint vs true boundary point of the same template index), implied-surface distances to the clean true boundary, and validity (endpoint within 1 mm of the true boundary, no endpoint-order reversal) are all computed from the raw coordinates.
- **Failure rule.** Crash, timeout, missing/malformed/non-finite/absurd output, validity < 0.5, or no better than an evaluator-side trivial reference on thickness, thickness change, cross-sectional or longitudinal correspondence, or surface RMS => worst value in every scored metric of every experiment.
- **Data provenance.** `data/hippo_template.npz`, `data/hippo_train*.npz` are exported by `python eval/test/hidden_cohort.py --export-public data` (development seed 20251219); the test seed lives only in `eval/test/evaluate.py`.
