# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-04 12:20] - core_claim
- Implemented a reduced-scale HippMetric pipeline with skeletal template coordinates, dense Gaussian-kernel deformation, paired spoke refinement, and baseline-anchored longitudinal processing.
- Packaged a procedural hippocampal benchmark with separate evaluation labels and method-visible geometry.
- CPU container jobs validated that HippMetric improves thickness, correspondence, and surface-fidelity metrics over the boundary-driven baseline while preserving valid local measurements.

### [2026-06-04 12:26] - core_claim
- Managed CPU container job `69a1af48-426` reran `scripts/run.sh` end to end and exited successfully.
- The job regenerated full, train, and test score files, and `python validate.py --compare` reported all checks passed.
- Final milestone remains `core_claim`; higher milestones need unavailable clinical/template/manual landmark resources.

## Stop Justification
- Completed at milestone `core_claim`.
