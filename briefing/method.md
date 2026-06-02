# Paper's Method

## Key Contribution

HippMetric is a skeletal-representation framework for hippocampal substructural morphometry. It extends the ARMM coordinate system to subfields and longitudinal data so measurements are indexed by an internal lamellar skeleton rather than by unstable boundary parameterizations.

## Approach

The paper builds a hippocampal template with skeletal surfaces and paired superior/inferior spokes. Subject processing reconstructs and refines subfield surfaces, maps the template skeleton into each subject, and iteratively refines spoke endpoints and directions. The spoke refinement enforces boundary convergence, normal alignment, paired-spoke symmetry, and non-intersection/validity constraints. Thickness is computed from valid spoke lengths, while longitudinal follow-ups reuse the baseline skeletal coordinate system and re-optimize spoke lengths to represent tissue loss or growth.

This reproduction implements the core computational steps at small scale: lamellar template coordinates, subject-specific skeletal transformation, paired superior/inferior spokes, iterative boundary and normal refinement, baseline-anchored longitudinal spoke optimization, local thickness extraction, and geometric validity reporting.

## Main Claims

Primary claim: an internal skeletal/lamellar coordinate system with geometry-preserving spoke refinement yields more stable cross-sectional and longitudinal correspondence than boundary-driven shape models.

Secondary claims: local subfield thickness can be measured with sub-voxel-scale error, reconstruction quality remains stable under atrophy, and the resulting features are useful for Alzheimer's disease classification and prognosis.
