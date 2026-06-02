# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-02 00:00] - none
- Started reproduction work from an empty scaffold.
- Read the HippMetric paper and identified the central computable claim: skeletal/lamellar correspondence with geometry-preserving spoke refinement improves local morphometry and longitudinal stability.

### [2026-06-02 00:00] - method_runs
- Implemented a scaled HippMetric pipeline with lamellar skeleton coordinates, paired superior/inferior spokes, boundary convergence, normal alignment, baseline-anchored longitudinal spoke optimization, and local thickness extraction.
- Added a method-independent synthetic hippocampal benchmark and boundary-driven baseline.
- Ran `bash scripts/reproduce.sh && python validate.py --compare` locally; all validation checks passed.

### [2026-06-02 00:00] - core_claim
- Scheduler job `078ea881-f47` completed with exit code `0`.
- The job regenerated the synthetic benchmark, ran the boundary baseline and HippMetric implementation, wrote `scoring/scores.json`, and passed `python validate.py --compare`.
- HippMetric improved the central correspondence/morphometry metrics over the boundary baseline while preserving valid local measurements: thickness MAE `0.121 mm` vs `7.090 mm`, longitudinal correspondence `0.148 mm` vs `1.950 mm`, surface HD `0.645 mm` vs `3.647 mm`, and valid spoke fraction `1.000`.

## Stop Justification
- Stopping at `core_claim`. The paper's clinical ADNI/GHABS experiments, manual landmark tables, and classification/prognosis analyses require controlled-access or unavailable assets. The reusable environment reproduces the paper's central computational claim on a non-trivial procedural benchmark with a method-independent evaluator.
