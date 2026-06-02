# Reproduction Milestones

**Current: method_runs**

## Progress Log

### [2026-06-02 18:15] - method_runs
- Existing scaled HippMetric implementation executes end to end on the packaged procedural benchmark.
- The pipeline generates data, runs a boundary-driven baseline, runs the skeletal/spoke method, and writes scores.

### [2026-06-02 18:15] - core_claim
- Reproduced the core geometric claim on a reduced benchmark: the skeletal-coordinate method improves subfield thickness, cross-sectional/longitudinal correspondence, and surface agreement over a boundary-driven baseline.
- Paper clinical datasets, manual landmarks, and the stated public code repository were not accessible in the workspace; higher milestones would require those assets or a working upstream release.

### [2026-06-02 18:15] - method_runs
- Continuing-agent audit reset the active milestone to `method_runs` pending a fresh validation job.
- Fixed evaluation label leakage risk by separating method-visible geometry inputs from evaluation-only ground truth labels.
- Increased procedural surface noise so the benchmark correspondence errors are not an order of magnitude easier than the paper-scale landmark task; `core_claim` will be restored only after recomputed scores still support the skeletal-coordinate method over the boundary baseline.
