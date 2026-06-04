# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-04 12:15] - core_claim
- Continuing-agent audit reran the packaged CPU reproduction job `3133904a-3c8`; it exited with code `0`.
- `scripts/run.sh` regenerated method and baseline artifacts, full/train/test scores, and passed `python validate.py --compare` inside the container.
- Fresh results support the core claim: HippMetric beats the boundary baseline on thickness, cross-sectional correspondence, longitudinal correspondence, and surface robustness while preserving valid spokes.

### [2026-06-02 00:00] - core_claim
- Validated the reduced-scale HippMetric implementation on the procedural hippocampal benchmark.
- `python validate.py` passes with independently evaluated method outputs and surface `q`/`HD` reported as distinct diagnostics.
- HippMetric improves over the boundary baseline on thickness, correspondence, and surface robustness while preserving valid spokes.

## Stop Justification
- Completed at milestone `core_claim`.
