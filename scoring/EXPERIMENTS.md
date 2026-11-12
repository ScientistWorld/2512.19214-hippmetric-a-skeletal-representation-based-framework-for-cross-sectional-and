# Experiment Overview

## subfield_thickness_accuracy

Establishes whether a method measures local hippocampal thickness accurately from a noisy segmentation, at anatomically corresponding positions, including subjects with disease-related thinning and follow-ups with progressive tissue loss. It also asks whether the measured change over time matches the true tissue loss, so that a method cannot score well by reporting a population-typical thickness while ignoring the subject's anatomy. A validity constraint checks that thickness comes from geometry that actually reaches the true boundary without crossing measurement directions.

## correspondence_stability

Establishes whether the same anatomical point is found in every subject (cross-sectional) and is tracked within a subject over follow-up scans in the region where tissue is being lost (longitudinal). This is the central claim of the paper: stable point-wise correspondence across individuals and time.

## surface_robustness

Establishes whether the boundary implied by a method's measurements lies on the true anatomy (not on the segmentation noise) for both healthy-like and atrophied scans. It is the constraint that prevents correspondence or thickness from being improved with geometry that departs from the anatomy.
