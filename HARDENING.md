# Hardening Report (final iteration)

The red-team audit (`REDTEAM.md`) found that the previous gym rewarded label access and generator conventions, not better morphometry:

- Test answers were readable or regenerable. Copying the labels scored all nine errors at 0.
- Observed vertices *were* the ground-truth spoke endpoints shuffled, so enumeration recovered exact correspondence.
- The reproduced method's nonlinear deformation was disabled (`query_step_scale=0`), so removing it tied exactly.
- Longitudinal labels carried a generator-only drift.
- Copying the input surface scored perfect reconstruction.
- Failed runs aborted the scorer instead of being scored.

Patching those individually would have left a test with no anatomical registration problem. This iteration therefore rebuilt the benchmark, the evaluator and the reproduction together, then audited them in three CPU jobs. The final job is `bd2946ea-fce`. Evidence for every number below is in `redteam/hardening/results/`. Earlier rounds are in `results_iter1/` and `results_iter2/`.

## What changed

**Benchmark (`eval/test/hidden_cohort.py`, kept on the evaluation side).**
- Each subject is a curved, cupped, twisted lamellar sheet with superior/inferior half-thickness fields. Subjects differ from the public template by nonlinear shape changes: arc geometry, width profile, head position, cupping, thickness modes, head digitations and a random smooth 3D warp. They also differ by scale and scanner pose.
- About half carry regional disease-like thinning at baseline, mirroring the paper's CU/CI contrast.
- Follow-ups (t1–t3) progressively erode a subject-specific anterior region along the true skeletal normals, as in the paper's simulated-atrophy study. The anatomy is what moves, so the labels follow the anatomy.
- A method sees **only a 0.5 mm binary segmentation**, with smooth boundary perturbations, voxel label flips, islands and holes. The paper's pipeline input is likewise a segmentation resampled to 0.5 mm.
- Ground truth: skeletal points, boundary points, thickness, atrophic region and a dense clean boundary.
- Template: 61 × 9 = 549 skeletal points and 1,098 spokes, the paper's template size.
- Public files: `data/hippo_template.npz`, and a 32-subject × 4-timepoint development cohort with labels (`data/hippo_train*.npz`, development seed).
- The 32 × 4 test cohort is generated inside `eval/test/` at evaluation time with a seed that exists only there.

**Interface and evaluator.**
- A method is any `scripts/predict_<name>.sh IN OUT`. It returns, per scan and template index, the skeletal point and the superior/inferior spoke endpoints.
- `eval/train/evaluate.py` and `eval/test/evaluate.py` (no shared code) discover every predictor on disk and run it. They recompute every number from those coordinates:
  - thickness (sum of spoke lengths), subfield means, and the longitudinal thickness change;
  - correspondence to the true point with the same index;
  - distances of the implied boundary to the *clean* true boundary;
  - validity: endpoint within 1 mm of the true boundary, with no endpoint-order reversal.
- The test writes only segmentations to a temp file; labels never leave the process. Outputs are deleted after scoring, because container `/tmp` is a 64 MB tmpfs.
- **Failure rule.** A run fails if it crashes, times out, writes missing, malformed, non-finite or absurd (>10⁴ mm) output, or has validity below 0.5. It also fails if it does no better than evaluator-side trivial references on thickness (per-scan constant), thickness change (no change), cross-sectional or longitudinal correspondence (template at the segmentation centroid), or surface RMS. A failed run gets the worst value of **every** scored metric of **every** experiment. The trivial references use a template regenerated inside `eval/test/`, never the editable data file.

**Reproduction restored to the paper's method (`method/hippmetric.py`).**
- RBOS-style refinement: shrink-wrap closing, hole filling, largest component, voxel-boundary mesh, Taubin smoothing.
- Multi-start similarity alignment.
- Gaussian-kernel diffeomorphic deformation, kernel width 7 → 3 mm in 0.5 mm steps until the mean surface distance is below threshold. It now *does* transport the internal skeletal and implied-boundary landmarks.
- Spoke refinement with the paper's three ray/mesh cases (Fig. 3B): E0, and E1 at 0.1 rad steps for up to 50 iterations, for three rounds; then E2 length symmetry and a final E0.
- Baseline-anchored follow-ups: rigid follow-up→baseline registration, baseline spokes reused, lengths re-optimised.

**Baseline (`baseline/boundary_model.py`).** The previous one paired halves of a PCA-sorted list; it is replaced by a meaningful boundary-driven control. Each scan is fitted independently: similarity fit, then nearest-boundary projection of the template's implied boundary points. There is no skeleton, no nonlinear deformation and no anchoring.

**Scoring (`scoring/reference.json`).**
- Experiment weights are unchanged (thickness 0.25, correspondence 0.50, surface 0.25).
- Added `longitudinal_thickness_change_error_mm` (|coef| 0.6, also gated). Without it, a method that ignores the subject's measured anatomy (template thickness) won on thickness. It measures the paper's "capture true tissue loss" claim.
- Added `subfield_mean_thickness_error_mm` (|coef| 0.5): the paper's subfield statistic D.
- Surface metrics are now Q = RMS 0.8, HD = max of directed distances 0.6 (the paper's definition, without the old factor 2) and p95 0.5. The coefficient-zero `surface_q_mm` was dropped. HD is a single-point maximum, so it gets less weight than the RMS.
- `valid_spoke_fraction` is counted once, in the thickness experiment, instead of three times.
- Paper numbers are unchanged. Those not on this setup's scale (the paper's Q normalisation, q, and the competitor surface values) moved to `_paper_*` keys and `_paper_reported`.

## Reference score

| | thickness MAE / p95 | subfield D | Δthickness err | validity | cross / p95 | longitudinal / p95 | Q / HD / p95 |
|---|---|---|---|---|---|---|---|
| Before (old gym, test) | 0.334 / 0.864 | – | – | 1.000 | 0.493 / 1.183 | 1.636 / 2.920 | 0.411 / 2.479 / 0.789 |
| After, test (`scores_test.json`) | 0.510 / 1.495 | 0.283 | 0.686 | 0.907 | 2.236 / 6.540 | 1.888 / 4.388 | 0.598 / 3.111 / 1.356 |
| After, train (`scores_train.json`) | 0.482 / 1.437 | 0.268 | 0.640 | 0.914 | 2.101 / 5.343 | 1.707 / 4.241 | 0.534 / 2.913 / 1.151 |
| Boundary baseline, test | 0.588 / 1.606 | 0.287 | 0.731 | 0.952 | 3.777 / 9.324 | 2.940 / 7.175 | 1.844 / 7.687 / 4.870 |

The before and after numbers come from different benchmarks and are not comparable value-for-value. The old errors were low partly because the old problem was trivially recoverable.

The reproduction shows the paper's claims in the paper's direction. HippMetric beats the boundary-driven model on every error metric:
- cross-sectional correspondence by 1.54 ± 0.22 mm;
- longitudinal correspondence by 0.98 ± 0.22 mm;
- surface Q by 1.25 ± 0.17 mm;
- thickness by 0.078 ± 0.026 mm.

All are paired over 32 hidden subjects. The baseline keeps a higher validity because its endpoints are snapped onto the observed surface. Paper anchors (`validate.py` deviation check passes):

| Metric | Paper | Here (test / train) |
|---|---|---|
| Thickness | < 0.5 | 0.51 / 0.48 |
| Longitudinal correspondence | 1.68 | 1.89 / 1.71 |
| CI HD | 1.81 | 3.11 / 2.91 |

## Do better results score higher?

Δ is the gym's rank rule. For each scored metric, it sums weight × |coef| × improvement in the metric's better direction ÷ the population SD over the audited attempts. Two populations are used:
- *successful attempts* (`d_ok`);
- *all attempts*, where failed runs carry worst values (`d_all`).

These depend on the audit population; the paired per-subject differences (mean ± SE, same hidden subjects) do not.

| Attempt | Before Δ (REDTEAM) | After Δ test (d_ok / d_all) | After Δ train | Paired test effect vs reference |
|---|---|---|---|---|
| Better: smoothing + finer registration (`hm_smooth10_fine`, train-selected) | +0.030 (old smoothing) | **+1.007 / +0.041** | +0.581 | thickness −0.031±0.006, Δthk −0.072±0.013, cross −0.101±0.012, long −0.129±0.021, Q −0.023±0.009, HD −0.177±0.048 |
| Smoothing σ=1.5 / 1.0 / 0.5 | – | +0.476 / +0.411 / +0.198 | +0.317 / +0.256 / +0.129 | thickness −0.021±0.005 (σ=1.5) |
| Weaker: remove nonlinear deformation (`hm_no_dense`) | **0 (exact tie)** | **failed gate** (thickness 0.620 ≥ trivial 0.614) | −3.048 | cross +0.593±0.062, long +0.634±0.099, Q +0.243±0.042 |
| Weaker: boundary-driven model | −3.927 | −6.245 / −0.400 | −6.708 | see above |
| Honest alternative: refit follow-ups independently | – | +0.167 / −0.015 | −0.307 | thickness −0.041±0.008, long +0.073±0.091, Q +0.082±0.069 |

Every paired effect of the better variant exceeds its SE by a factor of 2.5–12. The method is deterministic and the hidden cohort is fixed, so seed noise is zero. The remaining noise is the subject sampling these SEs measure. Train and test agree within sampling error (cross 2.10 ± 0.16 vs 2.24 ± 0.23 mm), and the variant chosen on train is also the best on test.

## Major shortcuts: fix and score before → after

| Shortcut | Before | Fix | After (test) |
|---|---|---|---|
| Copy visible labels | +1.621, all errors 0 | Test labels exist only in the test process; `data/` holds only the development cohort | Closed by construction (nothing to copy) |
| Replay visible generator | +1.621 | Generator and test seed live only in `eval/test/` | Closed by construction |
| Replace label file | +0.895 | Test evaluator never reads `data/` labels | Closed by construction |
| Generator label drift (0.84 mm × t) | +0.338 | Longitudinal labels follow the eroded anatomy | **−1.916** (long +0.759 ± 0.111) |
| Copy input surface as reconstruction | +0.726 | Surface scored from the s-rep endpoints against the clean true boundary | Snap endpoints to raw segmentation surface: **−0.642** (train: fails gate) |
| Remove nonlinear deformation | 0 (tie) | Benchmark needs nonlinear registration; reference transports landmarks | **Fails gate on test**; −3.048 train |
| Brute-force pair enumeration | +0.122 | Observations are segmentations, not shuffled endpoints | Not expressible; nearest-boundary matching (baseline) −6.245 |
| Zero thickness + copied surface | +0.224 | Coherent output + gate | **Failed → worst values** |
| NaN outputs | accepted, conditional +0.726 | Non-finite → failed | **Failed → worst values** |
| Missing output / crash | scorer aborted, stale or empty entries | Per-method failure, worst values, atomic write | **Failed → worst values**, others still scored |
| Whitelist via `scores_train.json` | omitted methods | Every `scripts/predict_*.sh` is scored; `scores_train.json` never read | Closed by construction |
| Impossible validity 1e30 | capped, tie | Validity is computed, never reported | |coords| > 10⁴ mm → **failed** |
| Order-dependent surface metric | −0.005 | Order-free distances to the true boundary; grid order only densifies the implied surface | Reversed point order: **failed** (correspondence 16 mm) |
| Template thickness instead of measurement (new) | – | `longitudinal_thickness_change_error_mm` + gate | **−0.394** (Δthk +0.301 ± 0.071) |
| Template only / constant | −4.876 (passed as valid) | Gate vs trivial references | **Failed → worst values** |

Forged score files and inflated baselines were already harmless and stay so. The evaluator writes the score file atomically and fresh. Neither the baselines nor the gate references come from method-editable code.

## Headroom check

The reference is at the bound of **no** scored metric. Validity is 0.907, and every error is well above 0. A train-selected variant beats it on all eleven error metrics and on validity, and the paired effects exceed noise. The brute-force analogue (nearest-boundary matching for every template point, the baseline) and the rigid-only ablation lose clearly.

No new experiment was needed. The thickness-change metric was added to stop priors that ignore the subject from paying.

## Shortcuts and limits left, stated plainly

- **Hidden generator on disk.** `eval/test/hidden_cohort.py` sits in the test container while predictors run, so a predictor could import it and regenerate the labels. Defending against that inside one container is not possible. The separate grader must catch it.
- **Synthetic substitute data.** The ADNI/GHABS segmentations, manual thickness and manual landmarks are not redistributable. The anatomy family is hand-written. A method could learn a statistical shape model of it from the 32 labelled development subjects. That is a legitimate method on this benchmark, but it may transfer only partly to real hippocampi.
- **Scaled method components:**
  - Deformetrica's geodesic LDDMM is replaced by a greedy composition of small Gaussian-kernel velocity steps, using the same kernel-width schedule.
  - FreeSurfer FS60 subfield surfaces and the Voronoi/NURBS template are replaced by one procedural sheet with five region labels.
  - The paper's 0.1 mm length stepping is solved exactly by ray/mesh intersection.
- **Anchoring evidence is mixed.** Within the skeletal method, baseline-anchored follow-ups beat independent refits on longitudinal correspondence on train (−0.165 ± 0.071) but not significantly on test (−0.073 ± 0.091). Independent refits measure thickness slightly better. The paper's comparison against boundary-driven models holds strongly; this internal design choice does not. A future method can therefore gain by improving follow-up processing, which is a legitimate direction.
- **Hard subjects remain.** Three or four test subjects keep large registration errors (cross 4–6 mm) for every method; this is headroom for more robust registration. Train/test means differ partly because of them, within sampling error.
- **Not reproduced:** the AD classification/prognosis analyses, ICC reproducibility versus HippUnfold, and the compactness analysis.
- **`validate.py` warning.** It warns that `eval/test/hidden_cohort.py` "regenerates the experiment". That is intended: the hidden test generates its inputs and then scores predictor outputs.
- **Old red-team folder.** `redteam/*` outside `redteam/hardening/` is the previous audit of the old gym and refers to files that no longer exist.

## Reproduce

- `bash scripts/run.sh` runs the reference reproduction: baseline and HippMetric on the development cohort, train/full/test scores, then validation.
- `bash redteam/hardening/run_audit.sh` reruns this audit. It installs `redteam/hardening/predictors/*` temporarily, writes `redteam/hardening/results/`, then removes them.
