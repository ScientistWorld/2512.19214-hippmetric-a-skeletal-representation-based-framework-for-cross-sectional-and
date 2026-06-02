# Research Direction

## Research Problem

This benchmark concerns hippocampal substructure morphometry from 3D shape data, especially stable correspondence across subjects and longitudinal atrophy.

## Core Contribution

The research goal is anatomically consistent local morphometry from hippocampal shape data. Improvements should target geometric modeling, correspondence, local thickness estimation, or robustness of hippocampal shape measurements.

## Approach Scope

In-scope work includes better shape parameterizations, more robust surface matching, improved local measurement validity, and stronger handling of longitudinal shape change. Methods may change the geometric optimization strategy as long as they still solve the same hippocampal morphometry and correspondence problem.

## Out of Bounds

Do not switch to a task that bypasses morphometry, such as directly predicting the procedural labels from sample indices. Do not use external clinical labels, larger generated datasets, or leaked ground-truth arrays to improve benchmark scores. Do not replace the evaluation with a method-specific scorer.
