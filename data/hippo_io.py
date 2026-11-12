#!/usr/bin/env python3
"""Public I/O and surface utilities for the hippocampal segmentation benchmark.

Scan files (``data/hippo_train.npz`` and the hidden test file handed to a
predictor) store one binary hippocampal segmentation per scan on an isotropic
0.5 mm grid:

- ``subjects``      (N, 2) int: subject id, timepoint (0 = baseline).
- ``mask_bits``     packed bits of all masks (``np.packbits`` of each C-order mask).
- ``mask_offsets``  (N + 1,) byte offsets of each scan in ``mask_bits``.
- ``mask_shapes``   (N, 3) grid shape of each mask.
- ``origins``       (N, 3) world position (mm) of voxel (0, 0, 0)'s centre.
- ``spacing``       (N,) voxel size (mm).

The template file (``data/hippo_template.npz``) holds the reference skeletal
grid (61 x 9 points, u-major), its superior/inferior spoke directions and
lengths, lamellar coordinates, subfield ids, and the template segmentation in
the same encoding (``mask_bits``, ``mask_shape``, ``origin``, ``spacing``).

These helpers only decode inputs and turn masks into surfaces. They contain no
ground truth and no evaluation logic.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import ndimage, sparse
from scipy.sparse.csgraph import connected_components


def _unpack(bits: np.ndarray, shape) -> np.ndarray:
    shape = tuple(int(s) for s in shape)
    count = int(np.prod(shape))
    return np.unpackbits(bits, count=count).astype(bool).reshape(shape)


def load_scans(path: str | Path) -> dict:
    with np.load(path, allow_pickle=False) as z:
        subjects = np.asarray(z["subjects"])
        bits = np.asarray(z["mask_bits"])
        offsets = np.asarray(z["mask_offsets"])
        shapes = np.asarray(z["mask_shapes"])
        origins = np.asarray(z["origins"], dtype=float)
        spacing = np.asarray(z["spacing"], dtype=float)
    masks = [_unpack(bits[offsets[i] : offsets[i + 1]], shapes[i]) for i in range(len(subjects))]
    return {"subjects": subjects, "masks": masks, "origins": origins, "spacing": spacing}


def load_template(path: str | Path) -> dict:
    with np.load(path, allow_pickle=False) as z:
        tpl = {k: np.asarray(z[k]) for k in z.files}
    tpl["mask"] = _unpack(tpl.pop("mask_bits"), tpl["mask_shape"])
    tpl["spacing"] = float(tpl["spacing"])
    return tpl


def mask_to_mesh(mask: np.ndarray, origin: np.ndarray, spacing: float) -> tuple[np.ndarray, np.ndarray]:
    """Voxel-boundary (cuberille) triangle mesh of a binary mask, outward oriented."""
    padded = np.pad(mask.astype(bool), 1)
    dims = np.array(padded.shape) + 1
    quads = []
    for axis in range(3):
        n = padded.shape[axis]
        lo = np.take(padded, np.arange(0, n - 1), axis=axis)
        hi = np.take(padded, np.arange(1, n), axis=axis)
        b, c = [a for a in range(3) if a != axis]
        # Winding (c0, c1, c2, c3) has normal e_b x e_c = +e_axis for axis 0/2, -e_axis for axis 1.
        winding_sign = 1 if axis != 1 else -1
        for sel, sign in ((lo & ~hi, 1), (~lo & hi, -1)):
            idx = np.argwhere(sel)
            if len(idx) == 0:
                continue
            base = idx.copy()
            base[:, axis] += 1
            c0 = base
            c1 = base.copy()
            c1[:, b] += 1
            c2 = c1.copy()
            c2[:, c] += 1
            c3 = base.copy()
            c3[:, c] += 1
            if sign * winding_sign > 0:
                quads.append(np.stack([c0, c1, c2, c3], axis=1))
            else:
                quads.append(np.stack([c0, c3, c2, c1], axis=1))
    if not quads:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
    q = np.concatenate(quads)  # (n, 4, 3) integer corner coordinates
    codes = (q[..., 0].astype(np.int64) * dims[1] + q[..., 1]) * dims[2] + q[..., 2]
    uniq, inv = np.unique(codes.ravel(), return_inverse=True)
    inv = inv.reshape(-1, 4)
    corner = np.stack([uniq // (dims[1] * dims[2]), (uniq // dims[2]) % dims[1], uniq % dims[2]], axis=1)
    vertices = np.asarray(origin, dtype=float) + spacing * (corner.astype(float) - 1.5)
    faces = np.concatenate([inv[:, [0, 1, 2]], inv[:, [0, 2, 3]]]).astype(np.int64)
    return vertices, faces


def _adjacency(n_vertices: int, faces: np.ndarray) -> sparse.csr_matrix:
    i = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2], faces[:, 1], faces[:, 2], faces[:, 0]])
    j = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0], faces[:, 0], faces[:, 1], faces[:, 2]])
    adj = sparse.csr_matrix((np.ones(len(i)), (i, j)), shape=(n_vertices, n_vertices))
    adj.sum_duplicates()
    adj.data[:] = 1.0
    return adj


def largest_component(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Keep the largest connected surface piece (removes islands and enclosed cavities)."""
    if len(faces) == 0:
        return vertices, faces
    _, labels = connected_components(_adjacency(len(vertices), faces), directed=False)
    keep_label = np.bincount(labels[faces[:, 0]]).argmax()
    keep_v = labels == keep_label
    new_index = np.full(len(vertices), -1, dtype=np.int64)
    new_index[keep_v] = np.arange(int(keep_v.sum()))
    keep_f = keep_v[faces].all(axis=1)
    return vertices[keep_v], new_index[faces[keep_f]]


def vertex_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    tri = vertices[faces]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    vn = np.zeros_like(vertices)
    for k in range(3):
        np.add.at(vn, faces[:, k], fn)
    norm = np.linalg.norm(vn, axis=1, keepdims=True)
    return vn / np.maximum(norm, 1e-12)


def taubin_smooth(vertices: np.ndarray, faces: np.ndarray, iterations: int = 20, lam: float = 0.5, mu: float = -0.53) -> np.ndarray:
    adj = _adjacency(len(vertices), faces)
    deg = np.asarray(adj.sum(axis=1)).ravel()
    walk = sparse.diags(1.0 / np.maximum(deg, 1.0)) @ adj
    x = vertices.copy()
    for _ in range(iterations):
        x = x + lam * (walk @ x - x)
        x = x + mu * (walk @ x - x)
    return x


def refine_mask(mask: np.ndarray, origin: np.ndarray, spacing: float, closing_iterations: int = 2):
    """Shrink-wrap style mask clean-up: closing, hole filling, largest 6-connected component.

    Returns the cleaned (padded) mask and its origin.
    """
    pad = closing_iterations + 1
    m = np.pad(mask.astype(bool), pad)
    origin = np.asarray(origin, dtype=float) - pad * float(spacing)
    cross = ndimage.generate_binary_structure(3, 1)
    if closing_iterations > 0:
        m = ndimage.binary_closing(m, structure=cross, iterations=closing_iterations)
    m = ndimage.binary_fill_holes(m)
    labels, n = ndimage.label(m, structure=cross)
    if n > 1:
        sizes = np.bincount(labels.ravel())
        sizes[0] = 0
        m = labels == int(np.argmax(sizes))
    return m, origin


def surface_from_mask(
    mask: np.ndarray, origin: np.ndarray, spacing: float, smooth_iterations: int = 20, closing_iterations: int = 2
):
    """Segmentation -> cleaned, smoothed, outward-oriented triangle surface (V, F, vertex normals)."""
    mask, origin = refine_mask(mask, origin, spacing, closing_iterations)
    v, f = mask_to_mesh(mask, origin, spacing)
    v, f = largest_component(v, f)
    if smooth_iterations > 0 and len(f):
        v = taubin_smooth(v, f, iterations=smooth_iterations)
    return v, f, vertex_normals(v, f)
