# Verification Report

## Initial Assessment

The prior workspace claimed `core_claim`, but an integrity audit removed a preserved vertex-order correspondence shortcut and shuffled observed surface vertices. CPU jobs `0a0df724-0dd`, `233a513d-e94`, `5e516a21-8cf`, `991e5724-553`, `ddcdaa10-328`, and `f3c6455c-ab9` have now validated tightened order-free paths in the managed container.

All six CPU validation jobs exited successfully and `python validate.py --compare` passed. The result is runnable, but the scientific claim is not yet restored: HippMetric improves thickness and surface fidelity, while correspondence stability is worse than the boundary baseline.

## Issues Found

- **Critical**: Current validated scores do not support `core_claim`. In job `f3c6455c-ab9`, HippMetric cross-sectional correspondence error was `5.081 mm` versus boundary baseline `2.038 mm`, and longitudinal correspondence error was `8.846 mm` versus baseline `2.909 mm`.
- **Cosmetic/system**: `README.md`, `manifest.json`, and tracked `trajectory/` deletions are pre-existing dirty workspace artifacts outside the gym interface. I did not modify or revert them.

## Fixes Applied

- Updated `method/hippmetric.py` to replace many-to-one nearest-neighbor matching with geometric one-to-one linear assignment in rigid alignment refinement and dense Gaussian-kernel deformation.
- After job `233a513d-e94` showed position-only assignment still failed correspondence, added observed surface-normal agreement to PCA sign selection and assignment cost, and uses method-visible normals during spoke refinement.
- After job `5e516a21-8cf` showed normal-aware assignment still failed correspondence, added damped transport for internal skeletal query points so boundary fitting cannot freely drag the medial coordinate system.
- After job `991e5724-553` showed damped internal transport still failed correspondence, updated `method/hippmetric.py` so scored correspondence landmarks are reported from the fitted skeletal coordinate frame, while thickness and surface reconstruction continue to use refined paired spokes.
- After job `ddcdaa10-328` showed coordinate-frame landmark reporting still failed correspondence, updated `method/hippmetric.py` so scored correspondence landmarks are reported from normal-aware, order-free boundary assignment in template index order.
- After job `f3c6455c-ab9` showed direct boundary assignment still failed correspondence, added an atlas-orientation prior to PCA sign selection and uses non-iterated atlas alignment for scored landmark assignment.
- Updated `data/synthetic_hippocampus.py` so surface normals are shuffled with vertices and remain row-aligned.
- Updated `MILESTONES.md`, `PROGRESS.md`, and `CHECKLIST.md` to reflect the honest current milestone: `method_runs`, not `core_claim`.
- Submitting a CPU validation job to regenerate data, outputs, full/train/test scores, and run `python validate.py --compare` for the atlas-prior landmark alignment path.

## Final Judgment

The workspace is not ready for final `done` as a `core_claim` gym yet. It is currently a validated `method_runs` implementation with atlas-prior landmark alignment under test. If the next CPU job shows HippMetric beats the boundary baseline on correspondence while preserving thickness/surface improvements, the milestone can be raised back to `core_claim`.

- Milestone: method_runs
- Ready for gym use: partial
- Confidence: medium
- Key limitation: correspondence claim failed after removing vertex-order dependence; atlas-prior landmark alignment is pending validation
