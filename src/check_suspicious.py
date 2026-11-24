#!/usr/bin/env python3
"""
Shared-input check for a stratum flagged AUC > 0.98 (protocol v1,
evaluation.suspicious_auc). Rebuilds the stratum exactly as
src/evaluate_scene.py does and describes its L1 positives vs negatives:
view_count, max parallax, distance to reference, position relative to the
scene centre (median of COLMAP points) and to the camera ring.

Usage:
    python src/check_suspicious.py --config configs/T1_garden.yaml --stratum 3
"""
import argparse
import os
import sys
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_features import load_colmap, select_views  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--stratum", type=int, required=True)
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    P = yaml.safe_load(open("configs/protocol_v1.yaml"))
    df = pd.read_parquet(cfg["out"])
    ex = pd.read_parquet(cfg["out"].replace(".parquet", "_extra.parquet"))
    df = pd.concat([df, ex.drop(columns="gaussian_id")], axis=1)
    d = df[df.view_count > 0].reset_index(drop=True)
    n = P["evaluation"]["depth_strata"]["n"]
    edges = np.quantile(d.mean_depth, np.linspace(0, 1, n + 1))
    st = np.clip(np.searchsorted(edges, d.mean_depth, side="right") - 1, 0, n - 1)
    s = d[st == a.stratum - 1]
    proj = cfg["projection"]
    cams, ref = load_colmap(cfg["colmap"], proj["train_max_width"], cfg["eval_holdout"],
                            proj.get("train_height"))
    centres = np.stack([-c["R"].T @ c["t"] for c in cams])
    c0 = np.median(ref, axis=0)
    ring = np.median(np.linalg.norm(centres - c0, axis=1))
    xyz = s[["x", "y", "z"]].to_numpy()
    s = s.assign(r_from_centre=np.linalg.norm(xyz - c0, axis=1) / ring)
    print(f"stratum {a.stratum}: depth {edges[a.stratum-1]:.3f}-{edges[a.stratum]:.3f}, N={len(s):,}; "
          f"camera ring radius (median, all {len(cams)} train cams) = {ring:.3f}")
    cols = ["view_count", "max_parallax_deg", "dist_to_reference", "r_from_centre",
            "opacity", "isolation", "contrib_F1"]
    q = s.groupby("unsupported")[cols].quantile([0.1, 0.5, 0.9]).unstack()
    with pd.option_context("display.width", 250, "display.max_columns", None,
                           "display.float_format", "{:.3f}".format):
        for c in cols:
            print(f"\n{c} (p10/p50/p90) by L1 label (0 = supported, 1 = unsupported):")
            print(q[c].to_string())
    pos = s[s.unsupported == 1]
    print(f"\nL1+ in stratum: {len(pos):,}; with view_count <= 2: "
          f"{int((pos.view_count <= 2).sum()):,}; outside camera ring (r > 1): "
          f"{int((pos.r_from_centre > 1).sum()):,}")
    neg = s[s.unsupported == 0]
    print(f"L1- in stratum: {len(neg):,}; with view_count <= 2: "
          f"{int((neg.view_count <= 2).sum()):,}; outside camera ring: "
          f"{int((neg.r_from_centre > 1).sum()):,}")


if __name__ == "__main__":
    main()
