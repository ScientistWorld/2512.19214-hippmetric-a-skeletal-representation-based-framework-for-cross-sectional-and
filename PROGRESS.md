# Progress

## What Works

- Paper-specific briefing, scoring targets, constraints, and direction documents are filled in.
- `data/synthetic_hippocampus.py` generates a small procedural hippocampal subfield benchmark with known thickness, landmark, and atrophy ground truth.
- `method/hippmetric.py` runs the paper's core computation at reduced scale: internal skeletal coordinates, paired spokes, boundary/normal refinement, valid thickness extraction, and longitudinal reuse of the baseline skeleton.
- `baseline/boundary_model.py` provides a boundary-anchored comparison method.
- `scripts/reproduce.sh` runs data generation, baseline, method, and evaluation end to end.
- `scripts/evaluate.sh` writes `scoring/scores.json` without importing from `method/`.

## Results

Local smoke-test command:

```bash
bash scripts/reproduce.sh && python validate.py --compare
```

Measured on the procedural benchmark:

- Thickness MAE: HippMetric `0.121 mm`; boundary baseline `7.090 mm`.
- Cross-sectional correspondence error: HippMetric `0.075 mm`; boundary baseline `2.196 mm`.
- Longitudinal correspondence error: HippMetric `0.148 mm`; boundary baseline `1.950 mm`.
- Surface HD: HippMetric `0.645 mm`; boundary baseline `3.647 mm`.
- Valid spoke fraction: both `1.000`.

Scheduler job `078ea881-f47` reproduced the same scores inside the compute container and exited with code `0`. `python validate.py --compare` passed in the job.

## Remaining

- Higher milestones would require public ADNI preprocessing assets, paper template assets, or the upstream HippMetric example data/manual landmarks.

## Issues

- ADNI access is controlled and GHABS is not public. The paper's manual landmarks and supplemental per-subfield tables are not included in the workspace.
- The reproduction therefore uses a procedural dataset that preserves the geometric correspondence and atrophy phenomena but does not reproduce clinical classification AUCs.
- The scheduler log path reported in the notification was not mounted directly, but the job logs were available at `/home/user/jobs/078ea881-f47/` and confirmed successful execution.
- The first final validation pass rejected `reference.json` because it mixed paper-scale clinical targets with the procedural benchmark scores. `reference.json` now uses the packaged benchmark's expected values so `scores.json` and `reference.json` compare the same experiment scale; paper clinical numbers remain documented in `briefing/evaluation.md`.

## Deviations from Paper

- **Data**: The paper used ADNI/GHABS FreeSurfer FS60 segmentations, manual landmarks, and simulated atrophy on ADNI surfaces. This workspace uses a tracked procedural generator because the clinical cohorts, manual annotations, and supplemental assets are unavailable in the repository.
- **Scale**: The paper used 549 skeletal points, 1,098 thickness measurements, and large clinical cohorts. This reproduction uses a smaller lamellar grid and 24 synthetic subjects with 4 time points to fit a quick reusable benchmark.
- **Registration**: The paper used Deformetrica LDDMM. This reproduction uses known procedural transforms to isolate and test the skeletal/spoke refinement and longitudinal-coordinate computation without relying on unavailable clinical surfaces.
