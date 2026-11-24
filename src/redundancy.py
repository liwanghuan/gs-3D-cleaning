#!/usr/bin/env python3
"""
Redundancy between signals (protocol v1): Spearman rank correlation, over
seen Gaussians, of each pair among view_count, contrib_F1, max_parallax_deg,
isolation, contrib_ratio, contrib_F2 — per scene. A new signal that is a
monotone re-expression of view_count adds no independent evidence.
A fixed random subsample (seed 0, 500,000) keeps it fast; N is printed.

Usage:
    python src/redundancy.py
"""
import numpy as np
import pandas as pd
import yaml
from scipy.stats import spearmanr

COLS = ["view_count", "contrib_F1", "max_parallax_deg", "isolation",
        "contrib_ratio", "contrib_F2"]


def main():
    P = yaml.safe_load(open("configs/protocol_v1.yaml"))
    rows = []
    for s in P["scenes"]:
        cfg = yaml.safe_load(open(f"configs/T1_{s}.yaml"))
        a = pd.read_parquet(cfg["out"], columns=["view_count", "isolation", "contrib_ratio"])
        b = pd.read_parquet(cfg["out"].replace(".parquet", "_extra.parquet"),
                            columns=["contrib_F1", "max_parallax_deg", "contrib_F2"])
        d = pd.concat([a, b], axis=1)
        d = d[d.view_count > 0]
        d = d.sample(n=min(500_000, len(d)), random_state=0)
        r = spearmanr(d[COLS].to_numpy()).statistic
        for i in range(len(COLS)):
            for j in range(i + 1, len(COLS)):
                rows.append(dict(scene=s, pair=f"{COLS[i]} ~ {COLS[j]}", rho=r[i, j], N=len(d)))
    t = pd.DataFrame(rows).pivot(index="pair", columns="scene", values="rho")[list(P["scenes"])]
    print("Spearman rho over seen Gaussians (random 500,000 per scene, seed 0)\n")
    with pd.option_context("display.width", 200, "display.float_format", "{:+.3f}".format):
        print(t.to_string())


if __name__ == "__main__":
    main()
