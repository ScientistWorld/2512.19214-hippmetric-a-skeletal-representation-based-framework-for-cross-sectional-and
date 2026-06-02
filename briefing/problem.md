# Problem Definition

## Research Question

The task is to produce reliable hippocampal substructure morphometry from 3D hippocampal segmentations or surfaces. A successful system should estimate local subfield thickness and preserve point-wise anatomical correspondence across different subjects and longitudinal scans, including scans with localized atrophy.

## Why It Matters

Hippocampal atrophy is a major imaging biomarker in aging and Alzheimer's disease. Global volume measures miss localized subfield and long-axis changes, while unstable correspondences can turn segmentation noise into false biological signal.

## Success Criteria

A good solution should produce accurate local thickness estimates, low landmark correspondence error across subjects and time, and stable surface reconstruction quality under atrophy-like shape changes. It should also maintain a valid measurement field rather than improving one metric by producing degenerate or invalid local measurements.
