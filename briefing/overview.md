# Overview

- **Paper ID:** 2512.19214
- **Title:** HippMetric: A skeletal-representation-based framework for cross-sectional and longitudinal hippocampal substructural morphometry
- **Domain:** Medical imaging / computational anatomy
- **TL;DR:** HippMetric measures hippocampal subfield morphology using an internal skeletal coordinate system that improves correspondence and longitudinal stability over boundary-driven shape models.

## Short Summary

The paper addresses hippocampal morphometry, where local subfield changes are clinically meaningful but hard to compare across subjects and time. HippMetric builds on ARMM and skeletal representations to define lamellar coordinates and paired spokes from an internal skeleton to the surface. The paper reports lower correspondence errors than cm-rep, ds-rep, and SPHARM-PDM, stable reconstruction under Alzheimer's disease atrophy, and stronger disease prediction than volumetric biomarkers.

## Key Results

- HippMetric cross-sectional correspondence errors are reported below about `1.66 mm`; competing models reach up to `9.97 mm`.
- Longitudinal simulated atrophy correspondence averages `1.68 mm` for HippMetric versus `3.56-10.57 mm` for baselines.
- HippMetric-derived substructural features reach GHABS validation AUC `0.861` for cross-sectional classification and `0.774` for conversion prediction.
