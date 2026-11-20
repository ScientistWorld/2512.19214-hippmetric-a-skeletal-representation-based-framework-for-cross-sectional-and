#!/usr/bin/env python3
"""Public reader for the real hippocampus anatomy used by the benchmark.

Source: Medical Segmentation Decathlon, Task04_Hippocampus (Vanderbilt
University Medical Center, CC-BY-SA 4.0), fetched by ``scripts/download.sh``
from the public MONAI mirror. The archive holds 260 labelled MRI crops, each
around one hippocampus, 1 mm isotropic, with label 1 = anterior (hippocampal
head) and label 2 = posterior (body and tail), drawn by human raters. All crops
share one orientation and chirality (anterior = +y, superior = +z).

``data/hippo_real_anatomy.npz`` stores the development subjects (every labelled
case except a held-out set reserved for the hidden test) in the packed-mask
encoding of ``data/hippo_io.py``:

- ``ids``              (N,) MSD case numbers
- ``mask_bits`` / ``mask_offsets`` / ``mask_shapes``   whole-hippocampus masks
- ``anterior_bits`` / ``anterior_offsets``             head (label 1) masks
- ``spacing``          (N,) voxel size in mm (1.0)

This module only decodes the archive. It contains no evaluation logic.
"""

from __future__ import annotations

import gzip
import re
import struct
import tarfile
from pathlib import Path

import numpy as np

TAR_URL = "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task04_Hippocampus.tar"
TAR_MD5 = "9d24dba78a72977dbd1d2e110310f31b"
LABEL_RE = re.compile(r"(?:^|/)labelsTr/hippocampus_(\d+)\.nii\.gz$")
N_HELDOUT = 32
_DTYPES = {2: np.uint8, 4: np.int16, 8: np.int32, 16: np.float32, 64: np.float64, 256: np.int8, 512: np.uint16, 768: np.uint32}


def read_nifti(raw: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Decode a (gzipped) NIfTI-1 volume: (array indexed [x, y, z], voxel size)."""
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    endian = "<" if struct.unpack("<i", raw[:4])[0] == 348 else ">"
    dim = struct.unpack(endian + "8h", raw[40:56])
    datatype = struct.unpack(endian + "h", raw[70:72])[0]
    pixdim = struct.unpack(endian + "8f", raw[76:108])
    offset = int(struct.unpack(endian + "f", raw[108:112])[0])
    shape = tuple(int(d) for d in dim[1:4])
    dtype = np.dtype(_DTYPES[datatype]).newbyteorder(endian)
    count = int(np.prod(shape))
    data = np.frombuffer(raw, dtype=dtype, count=count, offset=offset).reshape(shape, order="F")
    return np.array(data), np.asarray(pixdim[1:4], dtype=float)


def read_labels(archive: str | Path) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """All labelled cases of the MSD archive (a .tar or an extracted directory).

    Returns {case number: (integer label volume, voxel size)}.
    """
    archive = Path(archive)
    out: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    if archive.is_dir():
        for path in sorted(archive.rglob("hippocampus_*.nii.gz")):
            m = LABEL_RE.search(path.as_posix())
            if m and not path.name.startswith("._"):
                vol, sp = read_nifti(path.read_bytes())
                out[int(m.group(1))] = (np.rint(vol).astype(np.int16), sp)
        return out
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            m = LABEL_RE.search(member.name)
            if not m or not member.isfile() or Path(member.name).name.startswith("._"):
                continue
            vol, sp = read_nifti(tar.extractfile(member).read())
            out[int(m.group(1))] = (np.rint(vol).astype(np.int16), sp)
    return out


def split_ids(all_ids) -> tuple[list[int], list[int]]:
    """(development ids, held-out ids): every 8th case (offset 3) is held out for the hidden test."""
    ids = sorted(int(i) for i in all_ids)
    held = ids[3::8][:N_HELDOUT]
    held_set = set(held)
    return [i for i in ids if i not in held_set], held


def crop(label: np.ndarray, margin: int = 1) -> np.ndarray:
    idx = np.argwhere(label > 0)
    lo = np.maximum(idx.min(axis=0) - margin, 0)
    hi = np.minimum(idx.max(axis=0) + margin + 1, label.shape)
    return label[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]]


def pack(masks: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    packed = [np.packbits(m.ravel().astype(np.uint8)) for m in masks]
    offsets = np.concatenate([[0], np.cumsum([len(b) for b in packed])]).astype(np.int64)
    shapes = np.asarray([m.shape for m in masks], dtype=np.int64)
    return np.concatenate(packed).astype(np.uint8), offsets, shapes


def unpack(bits: np.ndarray, shape) -> np.ndarray:
    shape = tuple(int(s) for s in shape)
    return np.unpackbits(bits, count=int(np.prod(shape))).astype(bool).reshape(shape)


def anatomy_arrays(labels: dict[int, tuple[np.ndarray, np.ndarray]], ids: list[int]) -> dict:
    """Packed whole/anterior masks of the given cases (cropped around the label)."""
    whole, anterior, spacing = [], [], []
    for i in ids:
        lab, sp = labels[i]
        lab = crop(lab)
        whole.append(lab > 0)
        anterior.append(lab == 1)
        spacing.append(float(np.mean(sp)))
    wb, wo, ws = pack(whole)
    ab, ao, _ = pack(anterior)
    return {
        "ids": np.asarray(ids, dtype=np.int64),
        "mask_bits": wb,
        "mask_offsets": wo,
        "mask_shapes": ws,
        "anterior_bits": ab,
        "anterior_offsets": ao,
        "spacing": np.asarray(spacing, dtype=np.float64),
    }


def load_anatomy(path: str | Path) -> list[dict]:
    """Decode an anatomy file into [{'id', 'mask', 'anterior', 'spacing'}]."""
    with np.load(path, allow_pickle=False) as z:
        a = {k: np.asarray(z[k]) for k in z.files}
    out = []
    for i, cid in enumerate(a["ids"]):
        shape = a["mask_shapes"][i]
        out.append(
            {
                "id": int(cid),
                "mask": unpack(a["mask_bits"][a["mask_offsets"][i] : a["mask_offsets"][i + 1]], shape),
                "anterior": unpack(a["anterior_bits"][a["anterior_offsets"][i] : a["anterior_offsets"][i + 1]], shape),
                "spacing": float(a["spacing"][i]),
            }
        )
    return out
