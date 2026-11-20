# Hardening Report (final iteration)

## Starting point

The gym had already been hardened once; see `redteam/hardening/results_iter3/` for that audit. `REVIEW.md` named two remaining weaknesses:

1. All anatomy was a hand-written procedural sheet.
2. The only demonstrated gain was tuning.

It asked for:
- real hippocampus labels as the baselines of held-out subjects;
- follow-ups made inside `eval/test/` with hidden, known thinning along the true normals plus smooth warps;
- the paper's longitudinal correspondence and thickness-change errors scored on them, with the reference and the boundary-driven baseline run end to end;
- a check that a method better than tuning beats the reference there beyond noise.

`REDTEAM.md` describes the gym before the first hardening. All of its major shortcuts had been closed by that hardening and stay closed (table below).

## What changed

**Real-anatomy cohort.**
- **Source data.** Baselines are real manual hippocampus labels from the Medical Segmentation Decathlon Task04: Vanderbilt, CC-BY-SA 4.0, 260 labelled cases at 1 mm, label 1 = head, label 2 = body/tail. `scripts/download.sh` fetches them from the public MONAI mirror (md5-checked).
- **Split.** `data/msd_hippocampus.py` holds out every 8th case, 32 in all. They are stored only in `eval/test/real_heldout.npz`. The other 228 are the development set (`data/hippo_real_anatomy.npz`).
- **Template.** `data/build_real_template.py` builds `data/hippo_real_template.npz` from the 228 development labels:
  - rigid ICP to the median subject, then averaging of signed distance fields, two rounds (mean residual 0.65 mm);
  - a 61 × 9 lamellar grid along the curved long axis from head to tail;
  - spokes are the chords of the mean shape along each lamella's normal;
  - head/body/tail subfield ids come from the averaged MSD head label.
  `eval/test/real_template.npz` is a fixed copy that the hidden gate uses.
- **Follow-ups.** `eval/test/real_cohort.py` builds three follow-ups per subject at evaluation time, each with:
  - progressive erosion of the head along the true boundary normals (one or two anisotropic bumps, peak 1.0–1.7 mm at t3), plus 0.03 mm per timepoint everywhere;
  - an independent multi-scale smooth warp per follow-up (8–14 Gaussian displacement fields, widths 10–18 mm, Jacobian norm ≤ 0.12);
  - a new pose;
  - the same segmentation noise as the procedural cohort.
  The development split uses a separate copy, `eval/train/real_cohort.py`, with a public seed and 32 development subjects. The test seed exists only in `eval/test/evaluate.py`.
- **Scoring follows each method's own anatomy.** Each submitted baseline endpoint is projected onto the true baseline boundary. Its true follow-up position is that point moved inwards along the true normal by the erosion there, then warped and posed. From these the evaluator computes:
  - `real_longitudinal_correspondence_error_mm` (+ p95): inside the atrophic region, where erosion is ≥ 30 % of its peak;
  - `real_stable_correspondence_error_mm`: outside it (< 5 %), where only the warp and pose act;
  - `real_thickness_change_error_mm`: the spoke's measured change against the true change of the same spoke;
  - `real_surface_Q_mm` and `real_valid_spoke_fraction`.
- **Gates for the real cohort.** A run fails on the real cohort if:
  - its validity is below 0.5;
  - its longitudinal correspondence or surface RMS is no better than the template placed at the segmentation centroid;
  - its thickness change is no better than reporting no change on its own spokes (1e-6 mm margin, so reused baseline lengths cannot pass on floating-point noise).

**Interface.**
- Every predictor is called once per cohort. The input's `cohort` entry selects the template (`hippo_io.template_path`).
- A crash, invalid output or failed gate in either cohort gives the worst value in every metric of every experiment.
- Non-finite raw values are written as `null`.
- The per-call timeout is 2 h; the reference needs about 3 min per cohort, so wall-clock load cannot change its scores.

**Scoring (`scoring/reference.json`).**
- The real-anatomy metrics are filed under the experiment each one measures:
  - `real_thickness_change_error_mm` (|coef| 0.8) and `real_valid_spoke_fraction` (0.3) → `subfield_thickness_accuracy`;
  - `real_longitudinal_correspondence_error_mm` (1.0), its p95 (0.4) and `real_stable_correspondence_error_mm` (0.5) → `correspondence_stability`;
  - `real_surface_Q_mm` (0.6) → `surface_robustness`.
- Experiment weights stay 0.25 / 0.50 / 0.25.
- The paper's simulated-atrophy numbers (1.68 mm vs 3.56–10.57 mm) stay on the procedural `longitudinal_correspondence_error_mm`. They are not targets for the real-anatomy metrics: the paper scores against manual landmarks, while the gym scores against exact positions and adds warps (note in `reference.json`).
- An earlier draft used a separate fourth experiment. `validate.py` needs a paper value on each experiment's primary metric, and no paper value is on this scale. The fourth experiment was therefore folded into the three existing ones. Values are identical; the saved score files were regrouped with `redteam/hardening/regroup_scores.py`, and the final job reran the evaluators from the final code.

**Method.**
- The reference is unchanged. It is the paper's procedure: follow-ups are rigidly registered to the baseline, baseline spokes are reused and lengths re-measured.
- It now loads the template of the input's cohort.
- Two audit options were added:
  - `--nonrigid-followups` (variant): a wide-kernel Gaussian flow from baseline to follow-up after the rigid step, carrying skeletal points and spoke ends, then lengths are re-measured;
  - `--static-followups` (ablation): no re-measurement on follow-ups.

## Reference score

The procedural-cohort reference outputs did not change; values are identical to the previous hardening.

| Hidden test | thk MAE | Δthk | valid | cross | long | Q | HD | **R:long** | R:long p95 | R:stable | R:Δthk | R:Q | R:valid |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HippMetric (before) | 0.510 | 0.686 | 0.907 | 2.236 | 1.888 | 0.598 | 3.111 | – | – | – | – | – | – |
| HippMetric (after) | 0.510 | 0.686 | 0.907 | 2.236 | 1.888 | 0.598 | 3.111 | **0.678** | 1.510 | 0.593 | 0.482 | 0.921 | 0.930 |
| Boundary baseline (after) | 0.588 | 0.731 | 0.952 | 3.777 | 2.940 | 1.844 | 7.687 | **1.133** | 2.690 | 0.759 | 0.434 | 1.314 | 1.000 |
| Trivial (gate) | 0.614 | 1.086 | – | 4.009 | 3.456 | 2.104 | – | 2.235 | – | – | 0.879 (no change) | 2.851 | – |

On train (development), HippMetric scores R:long 0.641, stable 0.508, Δthk 0.472, Q 0.936, valid 0.931. The boundary baseline scores 0.907 / 0.746 / 0.417 / 1.368 / 1.000. Train and test agree within sampling error.

**Paper direction on real anatomy.** These are paired over the 32 held-out subjects, as baseline minus reference:
- longitudinal correspondence in the atrophic region: +0.424 ± 0.080 mm;
- stable region: +0.173 ± 0.037;
- surface Q: +0.393 ± 0.039.

The boundary-driven model, which refits each scan independently, slides its points; the anchored skeletal model does not. The same holds for the skeletal method refitted independently: `hm_independent_followups` is +0.426 ± 0.047 mm worse.

**Exception.** On real anatomy the boundary baseline measures thickness change about as well as the reference: −0.030 ± 0.029 on test and −0.059 ± 0.023 on train, slightly better. It also keeps validity 1.0, because its endpoints are snapped to the observed surface. The paper's thickness claim is therefore reproduced on the procedural cohort (0.510 vs 0.588 MAE; 0.686 vs 0.731 Δthk) but not on the real-anatomy thickness change. The reference's rigid-only follow-up registration measures along slightly misplaced spokes when the follow-up is warped. The nonrigid variant (0.363) and length smoothing (0.386) both beat the baseline there.

## Do better results score higher?

The rank rule (Δ) is: weight × |coef| × improvement in the metric's better direction ÷ population SD across the audited attempts. `d_ok` uses successful attempts only; failed attempts carry worst values. "Before" is the previous hardening's audit, with different weights and no real-anatomy metrics.

| Attempt | Before Δ test | After Δ test | After Δ train | Paired test effect vs reference (real anatomy) |
|---|---|---|---|---|
| **Better, not tuning: nonrigid follow-up registration** (`hm_nonrigid_followups`) | – | **+0.417** | +0.425 | R:long −0.129 ± 0.026, R:stable −0.189 ± 0.012, R:Δthk −0.110 ± 0.017; R:Q +0.043 ± 0.003 |
| Nonrigid + length smoothing | – | +0.838 | +0.747 | R:long −0.120 ± 0.026, R:Δthk −0.159 ± 0.021 |
| Tuning: length smoothing + finer registration (`hm_smooth10_fine`) | +1.007 | +1.190 | +0.853 | R:Δthk −0.094 ± 0.006; procedural cross −0.101 ± 0.012, long −0.129 ± 0.021 |
| Tuning: length smoothing σ = 1 | +0.411 | +0.600 | +0.507 | R:Δthk −0.101 ± 0.007 |
| Honest alternative: refit follow-ups independently | +0.167 | **−0.821** | −1.116 | R:long +0.426 ± 0.047, R:stable +0.176 ± 0.024 |
| Weaker: remove nonlinear deformation (`hm_no_dense`) | failed gate | failed gate | −3.322 | R:Q +0.124 ± 0.023 |
| Weaker: boundary-driven baseline | −6.245 | −7.704 | −7.714 | see above |

The nonrigid follow-up registration changes a fitting step, not a tuning parameter. Its gains are 5–16 SE on the real-anatomy longitudinal metrics. It loses a little surface Q (+0.043 mm real; +0.067 ± 0.041 procedural), and still ranks above the reference on both splits. It is also the direction the paper leaves open: it registers follow-ups only rigidly.

Independent refitting looked like a small improvement before (+0.167). On real anatomy it now ranks clearly below the reference, as the paper's anchored-follow-up argument predicts. The method is deterministic and the cohorts are fixed, so seed noise is zero; the SEs above are subject-sampling noise.

## Major shortcuts: fix and score before → after (hidden test)

| Shortcut | Before | After |
|---|---|---|
| Copy, replay or replace visible labels (REDTEAM) | closed by the previous hardening | closed. Test labels exist only in the evaluator process; the real-anatomy held-out cases live only in `eval/test/` |
| Remove nonlinear deformation | failed gate | failed gate (procedural thickness 0.620 ≥ trivial 0.614) |
| Zero thickness / template only / NaN / huge values / crash / missing output / reversed point order | failed → worst | failed → worst. Real-cohort gates fire as well, e.g. zero thickness: real validity 0.18; template only: real longitudinal 2.235 = trivial |
| **New: reuse baseline spoke lengths on follow-ups** (`sc_static_followups`) | – | **failed → worst**: thickness change = no change in both cohorts |
| Template thickness instead of measurement | −0.394 | **−1.407** (R:Δthk +0.200 ± 0.035, R:long +0.272 ± 0.028) |
| Snap endpoints to the raw segmentation surface | −0.642 | −0.831 (fails the gate on train) |
| Old generator label drift (0.84 mm × t) | −1.916 | −5.252 |

Forged score files, inflated baselines, whitelisting through `scores_train.json`, and reported (not computed) validity all remain harmless. The evaluator never reads them. Every `scripts/predict_*.sh` is scored, and the score file is written fresh and atomically.

## Headroom

The reference sits at the bound of no scored metric:
- validity is 0.907 procedural and 0.930 real;
- every error is well above 0;
- the real-anatomy longitudinal error (0.678 mm) is far above the segmentation-noise floor.

A change of fitting step (nonrigid follow-up registration) beats the reference beyond noise, and combining it with length smoothing goes further. No simple baseline outranks the reference. The boundary baseline is at the validity bound (1.0), but it is the baseline, and it loses overall by −7.7.

No brute-force analogue applies. The observations are segmentations, and per-scan nearest-boundary matching is the boundary baseline. The trivial references (constant thickness, no change, template at the centroid) all fail the gate.

## Shortcuts and limits left, stated plainly

- **Hidden files are readable while predictors run.** The procedural generator, the real-cohort generator, the held-out labels and the seeds all sit in `eval/test/` inside the test container. A predictor could read them and regenerate the answers. This cannot be prevented inside one container; the separate grader must catch any read of `eval/test/`.
- **Held-out baselines are public.** The MSD archive in `data/downloads/` contains the held-out cases' clean 1 mm labels, and the split rule is public. A predictor could match a test baseline to its MSD case and use the clean label; the follow-up changes stay hidden. This is forbidden in `scoring/CONSTRAINTS.md` and left to the grader. The gain is limited to baseline surface fidelity.
- **The follow-up change model is synthetic and visible.** `eval/train/real_cohort.py` shows the form of the change: Gaussian-bump erosion of the head, Gaussian multi-scale warps. A method could hard-code that parametric family instead of registering generally. General nonrigid registration already captures most of the gain. Fitting the generator's exact form should be treated by the grader as overfitting to the benchmark.
- **Atrophy is milder than the paper's simulation.** The paper erodes the anterior region until spokes approach zero length. Here the peak erosion is 1.0–1.7 mm on a head roughly 8 mm thick, so collapse to zero thickness is not tested. Deeper erosion would make tissue vanish, and per-spoke truth would then be undefined.
- **Real anatomy has no cross-sectional correspondence truth.** MSD has only a head vs body/tail split. The head/body mismatch of the transported template labels is reported as an unscored diagnostic (`real_head_label_mismatch`: 0.024 reference vs 0.027 baseline on test). Cross-sectional correspondence is scored on the procedural cohort only.
- **Real-anatomy thickness change does not favour the reference.** See "Reference score" above. This is a finding, not a defect: it is headroom that better follow-up registration closes.
- **Not reproduced:** FreeSurfer FS60 subfields and the Voronoi/NURBS ARMM template (replaced by procedural and mean-shape chordal templates), Deformetrica's geodesic LDDMM (greedy Gaussian-kernel flow), manual landmarks, ICC reproducibility, compactness, and the AD classification and prognosis analyses.
- **`validate.py` warns** that `eval/test/hidden_cohort.py` and `eval/{train,test}/real_cohort.py` "regenerate the experiment". This is intended: the evaluators generate inputs and truth, then score the predictor outputs.

## Reproduce

- `bash scripts/run.sh` runs the reference reproduction (`scripts/reproduce.sh`: train, full and hidden-test scores for HippMetric and the boundary baseline on both cohorts) and then `validate.py`.
- `bash redteam/hardening/job.sh` reruns this iteration's audit: it rebuilds the real-anatomy files if they are missing, runs the smoke test, the reference run, and every variant and shortcut on both splits. Results are in `redteam/hardening/results/`; earlier rounds are in `results_iter1..3/`.
