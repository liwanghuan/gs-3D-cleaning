#!/usr/bin/env python3
"""
Build the L2 label: distance from each Gaussian centre to the Tanks & Temples
laser scan, inside the official crop only.

Writes a separate label table (gaussian_id, in_crop, dist_to_scan_m,
unsupported_scan) so the T1 feature table stays untouched. Outside the crop
the label is missing, never 0.

Usage:
    python src/scan_label.py --config configs/L2_scan_label.yaml
"""

import argparse
import hashlib
import json
import os
import sys
import numpy as np
import pandas as pd
import yaml
from plyfile import PlyData
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from align_reference import crop_mask, apply  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    fcfg = yaml.safe_load(open(cfg["features_config"]))
    acfg = yaml.safe_load(open(cfg["align_config"]))
    tau = cfg["tau_scan_m"]

    df = pd.read_parquet(fcfg["out"], columns=["gaussian_id", "x", "y", "z", "unsupported"])
    N = len(df)
    T = np.loadtxt(acfg["out_matrix"])
    crop = json.load(open(acfg["tnt_crop"]))

    xyz = apply(T, df[["x", "y", "z"]].to_numpy(np.float64))
    in_crop = crop_mask(xyz, crop)

    v = PlyData.read(acfg["tnt_gt"])["vertex"]
    scan = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    scan = scan[crop_mask(scan, crop)]
    d = np.full(N, np.nan)
    d[in_crop], _ = cKDTree(scan).query(xyz[in_crop], k=1, workers=-1)

    lab = pd.array(np.where(in_crop, (d > tau).astype(np.int8), 0), dtype="Int8")
    lab[~in_crop] = pd.NA
    out = pd.DataFrame({
        "gaussian_id": df.gaussian_id.to_numpy(),
        "in_crop": in_crop,
        "dist_to_scan_m": d,
        "unsupported_scan": lab,
    })
    os.makedirs(os.path.dirname(cfg["out"]), exist_ok=True)
    out.to_parquet(cfg["out"], index=False)
    h = hashlib.sha256(open(cfg["out"], "rb").read()).hexdigest()

    n_in = int(in_crop.sum())
    pos = int((d[in_crop] > tau).sum())
    print(f"Gaussians N = {N:,}; scan points inside crop = {len(scan):,}")
    print(f"inside crop (labelled): {n_in:,} ({n_in / N * 100:.2f}%); "
          f"outside (label missing): {N - n_in:,}")
    print(f"tau = {tau} m")
    print(f"unsupported_scan = 1: {pos:,} of {n_in:,} ({pos / n_in * 100:.2f}%)")
    q = np.percentile(d[in_crop], [5, 25, 50, 75, 95, 99])
    print("dist_to_scan_m, in crop: " + "  ".join(
        f"p{p} {x:.4f}" for p, x in zip((5, 25, 50, 75, 95, 99), q)))

    y1 = df.unsupported.to_numpy()[in_crop]
    y2 = (d[in_crop] > tau).astype(int)
    ct = pd.crosstab(pd.Series(y1, name="L1 unsupported"),
                     pd.Series(y2, name="L2 unsupported_scan"))
    print("\nL1 vs L2 inside the crop (counts):")
    print(ct)
    tp = int(((y1 == 1) & (y2 == 1)).sum())
    print(f"agreement {np.mean(y1 == y2) * 100:.2f}%; of L2 positives, L1 also flags "
          f"{tp / max(y2.sum(), 1) * 100:.2f}%; of L1 positives, L2 also flags "
          f"{tp / max(y1.sum(), 1) * 100:.2f}%")
    print(f"\nwrote {cfg['out']}  sha256 {h}")


if __name__ == "__main__":
    main()
