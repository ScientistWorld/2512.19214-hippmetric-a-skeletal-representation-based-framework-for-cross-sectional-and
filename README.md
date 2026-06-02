# Overview

- **Paper ID:** 2512.19214
- **Title:** HippMetric: A skeletal-representation-based framework for cross-sectional and longitudinal hippocampal substructural morphometry
- **Domain:** Medical imaging / computational anatomy
- **TL;DR:** HippMetric measures hippocampal subfield morphology using an internal skeletal coordinate system that improves correspondence and longitudinal stability over boundary-driven shape models.

## Short Summary

The paper addresses hippocampal morphometry, where local subfield changes are clinically meaningful but hard to compare across subjects and time. HippMetric builds on ARMM and skeletal representations to define lamellar coordinates and paired spokes from an internal skeleton to the surface. The paper reports lower correspondence errors than cm-rep, ds-rep, and SPHARM-PDM, stable reconstruction under Alzheimer's disease atrophy, and stronger disease prediction than volumetric biomarkers.

## Key Results

- HippMetric cross-sectional correspondence errors are reported below about `1.66 mm`; competing models reach up to `9.97 mm`.
- Longitudinal simulated atrophy correspondence averages `1.68 mm` for HippMetric versus `3.56-10.57 mm` for baselines.
- HippMetric-derived substructural features reach GHABS validation AUC `0.861` for cross-sectional classification and `0.774` for conversion prediction.

---

# Problem Definition

## Research Question

The task is to produce reliable hippocampal substructure morphometry from 3D hippocampal segmentations or surfaces. A successful system should estimate local subfield thickness and preserve point-wise anatomical correspondence across different subjects and longitudinal scans, including scans with localized atrophy.

## Why It Matters

Hippocampal atrophy is a major imaging biomarker in aging and Alzheimer's disease. Global volume measures miss localized subfield and long-axis changes, while unstable correspondences can turn segmentation noise into false biological signal.

## Success Criteria

A good solution should produce accurate local thickness estimates, low landmark correspondence error across subjects and time, and stable surface reconstruction quality under atrophy-like shape changes. It should also maintain a valid measurement field rather than improving one metric by producing degenerate or invalid local measurements.

---

# Paper's Method

## Key Contribution

HippMetric is a skeletal-representation framework for hippocampal substructural morphometry. It extends the ARMM coordinate system to subfields and longitudinal data so measurements are indexed by an internal lamellar skeleton rather than by unstable boundary parameterizations.

## Approach

The paper builds a hippocampal template with skeletal surfaces and paired superior/inferior spokes. Subject processing reconstructs and refines subfield surfaces, maps the template skeleton into each subject, and iteratively refines spoke endpoints and directions. The spoke refinement enforces boundary convergence, normal alignment, paired-spoke symmetry, and non-intersection/validity constraints. Thickness is computed from valid spoke lengths, while longitudinal follow-ups reuse the baseline skeletal coordinate system and re-optimize spoke lengths to represent tissue loss or growth.

This reproduction implements the core computational steps at small scale: lamellar template coordinates, subject-specific skeletal transformation, paired superior/inferior spokes, iterative boundary and normal refinement, baseline-anchored longitudinal spoke optimization, local thickness extraction, and geometric validity reporting.

## Main Claims

Primary claim: an internal skeletal/lamellar coordinate system with geometry-preserving spoke refinement yields more stable cross-sectional and longitudinal correspondence than boundary-driven shape models.

Secondary claims: local subfield thickness can be measured with sub-voxel-scale error, reconstruction quality remains stable under atrophy, and the resulting features are useful for Alzheimer's disease classification and prognosis.

---

# Evaluation

## Metrics

The evaluation uses millimeter-scale geometric errors and a validity constraint:

- `thickness_mae_mm`: mean absolute error between predicted and reference local subfield thickness. Lower is better.
- `cross_sectional_correspondence_error_mm`: Euclidean error between predicted and reference landmarks for baseline scans. Lower is better.
- `longitudinal_correspondence_error_mm`: Euclidean error between predicted and reference landmarks under follow-up atrophy. Lower is better.
- `surface_Q_mm`, `surface_q_mm`, `surface_HD_mm`: mean, maximum, and Hausdorff nearest-surface distances between reconstructed and observed surfaces. Lower is better.
- `valid_spoke_fraction`: fraction of local measurements that remain geometrically valid. Higher is better.

## Baselines and Targets

The paper reports HippMetric correspondence errors of about `1.66 mm` cross-sectionally and `1.68 mm` longitudinally, with competing shape models ranging from `3.41 mm` to `9.97 mm` cross-sectionally and `3.56 mm` to `10.57 mm` longitudinally. It also reports subfield thickness errors below `0.5 mm` and robust reconstruction under pathology, with HippMetric CI `HD` around `1.809 mm`.

This workspace uses a small procedural benchmark because the clinical ADNI/GHABS labels, manual landmarks, and supplemental tables are not packaged. The same metric definitions are retained, and the evaluator compares method outputs against known procedural ground truth.

## Evaluation Protocol

Run `bash scripts/reproduce.sh` to generate the benchmark data, run the boundary baseline, run the reproduced method, and write `scoring/scores.json`. `scripts/evaluate.sh` is method-independent: it reads output files from `checkpoints/` and only imports code from `eval/`.

`scoring/reference.json` contains the expected packaged-benchmark values, not the clinical paper table values, so automated comparison checks the reproducible environment at the same scale as `scores.json`. The paper's clinical values remain listed above as external targets.

---

# Reproduction Log

### Iteration 1: gpt-5.5
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 6m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

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

</details>


---

# Reproduction Milestones

**Current: core_claim**

## Stop Justification
- Completed at milestone `core_claim`.
