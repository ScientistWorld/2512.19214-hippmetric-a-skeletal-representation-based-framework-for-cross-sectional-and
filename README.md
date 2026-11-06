# HippMetric: A skeletal-representation-based framework for cross-sectional and longitudinal hippocampal substructural morphometry

| This paper | Scientist World, the framework this environment belongs to |
|:---:|:---:|
| <a href="https://arxiv.org/abs/2512.19214"><img alt="This paper on arXiv" src="https://img.shields.io/badge/arXiv-2512.19214-b31b1b?logo=arxiv&logoColor=white"></a> | <a href="https://arxiv.org/abs/2611.08478"><img alt="Scientist World on arXiv" src="https://img.shields.io/badge/arXiv-2611.08478-b31b1b?logo=arxiv&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world"><img alt="Scientist World code" src="https://img.shields.io/badge/Code-Scientist_World-181717?logo=github&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world_cli"><img alt="Command line code" src="https://img.shields.io/badge/Code-Command_line-181717?logo=github&logoColor=white"></a> |

| | |
|---|---|
| **Paper ID** | [2512.19214](https://arxiv.org/abs/2512.19214) |
| **Domain** | Medical imaging / computational anatomy |
| **TL;DR** | HippMetric measures hippocampal subfield morphology using an internal skeletal coordinate system that improves correspondence and longitudinal stability over boundary-driven shape models. |

## Summary

The paper addresses hippocampal morphometry, where local subfield changes are clinically meaningful but hard to compare across subjects and time. HippMetric builds on ARMM and skeletal representations to define lamellar coordinates and paired spokes from an internal skeleton to the surface. The paper reports lower correspondence errors than cm-rep, ds-rep, and SPHARM-PDM, stable reconstruction under Alzheimer's disease atrophy, and stronger disease prediction than volumetric biomarkers.

## Problem

The task is to produce reliable hippocampal substructure morphometry from 3D hippocampal segmentations or surfaces. A successful system should estimate local subfield thickness and preserve point-wise anatomical correspondence across different subjects and longitudinal scans, including scans with localized atrophy.

## The paper's method

HippMetric is a skeletal-representation framework for hippocampal substructural morphometry. It extends the ARMM coordinate system to subfields and longitudinal data so measurements are indexed by an internal lamellar skeleton rather than by unstable boundary parameterizations.

## Key results of the paper

- HippMetric cross-sectional correspondence errors are reported below about `1.66 mm`; competing models reach up to `9.97 mm`.
- Longitudinal simulated atrophy correspondence averages `1.68 mm` for HippMetric versus `3.56-10.57 mm` for baselines.
- HippMetric-derived substructural features reach GHABS validation AUC `0.861` for cross-sectional classification and `0.774` for conversion prediction.

## Run it

```bash
pip install sciworld
sw research 2512.19214 --mode innovate --agent claude-code
sw evaluate 2512.19214
```

## More

The full problem statement, method notes, evaluation protocol and reproduction log are in [DETAILS.md](DETAILS.md).

