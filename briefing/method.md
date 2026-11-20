# Paper's Method

## Key Contribution

HippMetric is a skeletal-representation framework for hippocampal substructural morphometry. It extends the ARMM coordinate system to subfields and longitudinal data so measurements are indexed by an internal lamellar skeleton rather than by unstable boundary parameterizations.

## Approach

The paper builds a hippocampal template with skeletal surfaces and paired superior/inferior spokes. Subject processing reconstructs and refines subfield surfaces, maps the template skeleton into each subject, and iteratively refines spoke endpoints and directions. The spoke refinement enforces boundary convergence, normal alignment, paired-spoke symmetry, and non-intersection/validity constraints. Thickness is computed from valid spoke lengths, while longitudinal follow-ups reuse the baseline skeletal coordinate system and re-optimize spoke lengths to represent tissue loss or growth.

This reproduction (`method/hippmetric.py`) runs the paper's subject-level pipeline on segmentations: RBOS-style surface refinement (shrink-wrap closing, hole filling, largest component, voxel-boundary surface, Taubin smoothing); multi-start similarity alignment of the template surface; a coarse-to-fine Gaussian-kernel diffeomorphic deformation (kernel width 7 -> 3 mm in 0.5 mm steps until the mean surface distance is below threshold) that also transports the template's skeletal and implied boundary points; spoke refinement with the paper's three skeletal-point cases via ray/mesh intersection, E0 (boundary convergence) and E1 (orthogonality, 0.1 rad steps, up to 50 iterations) for three rounds, E2 (superior/inferior length symmetry) and a final E0; and baseline-anchored follow-ups (rigid follow-up-to-baseline registration, baseline spokes reused, lengths re-optimised). Thickness is the sum of the two spoke lengths. Deformetrica's geodesic LDDMM is replaced by a greedy composition of small Gaussian-kernel velocity steps (a scale-down of the same deformation model), and template construction from FreeSurfer subfields is replaced by a procedural template (procedural cohort) and, for the real-anatomy cohort, by a template built in `data/build_real_template.py` from the mean of 228 real hippocampus labels (MSD Task04): a 61 x 9 lamellar grid along the curved long axis whose spokes are the chords of the mean shape along each lamella's normal.

## Main Claims

Primary claim: an internal skeletal/lamellar coordinate system with geometry-preserving spoke refinement yields more stable cross-sectional and longitudinal correspondence than boundary-driven shape models.

Secondary claims: local subfield thickness can be measured with sub-voxel-scale error, reconstruction quality remains stable under atrophy, and the resulting features are useful for Alzheimer's disease classification and prognosis.
