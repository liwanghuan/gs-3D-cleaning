#!/usr/bin/env python3
"""
CPU-only per-Gaussian feature extraction for 3DGS data cleaning.

No CUDA, no gsplat, no training. Everything here is numpy + scipy.

The trick is that the two things you actually need — how many views see a
Gaussian, and how much of each view it covers — are pure projective geometry.
Alpha compositing is the only part that needs a rasterizer, and you can
approximate its role with the projected footprint area, which is what
FlexGaussian does for importance scoring ("importance score computation does
not rely on image content... it evaluates each 3D Gaussian's contribution by
counting how many pixels it overlaps with across a view set").

What you lose vs the GPU version: true transmittance T, so a Gaussian buried
inside an opaque wall looks as "contributing" as one on the surface. Occluded
Gaussians are a separate problem from floaters, so this is fine for week 1.

Setup:
    pip install numpy scipy pandas plyfile pyarrow pycolmap tqdm

Data (no training needed):
    Pre-trained models, 14GB, all standard scenes:
        https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/
    Or scenes + pre-trained splats together:
        hf download alexmkwizu/gaussian_training_datasets --repo-type dataset \
            --include "tandt/truck/*" --local-dir datasets

Usage:
    python extract_features_cpu.py \
        --ply     models/truck/point_cloud/iteration_30000/point_cloud.ply \
        --colmap  datasets/tandt/truck/sparse/0 \
        --out     features_truck.parquet
"""

import argparse
import numpy as np
import pandas as pd
from plyfile import PlyData
from scipy.spatial import cKDTree
from tqdm import tqdm


# --------------------------------------------------------------------------
def load_gaussians(path):
    """Standard 3DGS .ply. Opacity is stored as a logit, scales as logs."""
    v = PlyData.read(path)["vertex"]
    xyz = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float32)
    opacity = 1.0 / (1.0 + np.exp(-np.asarray(v["opacity"], np.float32)))
    scales = np.exp(np.stack([v[f"scale_{i}"] for i in range(3)], 1).astype(np.float32))
    quats = np.stack([v[f"rot_{i}"] for i in range(4)], 1).astype(np.float32)
    quats /= np.linalg.norm(quats, axis=1, keepdims=True) + 1e-9
    sh_dc = np.stack([v[f"f_dc_{i}"] for i in range(3)], 1).astype(np.float32)
    return dict(xyz=xyz, opacity=opacity, scales=scales, quats=quats, sh_dc=sh_dc)


def quats_to_R(q):
    """(w, x, y, z) -> [N, 3, 3]."""
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    N = len(q)
    R = np.empty((N, 3, 3), np.float32)
    R[:, 0, 0] = 1 - 2 * (y * y + z * z)
    R[:, 0, 1] = 2 * (x * y - w * z)
    R[:, 0, 2] = 2 * (x * z + w * y)
    R[:, 1, 0] = 2 * (x * y + w * z)
    R[:, 1, 1] = 1 - 2 * (x * x + z * z)
    R[:, 1, 2] = 2 * (y * z - w * x)
    R[:, 2, 0] = 2 * (x * z - w * y)
    R[:, 2, 1] = 2 * (y * z + w * x)
    R[:, 2, 2] = 1 - 2 * (x * x + y * y)
    return R


def covariance_3d(g):
    """Sigma = R diag(s^2) R^T, computed once and reused across every view."""
    R = quats_to_R(g["quats"])
    S2 = g["scales"].astype(np.float32) ** 2
    # R * s^2 broadcast along columns, then times R^T
    RS = R * S2[:, None, :]
    return np.einsum("nij,nkj->nik", RS, R)


# --------------------------------------------------------------------------
def intrinsic_features(g):
    s = np.sort(g["scales"], axis=1)
    s_min, s_mid, s_max = s[:, 0], s[:, 1], s[:, 2]
    return pd.DataFrame({
        "opacity":    g["opacity"],
        "scale_max":  s_max,
        "scale_min":  s_min,
        "volume":     g["scales"].prod(axis=1),
        "anisotropy": s_max / (s_min + 1e-9),
        "planarity":  s_mid / (s_max + 1e-9),
        "sh_dc_norm": np.linalg.norm(g["sh_dc"], axis=1),
    })


def contextual_features(g, k=8):
    tree = cKDTree(g["xyz"])
    d, _ = tree.query(g["xyz"], k=k + 1, workers=-1)
    knn = d[:, 1:]
    mean = knn.mean(axis=1)
    return pd.DataFrame({
        "knn_mean":  mean,
        "knn_max":   knn.max(axis=1),
        "isolation": mean / (np.median(mean) + 1e-9),
    })


# --------------------------------------------------------------------------
def evidential_features_cpu(g, cov3d, cameras, chunk=400_000):
    """
    Per view, project every Gaussian and record:
      - whether it lands inside the image (view coverage)
      - the area of its projected footprint in pixels (contribution proxy)

    cameras: list of dicts with R [3,3] world-to-cam, t [3], fx, fy, cx, cy,
             width, height.
    """
    N = len(g["xyz"])
    xyz = g["xyz"]
    opac = g["opacity"]

    view_count = np.zeros(N, np.int32)
    cov_sum = np.zeros(N, np.float64)     # summed opacity-weighted pixel area
    cov_max = np.zeros(N, np.float32)     # best single view
    radius_max = np.zeros(N, np.float32)

    for cam in tqdm(cameras, desc="views"):
        R, t = cam["R"].astype(np.float32), cam["t"].astype(np.float32)
        fx, fy, cx, cy = cam["fx"], cam["fy"], cam["cx"], cam["cy"]
        Wd, Ht = cam["width"], cam["height"]

        this_view = np.zeros(N, np.float32)

        for a in range(0, N, chunk):
            b = min(a + chunk, N)
            p = xyz[a:b] @ R.T + t                     # camera space
            tz = p[:, 2]
            front = tz > 0.2
            if not front.any():
                continue

            idx = np.nonzero(front)[0]
            pz = tz[idx]
            px, py = p[idx, 0], p[idx, 1]

            u = fx * px / pz + cx
            vv = fy * py / pz + cy

            # EWA splatting Jacobian of the perspective projection
            J = np.zeros((len(idx), 2, 3), np.float32)
            J[:, 0, 0] = fx / pz
            J[:, 0, 2] = -fx * px / (pz * pz)
            J[:, 1, 1] = fy / pz
            J[:, 1, 2] = -fy * py / (pz * pz)

            T = np.einsum("nij,jk->nik", J, R)          # [n, 2, 3]
            S = cov3d[a:b][idx]
            c2 = np.einsum("nij,njk,nlk->nil", T, S, T)  # [n, 2, 2]

            # screen-space low-pass filter, as in the 3DGS rasteriser
            c2[:, 0, 0] += 0.3
            c2[:, 1, 1] += 0.3

            aa, bb, cc = c2[:, 0, 0], c2[:, 0, 1], c2[:, 1, 1]
            det = np.maximum(aa * cc - bb * bb, 1e-9)
            mid = 0.5 * (aa + cc)
            disc = np.sqrt(np.maximum(mid * mid - det, 0.0))
            lam_max = mid + disc
            radius = 3.0 * np.sqrt(np.maximum(lam_max, 0.0))

            # visible if the footprint overlaps the image rectangle at all
            inside = (u + radius > 0) & (u - radius < Wd) & \
                     (vv + radius > 0) & (vv - radius < Ht)
            if not inside.any():
                continue

            sel = idx[inside]
            # ellipse area at 3 sigma = pi * (3 sqrt(l1)) * (3 sqrt(l2))
            area = 9.0 * np.pi * np.sqrt(det[inside])
            # cap at the image so one giant background blob cannot dominate
            area = np.minimum(area, Wd * Ht)

            gidx = sel + a
            view_count[gidx] += 1
            this_view[gidx] = opac[gidx] * area.astype(np.float32)
            radius_max[gidx] = np.maximum(radius_max[gidx], radius[inside])

        cov_sum += this_view
        np.maximum(cov_max, this_view, out=cov_max)

    n_views = len(cameras)
    mean_contrib = cov_sum / np.maximum(view_count, 1)

    return pd.DataFrame({
        "view_count":    view_count,
        "view_frac":     view_count / n_views,
        "cov_sum":       cov_sum,
        "cov_max":       cov_max,
        "radius_max_px": radius_max,
        # >> the discriminator: peak view vs typical view <<
        "contrib_ratio": cov_max / (mean_contrib + 1e-9),
    })


# --------------------------------------------------------------------------
def reference_features(g, ref_xyz, scale_mult=20.0):
    """
    Distance to a geometrically-verified reference. COLMAP's points3D from
    the sparse reconstruction already passed multi-view triangulation with a
    reprojection-error check, which is exactly the consistency test 3DGS
    never applies. Sparse, but free — it ships with every scene.

    Upgrade to COLMAP dense (needs a GPU) or LiDAR when you have it.
    """
    tree = cKDTree(ref_xyz)
    dist, _ = tree.query(g["xyz"], k=1, workers=-1)

    spacing, _ = tree.query(ref_xyz, k=2, workers=-1)
    tau = scale_mult * np.median(spacing[:, 1])

    return pd.DataFrame({
        "dist_to_reference": dist,
        "unsupported": (dist > tau).astype(np.int8),
    }), tau


# --------------------------------------------------------------------------
def load_colmap(path):
    """Cameras and sparse points via pycolmap (pip-installable, CPU-only)."""
    import pycolmap
    rec = pycolmap.Reconstruction(path)

    cams = []
    for img in rec.images.values():
        cam = rec.cameras[img.camera_id]
        p = cam.params
        if cam.model_name in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL"):
            fx, fy, cxx, cyy = p[0], p[0], p[1], p[2]
        else:                                    # PINHOLE, OPENCV
            fx, fy, cxx, cyy = p[0], p[1], p[2], p[3]

        # pycolmap exposes world-to-camera as cam_from_world
        try:
            T = img.cam_from_world
            R, t = T.rotation.matrix(), T.translation
        except AttributeError:                   # older pycolmap
            R, t = img.rotation_matrix(), img.tvec

        cams.append(dict(R=np.asarray(R), t=np.asarray(t),
                         fx=fx, fy=fy, cx=cxx, cy=cyy,
                         width=cam.width, height=cam.height))

    pts = np.array([p.xyz for p in rec.points3D.values()], np.float32)
    return cams, pts


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ply", required=True)
    ap.add_argument("--colmap", required=True)
    ap.add_argument("--out", default="features_cpu.parquet")
    ap.add_argument("--max-views", type=int, default=0,
                    help="subsample views for a fast first pass (0 = all)")
    args = ap.parse_args()

    g = load_gaussians(args.ply)
    N = len(g["xyz"])
    print(f"loaded {N:,} Gaussians")

    cams, ref_pts = load_colmap(args.colmap)
    if args.max_views and len(cams) > args.max_views:
        step = len(cams) // args.max_views
        cams = cams[::step][:args.max_views]
    print(f"{len(cams)} views, {len(ref_pts):,} reference points")

    print("computing 3D covariances...")
    cov3d = covariance_3d(g)

    parts = [
        intrinsic_features(g),
        contextual_features(g),
        evidential_features_cpu(g, cov3d, cams),
    ]
    ref_df, tau = reference_features(g, ref_pts)
    print(f"reference threshold tau = {tau:.4f} scene units")
    parts.append(ref_df)

    df = pd.concat(parts, axis=1)
    df.insert(0, "gaussian_id", np.arange(N))
    df[["x", "y", "z"]] = g["xyz"]
    df.to_parquet(args.out)

    print(f"\nwrote {args.out}  ({len(df):,} rows, {len(df.columns)} cols)")
    print(f"\nunsupported (weak floater label): "
          f"{df.unsupported.mean() * 100:.1f}% of Gaussians")
    print("\nmedian feature values, supported vs unsupported:")
    print(df.groupby("unsupported")[
        ["view_frac", "contrib_ratio", "anisotropy", "isolation", "opacity"]
    ].median().T)


if __name__ == "__main__":
    main()
