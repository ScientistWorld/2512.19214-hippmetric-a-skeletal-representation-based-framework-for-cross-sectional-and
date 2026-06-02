# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-02 18:02] - core_claim
- Implemented and evaluated the paper's core skeletal-coordinate and spoke-refinement computation on a procedural hippocampal benchmark.
- Compute-container job `078ea881-f47` ran `scripts/reproduce.sh` and `python validate.py --compare` successfully.
- HippMetric reduced longitudinal correspondence error from `1.950 mm` for the boundary baseline to `0.148 mm` while preserving `valid_spoke_fraction = 1.000`.

## Stop Justification
- Completed at milestone `core_claim`. Further clinical reproduction would require unavailable ADNI/GHABS cohort assets, manual landmarks, or the paper's private template data.
