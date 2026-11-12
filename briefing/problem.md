# Problem Definition

## Research Question

Given a 3D binary segmentation of a hippocampus (one per scan, on a 0.5 mm grid), place a fixed anatomical coordinate system into it: for every point of a fixed template sheet (61 lamellae along the long axis x 9 positions across it), report where that anatomical point lies in the scan and how far the tissue extends from it towards the superior and inferior boundary. From this, local thickness is read off at anatomically corresponding positions across subjects, and across a subject's follow-up scans while tissue is being lost.

## Why It Matters

Hippocampal atrophy is a major imaging biomarker in ageing and Alzheimer's disease, and it is regional (subfield- and long-axis-specific). Global volumes miss it. Local measurements are only comparable across people and over time if the same anatomical location is measured each time; segmentation noise and shape variability make that hard, and correspondence that drifts as tissue disappears turns real atrophy into apparent shape change.

## Data

- `data/hippo_template.npz`: the template (skeletal points, superior/inferior directions and extents, lamellar coordinates, subfield ids, template segmentation).
- `data/hippo_train.npz`: development cohort of 32 subjects x 4 timepoints (baseline + 3 follow-ups). Subjects differ in shape, size, pose and thickness pattern; about half carry baseline regional thinning; follow-ups lose tissue in a subject-specific region. Segmentations contain boundary inconsistencies, label noise, islands and holes.
- `data/hippo_train_labels.npz`: ground truth for the development cohort.
- The scored test cohort (32 subjects x 4 timepoints from the same population) is not distributed; predictors are run on it by the hidden evaluator.

## Success Criteria

Accurate local thickness and thickness change, low point-wise correspondence error across subjects and across a subject's follow-ups, and an implied boundary that stays on the true anatomy, while keeping the local measurement geometry valid (endpoints on the boundary, no crossing measurement directions).
