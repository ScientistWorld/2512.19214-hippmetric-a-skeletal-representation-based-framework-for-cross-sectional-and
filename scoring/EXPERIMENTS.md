# Experiment Overview

## synthetic_subfield_thickness

This experiment tests whether a system can recover local hippocampal subfield thickness from surface geometry when the reference thickness is known. It measures the core morphometry task without requiring access to private clinical labels or manual annotations.

## synthetic_correspondence

This experiment tests whether a system preserves point-wise anatomical landmark locations across subjects and during simulated longitudinal tissue loss. It is the main benchmark for the paper's correspondence-stability claim.

## synthetic_surface_robustness

This experiment tests whether the reconstructed measurement surface remains close to the observed anatomy under both baseline variation and atrophy-like follow-up changes. It guards against methods that reduce landmark error while producing poor or invalid geometry.
