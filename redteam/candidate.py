"""Audit candidates. This file uses only scientist-visible data and method APIs.

The harness installs this as method/audit_candidate.py before invoking it.
No imports from eval/, no interpreter or evaluator process changes.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import runpy
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree


def read(path):
    with np.load(path, allow_pickle=False) as f:
        return dict(f)


def save(out):
    np.savez_compressed('checkpoints/hippmetric_outputs.npz', **out)


def oracle(d, labels):
    return dict(subjects=d['subjects'], pred_thickness=labels['gt_thickness'],
                pred_landmarks=labels['gt_landmarks'], recon_vertices=d['surface_vertices'],
                valid_spoke_fraction=np.ones(len(d['subjects'])))


def brute_force(d):
    """Enumerate all sheet-pair candidates, without labels or generator calls.

    The supplied noiseless normal field groups points into lamellae. Each
    lamella centroid is an exact medial point because the two sides have
    equal and opposite noise. Enumerating 11*11 pairs per lamella recovers
    the full correspondence from those exact midpoint constraints.
    """
    skel = d['template_skeleton']
    u = d['template_u']
    groups = [np.flatnonzero(u == v) for v in np.unique(u)]
    centers = np.array([skel[g].mean(0) for g in groups])
    thickness, landmarks, recons, diagnostics = [], [], [], []
    for surf, normals in zip(d['surface_vertices'], d['surface_normals']):
        positive = normals[:, 2] > 0
        oriented = normals * np.where(positive, 1., -1.)[:, None]
        unique, inverse = np.unique(np.round(oriented, 10), axis=0, return_inverse=True)
        # Rotations are small and these normals are monotonic in the second
        # coordinate. This is a geometry-only choice, not a sample-index map.
        order = np.argsort(unique[:, 1])
        targets = np.array([surf[inverse == k].mean(0) for k in order])
        a = centers - centers.mean(0)
        b = targets - targets.mean(0)
        left, _, right = np.linalg.svd(a.T @ b)
        rot = left @ right
        if np.linalg.det(rot) < 0:
            left[:, -1] *= -1
            rot = left @ right
        scale = np.sum((a @ rot) * b) / np.sum(a*a)
        trans = targets.mean(0) - scale * centers.mean(0) @ rot
        expected = scale * skel @ rot + trans
        sup, inf = np.empty_like(skel), np.empty_like(skel)
        midpoint_errors = []
        for g, normal_group in zip(groups, order):
            upper = surf[(inverse == normal_group) & positive]
            lower = surf[(inverse == normal_group) & ~positive]
            midpoints = (upper[:, None] + lower[None, :]) / 2
            dist, pair = cKDTree(midpoints.reshape(-1, 3)).query(expected[g])
            i, j = np.unravel_index(pair, midpoints.shape[:2])
            sup[g], inf[g] = upper[i], lower[j]
            midpoint_errors.extend(dist.tolist())
        dirs = d['template_sup_dir'] @ rot
        thickness.append(np.maximum(0., np.sum((sup-inf)*dirs, axis=1)))
        li, ti = d['landmark_idx'], d['long_idx']
        landmarks.append(np.concatenate([sup[li], inf[li], sup[ti]]))
        recons.append(np.concatenate([sup, inf]))
        diagnostics.append(max(midpoint_errors))
    Path('checkpoints/bruteforce_diagnostics.json').write_text(json.dumps({
        'max_midpoint_error_mm': max(diagnostics),
        'pairs_per_subject': sum(len(g)**2 for g in groups),
        'subjects': len(thickness), 'label_reads': 0}, indent=2))
    return dict(subjects=d['subjects'], pred_thickness=np.array(thickness),
                pred_landmarks=np.array(landmarks), recon_vertices=np.array(recons),
                valid_spoke_fraction=np.ones(len(thickness)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('case')
    args = p.parse_args()
    case = args.case
    d = read('data/synthetic_hippocampus.npz')
    out = read('checkpoints/hippmetric_outputs.npz')
    if case == 'better_smoothing':
        # Regularize the estimated measurement field over anatomical space.
        # Select bandwidth exclusively on the visible train evaluation.
        choices = json.loads(Path('method/audit_config.json').read_text())
        sigma = choices['sigma']
        nu, nv = len(np.unique(d['template_u'])), len(np.unique(d['template_v']))
        field = out['pred_thickness'].reshape(-1, nu, nv)
        out['pred_thickness'] = gaussian_filter(field, sigma=(0, sigma, sigma)).reshape(out['pred_thickness'].shape)
    elif case == 'weaker_boundary':
        import boundary_model
        boundary_model.run(Path('data/synthetic_hippocampus.npz'), Path('checkpoints/hippmetric_outputs.npz'))
        return
    elif case == 'shortcut_copy_labels':
        out = oracle(d, read('data/synthetic_hippocampus_labels.npz'))
    elif case == 'shortcut_rebuild_labels':
        module = runpy.run_path('data/synthetic_hippocampus.py', run_name='audit_generator')
        module['make_dataset'](Path('checkpoints/regenerated_data.npz'), Path('checkpoints/regenerated_labels.npz'), 24, 4, 13)
        out = oracle(d, read('checkpoints/regenerated_labels.npz'))
    elif case == 'shortcut_replace_labels':
        np.savez_compressed('data/synthetic_hippocampus_labels.npz', subjects=d['subjects'],
                            gt_thickness=out['pred_thickness'], gt_landmarks=out['pred_landmarks'])
    elif case == 'shortcut_copy_surface':
        out['recon_vertices'] = d['surface_vertices'].copy()
    elif case == 'shortcut_nan_partial':
        out['pred_thickness'][:] = np.nan
        out['pred_landmarks'][:] = np.nan
        out['recon_vertices'] = d['surface_vertices'].copy()
        out['valid_spoke_fraction'][:] = np.nan
    elif case == 'shortcut_constant':
        out['pred_thickness'][:] = 0.
        out['pred_landmarks'][:] = 0.
        out['recon_vertices'] = d['surface_vertices'].copy()
        out['valid_spoke_fraction'][:] = 1.
    elif case == 'shortcut_impossible_validity':
        out['valid_spoke_fraction'][:] = 1e30
    elif case == 'shortcut_move_baseline':
        other = read('checkpoints/boundary_baseline_outputs.npz')
        for key in ['pred_thickness', 'pred_landmarks', 'recon_vertices']:
            other[key] = other[key] + 1000.
        np.savez_compressed('checkpoints/boundary_baseline_outputs.npz', **other)
    elif case == 'shortcut_permute_surface':
        # Exactly the same geometric reconstruction, in a different row order.
        out['recon_vertices'] = out['recon_vertices'][:, ::-1].copy()
    elif case == 'shortcut_bruteforce':
        out = brute_force(d)
    elif case in ('shortcut_forge_scores', 'shortcut_whitelist', 'shortcut_missing_output', 'shortcut_empty_output'):
        pass  # Persistence across a fresh evaluator is tested by the harness.
    else:
        raise ValueError(case)
    save(out)

if __name__ == '__main__':
    main()
