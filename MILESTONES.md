# Reproduction Milestones

**Current: method_runs**

## Progress Log

### [2026-06-04 13:23] - method_runs
- CPU container job `f3c6455c-ab9` validated that normal-aware boundary-assignment landmark reporting runs and passes `python validate.py --compare`, but it still does not support `core_claim`.
- The boundary-assignment path preserved thickness and surface improvements (HippMetric thickness MAE `0.354 mm` vs boundary `6.971 mm`, surface Q `0.105 mm` vs boundary `1.308 mm`) but correspondence remained worse than the boundary baseline (cross-sectional `5.081 mm` vs `2.038 mm`, longitudinal `8.846 mm` vs `2.909 mm`).
- Added an atlas-orientation prior to PCA sign selection and uses non-iterated atlas alignment for scored landmark assignment to reduce long-axis/sign ambiguity before order-free matching.

### [2026-06-04 13:18] - method_runs
- CPU container job `ddcdaa10-328` validated that coordinate-frame landmark reporting runs and passes `python validate.py --compare`, but it still does not support `core_claim`.
- The coordinate-frame path preserved thickness and surface improvements (HippMetric thickness MAE `0.354 mm` vs boundary `6.971 mm`, surface Q `0.105 mm` vs boundary `1.308 mm`) but correspondence remained worse than the boundary baseline (cross-sectional `5.112 mm` vs `2.038 mm`, longitudinal `8.842 mm` vs `2.909 mm`).
- Updated HippMetric landmark outputs to use an order-free, normal-aware boundary assignment in template index order for scored correspondence landmarks, while keeping refined paired spokes for thickness and reconstruction.

### [2026-06-04 13:13] - method_runs
- CPU container job `991e5724-553` validated that damped internal transport runs and passes `python validate.py --compare`, but it still does not support `core_claim`.
- The damped path preserved the strong thickness and surface results (HippMetric thickness MAE `0.355 mm` vs boundary `6.971 mm`, surface Q `0.105 mm` vs boundary `1.308 mm`) but correspondence remained worse than the boundary baseline (cross-sectional `5.082 mm` vs `2.038 mm`, longitudinal `7.718 mm` vs `2.909 mm`).
- Updated HippMetric landmark outputs to use the subject-aligned skeletal coordinate frame for correspondence landmarks, while leaving refined paired spokes as the source of thickness and surface reconstruction outputs.

### [2026-06-04 12:58] - method_runs
- CPU container job `0a0df724-0dd` regenerated procedural data, baseline outputs, HippMetric outputs, full scores, train/test scores, and ran `python validate.py --compare` with exit code `0`.
- The tightened order-free path executes end to end, so `method_runs` is restored.
- The job does not support `core_claim`: HippMetric improved thickness MAE (`0.499 mm` vs `6.971 mm`) and surface Q (`0.439 mm` vs `1.308 mm`) but lost correspondence stability to the boundary baseline (cross-sectional `5.296 mm` vs `2.038 mm`, longitudinal `7.743 mm` vs `2.909 mm`).
- Added an order-free one-to-one surface assignment in the registration/deformation loop and resubmitted a CPU validation job to test whether the core correspondence result is restored without using vertex row order.

### [2026-06-04 13:03] - method_runs
- CPU container job `233a513d-e94` validated that the one-to-one assignment path runs and passes `python validate.py --compare`, but it still does not support `core_claim`.
- Assignment improved thickness (`0.351 mm`) and surface fidelity (`Q=0.130 mm`) but correspondence remains worse than the boundary baseline (cross-sectional `5.103 mm` vs `2.038 mm`, longitudinal `7.737 mm` vs `2.909 mm`).
- Added observed surface-normal agreement to PCA sign selection and order-free assignment, and uses method-visible normals during spoke refinement to reduce anatomical side and long-axis ambiguity.

### [2026-06-04 13:08] - method_runs
- CPU container job `5e516a21-8cf` validated that the normal-aware assignment path runs and passes `python validate.py --compare`, but it still does not support `core_claim`.
- Normal-aware matching improved surface fidelity (`Q=0.118 mm`) but not correspondence (cross-sectional `5.084 mm` vs boundary `2.038 mm`, longitudinal `7.744 mm` vs boundary `2.909 mm`).
- Added damped transport for internal skeletal query points so dense boundary matching does not freely drag the medial coordinate system and destroy anatomical landmark identity.

### [2026-06-04 12:50] - none
- Continuing audit found that the previous `core_claim` claim depended on a reduced synthetic prototype and a preserved mesh-order registration path, which is not a defensible reproduction of the paper's actual procedure.
- Removed the vertex-order registration shortcut, made the procedural surfaces order-invariant for future runs, and changed `scripts/run.sh` to regenerate data, baseline outputs, method outputs, full scores, split scores, and validation in one job.
- Host Python lacks `numpy`, so the tightened code path is being submitted for container validation before claiming `method_runs` again.

### [2026-06-04 12:20] - core_claim
- Implemented a reduced-scale HippMetric pipeline with skeletal template coordinates, dense Gaussian-kernel deformation, paired spoke refinement, and baseline-anchored longitudinal processing.
- Packaged a procedural hippocampal benchmark with separate evaluation labels and method-visible geometry.
- CPU container jobs validated that HippMetric improves thickness, correspondence, and surface-fidelity metrics over the boundary-driven baseline while preserving valid local measurements.

### [2026-06-04 12:26] - core_claim
- Managed CPU container job `69a1af48-426` reran `scripts/run.sh` end to end and exited successfully.
- The job regenerated full, train, and test score files, and `python validate.py --compare` reported all checks passed.
- Final milestone remains `core_claim`; higher milestones need unavailable clinical/template/manual landmark resources.

## Stop Justification
- Not stopping yet. Current validated milestone is `method_runs`; `core_claim` requires a follow-up validation showing HippMetric improves the scored correspondence metrics over the boundary baseline after removing vertex-order dependence.
