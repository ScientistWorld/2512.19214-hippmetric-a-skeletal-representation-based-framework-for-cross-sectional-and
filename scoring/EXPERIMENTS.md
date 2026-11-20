# Experiment Overview

Every experiment is measured on two cohorts: a procedural cohort with fully known geometry, and a real-anatomy cohort whose baselines are real (manually labelled) hippocampi and whose follow-ups carry hidden, known changes.

## subfield_thickness_accuracy

Establishes whether a method measures local hippocampal thickness accurately from a noisy segmentation, at anatomically corresponding positions, including subjects with disease-related thinning and follow-ups with progressive tissue loss. It also asks whether the measured change over time matches the true tissue loss, on procedural and on real anatomy, so that a method cannot score well by reporting a population-typical thickness while ignoring the subject's anatomy. A validity constraint on both cohorts checks that thickness comes from geometry that actually reaches the true boundary without crossing measurement directions.

## correspondence_stability

Establishes whether the same anatomical point is found in every subject (cross-sectional, procedural cohort) and is tracked within a subject over follow-up scans: in the region where tissue is being lost (procedural and real anatomy) and, on real anatomy, also where no tissue is lost but the follow-up scan is deformed and re-posed. This is the central claim of the paper: stable point-wise correspondence across individuals and time.

## surface_robustness

Establishes whether the boundary implied by a method's measurements lies on the true anatomy (not on the segmentation noise) for healthy-like, atrophied and real hippocampi. It is the constraint that prevents correspondence or thickness from being improved with geometry that departs from the anatomy.
