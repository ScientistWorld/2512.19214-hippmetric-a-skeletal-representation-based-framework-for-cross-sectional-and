# Verification Report

## Initial Assessment

The workspace entered final verification at `core_claim`. The claimed milestone was justified at reduced scale: the implemented method runs end to end on the packaged procedural hippocampal benchmark and outperforms the boundary-driven baseline on thickness, cross-sectional correspondence, longitudinal correspondence, and surface fidelity. The main limitation is that the clinical ADNI/GHABS data, manual landmarks, full template assets, and upstream repository are unavailable, so this is a procedural benchmark rather than a full clinical reproduction.

## Issues Found

- **Minor**: `scripts/evaluate.sh` originally hardcoded the paper method and baseline artifact paths. This would make future methods harder to score without editing evaluator code.
- **Minor**: The main `scores.json` evaluator did not emit the p95 tail metrics already declared in `reference.json` and used by the train/test evaluators.
- **Minor**: `valid_spoke_fraction` was purely method-reported, making the validity constraint easy to game.
- **Cosmetic**: `briefing/evaluation.md` and `scoring/DIRECTION.md` named the paper method and mechanism more directly than needed for method-safe, from-scratch guidance.

## Fixes Applied

- Made `eval/evaluate_outputs.py` discover and score every `checkpoints/*_outputs.npz` artifact, matching the train/test evaluator interface.
- Added p95 thickness, correspondence, and surface metrics to the main `scores.json` output.
- Capped reported validity by evaluator-observable checks for finite, nonnegative thickness and finite landmark/surface outputs in the main, train, and test evaluators.
- Reworded method-safe documentation to describe the problem and allowed research direction without over-specifying the paper's implementation.
- Submitted CPU job `01b6d854-37c`, which regenerated `scores.json`, `scores_train.json`, and `scores_test.json` and passed `python validate.py --compare` inside the container.

## Final Judgment

The workspace is ready to serve as a research gym at `core_claim`. Improve-mode agents can build on the reproduced method, and from-scratch agents can use the data/eval/problem files without importing or depending on `method/`. The gym has meaningful train/test slices and a reusable evaluator, but it remains a reduced procedural benchmark rather than a full reproduction on the paper's private/controlled clinical cohorts.

- Milestone: core_claim
- Ready for gym use: yes
- Confidence: medium
- Key limitation: synthetic procedural data only, because the paper's clinical cohorts and upstream example assets were unavailable.
