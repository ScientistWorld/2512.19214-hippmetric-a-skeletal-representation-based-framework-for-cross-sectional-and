# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-04 12:20] - core_claim
- Implemented a reduced-scale HippMetric pipeline with skeletal template coordinates, dense Gaussian-kernel deformation, paired spoke refinement, and baseline-anchored longitudinal processing.
- Packaged a procedural hippocampal benchmark with separate evaluation labels and method-visible geometry.
- CPU container jobs validated that HippMetric improves thickness, correspondence, and surface-fidelity metrics over the boundary-driven baseline while preserving valid local measurements.

## Stop Justification
- Current packaged environment supports the paper's core geometric correspondence claim on the procedural benchmark. Higher milestones require unavailable ADNI/GHABS assets or the paper's private template/manual landmark resources.
