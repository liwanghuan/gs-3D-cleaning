"""
Minimal reader for COLMAP sparse binaries (cameras.bin, images.bin,
points3D.bin). Pure numpy + struct.

Exists because pycolmap ships no wheel for the Python this project runs on.
The format is COLMAP's documented binary layout; the qvec is (w, x, y, z)
and (R, t) map world to camera, same as pycolmap's cam_from_world.
"""

import os
import struct
import numpy as np

# model_id -> (name, number of params)
CAMERA_MODELS = {
    0: ("SIMPLE_PINHOLE", 3), 1: ("PINHOLE", 4), 2: ("SIMPLE_RADIAL", 4),
    3: ("RADIAL", 5), 4: ("OPENCV", 8), 5: ("OPENCV_FISHEYE", 8),
    6: ("FULL_OPENCV", 12), 7: ("FOV", 5), 8: ("SIMPLE_RADIAL_FISHEYE", 4),
    9: ("RADIAL_FISHEYE", 5), 10: ("THIN_PRISM_FISHEYE", 12),
}


def _read(f, fmt):
    return struct.unpack("<" + fmt, f.read(struct.calcsize("<" + fmt)))


def qvec_to_R(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def read_cameras(path):
    cams = {}
    with open(path, "rb") as f:
        (n,) = _read(f, "Q")
        for _ in range(n):
            cam_id, model_id, w, h = _read(f, "iiQQ")
            name, n_params = CAMERA_MODELS[model_id]
            params = np.array(_read(f, "d" * n_params))
            cams[cam_id] = dict(model=name, width=w, height=h, params=params)
    return cams


def read_images(path):
    imgs = {}
    with open(path, "rb") as f:
        (n,) = _read(f, "Q")
        for _ in range(n):
            img_id, qw, qx, qy, qz, tx, ty, tz, cam_id = _read(f, "idddddddi")
            name = b""
            while (c := f.read(1)) != b"\x00":
                name += c
            (n_pts,) = _read(f, "Q")
            f.seek(24 * n_pts, os.SEEK_CUR)       # skip (x, y, point3D_id) rows
            imgs[img_id] = dict(name=name.decode(), camera_id=cam_id,
                                qvec=np.array([qw, qx, qy, qz]),
                                tvec=np.array([tx, ty, tz]))
    return imgs


def read_points3D(path):
    xyz, err, track = [], [], []
    with open(path, "rb") as f:
        (n,) = _read(f, "Q")
        for _ in range(n):
            _pid, x, y, z, _r, _g, _b, e, tl = _read(f, "QdddBBBdQ")
            f.seek(8 * tl, os.SEEK_CUR)           # skip (image_id, point2D_idx)
            xyz.append((x, y, z)); err.append(e); track.append(tl)
    return (np.array(xyz, np.float64), np.array(err), np.array(track, np.int64))


def read_sparse(path):
    return (read_cameras(os.path.join(path, "cameras.bin")),
            read_images(os.path.join(path, "images.bin")),
            read_points3D(os.path.join(path, "points3D.bin")))
