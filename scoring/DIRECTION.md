# Research Direction

## Research Problem

This benchmark concerns hippocampal substructure morphometry from 3D shape data, especially stable correspondence across subjects and longitudinal atrophy.

## Core Contribution

The paper's contribution is an anatomy-aligned internal coordinate and spoke-based morphometry framework. Improvements should target geometric modeling, correspondence, local thickness estimation, or robustness of hippocampal shape measurements.

## Approach Scope

In-scope work includes improved skeletal templates, better spoke refinement, more robust surface matching, alternative internal coordinate parameterizations, and validity constraints for local morphometry. Methods may change the geometric optimization strategy as long as they still solve the same hippocampal morphometry and correspondence problem.

## Out of Bounds

Do not switch to a task that bypasses morphometry, such as directly predicting the procedural labels from sample indices. Do not use external clinical labels, larger generated datasets, or leaked ground-truth arrays to improve benchmark scores. Do not replace the evaluation with a method-specific scorer.
