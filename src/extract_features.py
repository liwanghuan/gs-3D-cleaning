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
Gaussians are a separate problem from floaters (AGENTS.md §7).

Thresholds and constants live in the YAML config, never in this file.

Usage:
    python src/extract_features.py --config configs/T1_truck.yaml
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import yaml
from plyfile import PlyData
from scipy.spatial import cKDTree
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colmap_io import read_sparse, qvec_to_R  # noqa: E402

COLUMNS = [
    "gaussian_id", "x", "y", "z", "opacity", "scale_max", "scale_min",
    "volume", "anisotropy", "planarity", "sh_dc_norm", "knn_mean", "knn_max",
    "isolation", "view_count", "view_frac", "cov_sum", "cov_max",
    "radius_max_px", "contrib_ratio", "dist_to_reference", "unsupported",
]


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


def contextual_features(g, k):
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
def evidential_features_cpu(g, cov3d, cameras, cfg, chunk=400_000):
    """
    Per view, project every Gaussian and record:
      - whether it lands inside the image (view coverage)
      - the area of its projected footprint in pixels (contribution proxy)

    cameras: list of dicts with R [3,3] world-to-cam, t [3], fx, fy, cx, cy,
             width, height (at training resolution).
    """
    near = cfg["near_plane"]
    lowpass = cfg["lowpass_px2"]
    nsig = cfg["footprint_sigma"]
    clamp = cfg["jacobian_fov_clamp"]

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
        # the reference rasteriser clamps x/z, y/z to 1.3 tan(fov/2) before
        # building the Jacobian, so off-screen Gaussians do not explode
        limx = clamp * (0.5 * Wd / fx)
        limy = clamp * (0.5 * Ht / fy)

        this_view = np.zeros(N, np.float32)

        for a in range(0, N, chunk):
            b = min(a + chunk, N)
            p = xyz[a:b] @ R.T + t                     # camera space
            tz = p[:, 2]
            front = tz > near
            if not front.any():
                continue

            idx = np.nonzero(front)[0]
            pz = tz[idx]
            px, py = p[idx, 0], p[idx, 1]

            u = fx * px / pz + cx
            vv = fy * py / pz + cy

            jx = np.clip(px / pz, -limx, limx) * pz
            jy = np.clip(py / pz, -limy, limy) * pz

            # EWA splatting Jacobian of the perspective projection
            J = np.zeros((len(idx), 2, 3), np.float32)
            J[:, 0, 0] = fx / pz
            J[:, 0, 2] = -fx * jx / (pz * pz)
            J[:, 1, 1] = fy / pz
            J[:, 1, 2] = -fy * jy / (pz * pz)

            T = np.einsum("nij,jk->nik", J, R)          # [n, 2, 3]
            S = cov3d[a:b][idx]
            c2 = np.einsum("nij,njk,nlk->nil", T, S, T)  # [n, 2, 2]

            # screen-space low-pass filter, as in the 3DGS rasteriser
            c2[:, 0, 0] += lowpass
            c2[:, 1, 1] += lowpass

            aa, bb, cc = c2[:, 0, 0], c2[:, 0, 1], c2[:, 1, 1]
            det = np.maximum(aa * cc - bb * bb, 1e-9)
            mid = 0.5 * (aa + cc)
            disc = np.sqrt(np.maximum(mid * mid - det, 0.0))
            lam_max = mid + disc
            radius = nsig * np.sqrt(np.maximum(lam_max, 0.0))

            # visible if the footprint overlaps the image rectangle at all
            inside = (u + radius > 0) & (u - radius < Wd) & \
                     (vv + radius > 0) & (vv - radius < Ht)
            if not inside.any():
                continue

            sel = idx[inside]
            # ellipse area at n sigma = pi * (n sqrt(l1)) * (n sqrt(l2))
            area = nsig * nsig * np.pi * np.sqrt(det[inside])
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
def reference_features(g, ref_xyz, scale_mult):
    """
    Distance to a geometrically-verified reference. COLMAP's points3D from
    the sparse reconstruction already passed multi-view triangulation with a
    reprojection-error check, which is exactly the consistency test 3DGS
    never applies. Sparse, but free — it ships with every scene.

    Weak supervision only: high precision, low recall (AGENTS.md §1.3).
    """
    tree = cKDTree(ref_xyz)
    dist, _ = tree.query(g["xyz"], k=1, workers=-1)

    spacing, _ = tree.query(ref_xyz, k=2, workers=-1)
    median_spacing = float(np.median(spacing[:, 1]))
    tau = scale_mult * median_spacing

    return pd.DataFrame({
        "dist_to_reference": dist,
        "unsupported": (dist > tau).astype(np.int8),
    }), tau, median_spacing


# --------------------------------------------------------------------------
def load_colmap(path, train_max_width, eval_holdout):
    """
    Cameras and sparse points from COLMAP binaries. Intrinsics are rescaled
    to the resolution 3DGS trained at (its default `-r -1` downsamples any
    image wider than train_max_width), so pixel-space constants such as the
    0.3 low-pass act at the same scale as in the rasteriser.

    With eval_holdout > 0, drops the test views exactly as 3DGS does
    (sorted by name, index % eval_holdout == 0), since the model never saw them.
    """
    cameras, images, (pts, _err, _track) = read_sparse(path)

    ordered = sorted(images.values(), key=lambda im: im["name"])
    if eval_holdout:
        ordered = [im for i, im in enumerate(ordered) if i % eval_holdout != 0]

    cams = []
    for img in ordered:
        cam = cameras[img["camera_id"]]
        p = cam["params"]
        if cam["model"] in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL"):
            fx, fy, cxx, cyy = p[0], p[0], p[1], p[2]
        elif cam["model"] in ("PINHOLE", "OPENCV", "FULL_OPENCV"):
            fx, fy, cxx, cyy = p[0], p[1], p[2], p[3]
        else:
            raise ValueError(f"unsupported camera model {cam['model']}")
        if cam["model"] not in ("SIMPLE_PINHOLE", "PINHOLE"):
            print(f"warning: {cam['model']} distortion ignored", file=sys.stderr)

        W, H = cam["width"], cam["height"]
        s = W / train_max_width if (train_max_width and W > train_max_width) else 1.0
        Wt, Ht = round(W / s), round(H / s)
        sx, sy = Wt / W, Ht / H

        cams.append(dict(name=img["name"],
                         R=qvec_to_R(img["qvec"]), t=img["tvec"],
                         fx=fx * sx, fy=fy * sy, cx=cxx * sx, cy=cyy * sy,
                         width=Wt, height=Ht))
    return cams, pts.astype(np.float32)


# --------------------------------------------------------------------------
def range_report(df):
    """Report out-of-range values. Never clip (AGENTS.md T1 checkpoint)."""
    checks = [
        ("opacity in [0,1]", ~df.opacity.between(0, 1)),
        ("scale_min > 0",    ~(df.scale_min > 0)),
        ("scale_max > 0",    ~(df.scale_max > 0)),
        ("view_frac in [0,1]", ~df.view_frac.between(0, 1)),
    ]
    num = df.select_dtypes("number")
    checks.append(("all values finite", ~np.isfinite(num).all(axis=1)))
    ok = True
    for name, bad in checks:
        n = int(bad.sum())
        ok &= n == 0
        print(f"  {'PASS' if n == 0 else 'FAIL'}  {name:<20} violations: {n:,} / {len(df):,}")

    # in range but worth knowing about before any analysis
    N = len(df)
    notes = [
        ("view_count == 0 (seen by no sampled view)", df.view_count == 0),
        ("opacity == 1.0 exactly (float32 sigmoid saturation)", df.opacity == 1.0),
        ("scale_min < 1e-6 scene units", df.scale_min < 1e-6),
        ("anisotropy > 1e4", df.anisotropy > 1e4),
    ]
    print("\nnotable but in range:")
    for name, m in notes:
        print(f"  {int(m.sum()):>10,} / {N:,}  ({m.mean() * 100:.2f}%)  {name}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--max-views", type=int, default=None,
                    help="override config: subsample views (0 = all)")
    ap.add_argument("--out", default=None, help="override config output path")
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    max_views = cfg["max_views"] if args.max_views is None else args.max_views
    out = args.out or cfg["out"]

    g = load_gaussians(cfg["ply"])
    N = len(g["xyz"])
    print(f"loaded {N:,} Gaussians")

    cams, ref_pts = load_colmap(cfg["colmap"], cfg["projection"]["train_max_width"],
                                cfg["eval_holdout"])
    n_total = len(cams)
    if max_views and len(cams) > max_views:
        step = len(cams) // max_views
        cams = cams[::step][:max_views]
    print(f"{len(cams)} of {n_total} training views "
          f"({cams[0]['width']}x{cams[0]['height']} px), "
          f"{len(ref_pts):,} reference points")

    print("computing 3D covariances...")
    cov3d = covariance_3d(g)

    parts = [
        intrinsic_features(g),
        contextual_features(g, cfg["knn_k"]),
        evidential_features_cpu(g, cov3d, cams, cfg["projection"]),
    ]
    ref_df, tau, spacing = reference_features(g, ref_pts, cfg["unsupported_spacing_mult"])
    print(f"median reference spacing = {spacing:.5f} scene units; "
          f"tau = {cfg['unsupported_spacing_mult']} x spacing = {tau:.5f}")
    parts.append(ref_df)

    df = pd.concat(parts, axis=1)
    df.insert(0, "gaussian_id", np.arange(N))
    df[["x", "y", "z"]] = g["xyz"]
    df = df[COLUMNS]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    df.to_parquet(out, index=False)

    print(f"\nwrote {out}  ({len(df):,} rows, {len(df.columns)} cols)")
    print("columns:", ", ".join(df.columns))
    with pd.option_context("display.max_columns", None, "display.width", 200,
                           "display.float_format", "{:.4g}".format):
        print(df.describe().T)
    print("\nrange checks (nothing clipped):")
    range_report(df)
    print(f"\nunsupported (weak floater label): {int(df.unsupported.sum()):,} "
          f"of {N:,} = {df.unsupported.mean() * 100:.2f}%")


if __name__ == "__main__":
    main()
