#!/usr/bin/env python3
"""
T2 sanity checks on real data, before any analysis (AGENTS.md T2).

  1. quaternion -> rotation matrices are orthonormal
  2. an isotropic-scale Gaussian has covariance s^2 I under any rotation
  3. view_count is 0 for Gaussians behind every camera
  4. re-running extraction on identical input is bitwise identical
  5. reference points and Gaussians share a coordinate frame (bbox overlap)
     5b (beyond the spec): the model's own init cloud coincides with points3D

Usage:
    python src/checks.py --config configs/T2_checks.yaml
"""

import argparse
import hashlib
import os
import subprocess
import sys
import numpy as np
import pandas as pd
import yaml
from plyfile import PlyData
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_features import (  # noqa: E402
    load_gaussians, quats_to_R, covariance_3d, evidential_features_cpu,
    load_colmap, select_views,
)

RESULTS = []


def record(name, passed, detail):
    RESULTS.append((name, passed, detail))
    print(f"  {'PASS' if passed else 'FAIL'}  {detail}")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------------------
def check_orthonormal(g, tol):
    print("\n[1] quaternion -> rotation orthonormality")
    R = quats_to_R(g["quats"]).astype(np.float64)
    dev = np.abs(np.einsum("nij,nkj->nik", R, R) - np.eye(3)).max(axis=(1, 2))
    det = np.linalg.det(R)
    n = len(R)
    worst = float(dev.max())
    print(f"  N = {n:,}; max |R R^T - I| = {worst:.3e}; median = {np.median(dev):.3e}")
    print(f"  det(R): min {det.min():.7f}  max {det.max():.7f}")
    record("1 orthonormal", worst < tol and det.min() > 0,
           f"max deviation {worst:.3e} vs tol {tol:.0e}; det in [{det.min():.6f}, {det.max():.6f}]")


def check_isotropic(g, tol):
    print("\n[2] isotropic scale -> s^2 I under every real rotation")
    s = g["scales"].max(axis=1)                       # one real scale per Gaussian
    iso = dict(g, scales=np.repeat(s[:, None], 3, axis=1))
    cov = covariance_3d(iso).astype(np.float64)
    s2 = (s.astype(np.float64) ** 2)[:, None, None]
    rel = np.abs(cov - s2 * np.eye(3)).max(axis=(1, 2)) / s2[:, 0, 0]
    worst = float(rel.max())
    print(f"  N = {len(rel):,}; max |Sigma - s^2 I| / s^2 = {worst:.3e}; median = {np.median(rel):.3e}")
    record("2 isotropic", worst < tol, f"max relative deviation {worst:.3e} vs tol {tol:.0e}")


def check_behind(g, cams, proj, df, offset_mult):
    print("\n[3] view_count == 0 for Gaussians behind every camera")
    near = proj["near_plane"]

    # (a) real Gaussians: in front of no sampled camera
    xyz = g["xyz"].astype(np.float64)
    in_front_any = np.zeros(len(xyz), bool)
    for c in cams:
        z = xyz @ c["R"][2] + c["t"][2]
        in_front_any |= z > near
    behind_all = ~in_front_any
    n_behind = int(behind_all.sum())
    print(f"  real: {n_behind:,} of {len(xyz):,} Gaussians are behind all {len(cams)} sampled views")
    if n_behind:
        bad = int((df.view_count.values[behind_all] != 0).sum())
        record("3a real behind-all", bad == 0,
               f"{n_behind:,} real Gaussians behind every view; {bad} have view_count != 0")
    else:
        record("3a real behind-all", True,
               "no real Gaussian is behind every sampled view (none exist), so nothing to test on real data")

    # (b) synthetic: one Gaussian behind each camera, tested against that camera
    # alone, so it is behind every camera in its view set by construction.
    bad, n = 0, 0
    for c in cams:
        Rwc = c["R"]
        centre = -Rwc.T @ c["t"]
        fwd = Rwc[2]                                   # camera +z in world
        p = (centre - offset_mult * near * fwd)[None].astype(np.float32)
        syn = dict(xyz=p, opacity=np.ones(1, np.float32),
                   scales=np.full((1, 3), 0.05, np.float32),
                   quats=np.array([[1, 0, 0, 0]], np.float32),
                   sh_dc=np.zeros((1, 3), np.float32))
        out = evidential_features_cpu(syn, covariance_3d(syn), [c], proj)
        n += 1
        bad += int(out.view_count.iloc[0] != 0)
    record("3b synthetic behind", bad == 0,
           f"{n} synthetic Gaussians, each {offset_mult:g} x near plane behind one camera; {bad} counted as seen")


def check_rerun(cfg_path, rerun_dir, t1_sha):
    print("\n[4] bitwise-identical re-run")
    os.makedirs(rerun_dir, exist_ok=True)
    paths = [os.path.join(rerun_dir, f"run{i}.parquet") for i in (1, 2)]
    for p in paths:
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "extract_features.py"),
                        "--config", cfg_path, "--out", p],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    h = [sha256(p) for p in paths]
    for p, x in zip(paths, h):
        print(f"  {x}  {p}")
    print(f"  {t1_sha}  (T1 run, recorded)")
    same = h[0] == h[1]
    record("4 rerun identical", same,
           f"two fresh runs {'identical' if same else 'DIFFER'}; "
           f"{'match' if h[0] == t1_sha else 'do NOT match'} the T1 hash")
    return paths[0]


def box_overlap(a_lo, a_hi, b_lo, b_hi):
    inter = np.clip(np.minimum(a_hi, b_hi) - np.maximum(a_lo, b_lo), 0, None).prod()
    return inter / (a_hi - a_lo).prod(), inter / (b_hi - b_lo).prod()


def check_frame(g, ref, pct):
    print("\n[5] reference points vs Gaussians: same coordinate frame?")
    G, P = g["xyz"].astype(np.float64), ref.astype(np.float64)
    boxes = {
        "raw min/max": (G.min(0), G.max(0), P.min(0), P.max(0)),
        f"p{pct[0]}-p{pct[1]}": (*np.percentile(G, pct, axis=0), *np.percentile(P, pct, axis=0)),
    }
    for name, (glo, ghi, plo, phi) in boxes.items():
        of_ref, of_g = box_overlap(plo, phi, glo, ghi)
        print(f"  {name}:")
        print(f"    Gaussians  lo {np.round(glo, 3)}  hi {np.round(ghi, 3)}")
        print(f"    reference  lo {np.round(plo, 3)}  hi {np.round(phi, 3)}")
        print(f"    intersection = {of_ref * 100:.2f}% of reference box, {of_g * 100:.2f}% of Gaussian box")
        boxes[name] = (of_ref, of_g)
    of_ref, of_g = boxes[f"p{pct[0]}-p{pct[1]}"]
    med_g, med_p = np.median(G, 0), np.median(P, 0)
    print(f"  median centre: Gaussians {np.round(med_g, 3)}  reference {np.round(med_p, 3)}")
    record("5 same frame", of_ref > 0 and of_g > 0,
           f"robust boxes overlap: {of_ref * 100:.2f}% of reference box, {of_g * 100:.2f}% of Gaussian box")


def check_init_cloud(init_path, ref, tol):
    print("\n[5b] model's initial point cloud vs COLMAP points3D")
    v = PlyData.read(init_path)["vertex"]
    init = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    d, _ = cKDTree(ref.astype(np.float64)).query(init, k=1, workers=-1)
    print(f"  init points N = {len(init):,}; reference points N = {len(ref):,}")
    print(f"  NN distance init -> reference: max {d.max():.3e}  median {np.median(d):.3e}")
    record("5b init cloud", len(init) == len(ref) and d.max() < tol,
           f"{len(init):,} init vs {len(ref):,} reference points; max NN distance {d.max():.3e} vs tol {tol:.0e}")


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    fcfg = yaml.safe_load(open(cfg["features_config"]))

    g = load_gaussians(fcfg["ply"])
    cams, ref = load_colmap(fcfg["colmap"], fcfg["projection"]["train_max_width"],
                            fcfg["eval_holdout"])
    cams = select_views(cams, fcfg["max_views"])
    print(f"{len(g['xyz']):,} Gaussians, {len(cams)} views, {len(ref):,} reference points")

    check_orthonormal(g, cfg["orthonormal_tol"])
    check_isotropic(g, cfg["isotropic_rel_tol"])
    rerun = check_rerun(cfg["features_config"], cfg["rerun_dir"], cfg["t1_parquet_sha256"])
    df = pd.read_parquet(rerun, columns=["view_count"])
    check_behind(g, cams, fcfg["projection"], df, cfg["behind_offset_near_mult"])
    check_frame(g, ref, cfg["bbox_robust_pct"])
    check_init_cloud(cfg["init_ply"], ref, cfg["init_match_tol"])

    print("\nsummary:")
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    sys.exit(0 if all(ok for _, ok, _ in RESULTS) else 1)


if __name__ == "__main__":
    main()
