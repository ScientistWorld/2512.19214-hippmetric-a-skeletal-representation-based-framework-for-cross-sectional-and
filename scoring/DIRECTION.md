# Research Direction

## Research Problem

Anatomically consistent local morphometry of the hippocampus from noisy 3D segmentations: placing a fixed lamellar coordinate system into each subject and each follow-up scan, and measuring local thickness and its change at corresponding locations, on procedural and real hippocampal anatomy.

## Core Contribution Sought

Better correspondence across subjects and over time (both where tissue is lost and where the follow-up is only deformed), more accurate local thickness and thickness change, and an implied boundary that follows the true anatomy rather than the segmentation noise.

## Approach Scope

In scope: registration and deformation models (template-to-subject and follow-up-to-baseline), use of interior (skeletal) versus boundary information, surface reconstruction and denoising, spoke/measurement optimisation, longitudinal modelling of tissue loss, templates and statistical shape priors learned from the development data.

## Out of Bounds

Reading or reconstructing the hidden evaluation cohorts or evaluator code under `eval/test/`; looking up held-out cases in the public MSD archive; reporting thickness or positions that ignore the subject's anatomy; changing the evaluator.
