#!/usr/bin/env python3
"""
Protocol v1 evaluation of one scene (configs/protocol_v1.yaml), against the
L1 COLMAP label. Every setting comes from the protocol; nothing is chosen here.

  [T3] near/far-init split: unsupported rate per group, AUC on far-init alone
  [T4] AUC per signal (4 original features + 4 pre-registered new signals):
       pooled, N-weighted mean within depth strata, per stratum;
       any AUC > suspicious_auc (pooled or any stratum) is flagged for a
       shared-input check before it may be reported.

Unseen Gaussians (view_count == 0) are excluded from every AUC; count reported.
Writes out/reports/protocol_v1/<scene>_auc.csv and _strata.csv.

Usage:
    python src/evaluate_scene.py --config configs/T1_<scene>.yaml
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import yaml
from plyfile import PlyData
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from confound import auc_mann_whitney  # noqa: E402

PROTOCOL = "configs/protocol_v1.yaml"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    P = yaml.safe_load(open(PROTOCOL))
    scene = cfg["scene"]
    E = P["evaluation"]

    dirs = dict(P["features"]["directions"])
    dirs.update({k: v["direction"] for k, v in P["new_signals"].items()})

    df = pd.read_parquet(cfg["out"])
    ex = pd.read_parquet(cfg["out"].replace(".parquet", "_extra.parquet"))
    assert np.array_equal(df.gaussian_id.to_numpy(), ex.gaussian_id.to_numpy())
    df = pd.concat([df, ex.drop(columns="gaussian_id")], axis=1)
    N = len(df)
    y_all = df.unsupported.to_numpy()
    print(f"[{scene}] N = {N:,}; L1 unsupported = {int(y_all.sum()):,} "
          f"({y_all.mean() * 100:.2f}%)")

    # ---------------- T3 confound
    init_ply = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(cfg["ply"]))),
                            "input.ply")
    v = PlyData.read(init_ply)["vertex"]
    init = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    tree = cKDTree(init)
    spacing = float(np.median(tree.query(init, k=2, workers=-1)[0][:, 1]))
    d_init = tree.query(df[["x", "y", "z"]].to_numpy(np.float64), k=1, workers=-1)[0]
    far = d_init > P["confound_T3"]["near_init_spacing_mult"] * spacing
    same = float(np.abs(d_init - df.dist_to_reference.to_numpy()).max())
    print(f"\n[T3] init points {len(init):,}; median init spacing {spacing:.5g}; "
          f"max |d_init - d_ref| = {same:.3g} (0 => init cloud == reference)")
    for name, m in (("near-init", ~far), ("far-init", far)):
        print(f"  {name:<9} N = {int(m.sum()):>10,} ({m.mean() * 100:5.2f}%)  "
              f"unsupported = {int(y_all[m].sum()):,} ({y_all[m].mean() * 100:.2f}%)")

    # ---------------- scope
    seen = df.view_count.to_numpy() > 0
    print(f"\nscope: seen by >= 1 of {cfg['max_views']} views = {int(seen.sum()):,}; "
          f"excluded unseen = {int((~seen).sum()):,} "
          f"(of which L1+ {int(y_all[~seen].sum()):,})")
    d = df[seen].reset_index(drop=True)
    far_s = far[seen]
    y = d.unsupported.to_numpy()

    S = E["depth_strata"]
    edges = np.quantile(d.mean_depth, np.linspace(0, 1, S["n"] + 1))
    strat = np.clip(np.searchsorted(edges, d.mean_depth, side="right") - 1, 0, S["n"] - 1)

    def score(sub, f):
        s = sub[f].to_numpy(np.float64)
        return s if dirs[f] == "high" else -s

    srows = []
    for k in range(S["n"]):
        m = strat == k
        ys = y[m]
        npos, nneg = int(ys.sum()), int(len(ys) - ys.sum())
        ok = min(npos, nneg) >= S["min_per_class"]
        row = dict(scene=scene, stratum=k + 1, depth_lo=edges[k], depth_hi=edges[k + 1],
                   N=int(m.sum()), n_pos=npos, n_neg=nneg, used=ok)
        for f in dirs:
            row[f] = auc_mann_whitney(score(d[m], f), ys)[0] if ok else np.nan
        srows.append(row)
    st = pd.DataFrame(srows)
    used = st[st.used]

    rows = []
    for f in dirs:
        s = score(d, f)
        a, npos, nneg = auc_mann_whitney(s, y)
        a_far = auc_mann_whitney(s[far_s], y[far_s])[0]
        w = used.N
        within = float((used[f] * w).sum() / w.sum()) if len(used) else np.nan
        flag = (a > E["suspicious_auc"]) or bool((used[f] > E["suspicious_auc"]).any())
        rows.append(dict(scene=scene, feature=f, artefact_if=dirs[f],
                         auc_pooled=a, auc_within_depth=within, auc_far_init=a_far,
                         strata_used=len(used), strata_below_0_5=int((used[f] < 0.5).sum()),
                         stratum_min=used[f].min(), stratum_max=used[f].max(),
                         n_pos=npos, n_neg=nneg, n_pos_far=int(y[far_s].sum()),
                         n_far=int(far_s.sum()), suspicious=flag))
    t = pd.DataFrame(rows)

    with pd.option_context("display.width", 250, "display.max_columns", None,
                           "display.float_format", "{:.4f}".format):
        print(f"\n[strata] {S['n']} equal-count bins of mean camera depth; "
              f"used {len(used)} (min {S['min_per_class']} per class)")
        print(st.drop(columns="scene").to_string(index=False))
        print("\n[AUC] against L1 `unsupported` (seen only)")
        print(t.drop(columns="scene").to_string(index=False))
    if t.suspicious.any():
        print("\n!! AUC above", E["suspicious_auc"], "for:",
              ", ".join(t.feature[t.suspicious]), "-> shared-input check required")

    os.makedirs("out/reports/protocol_v1", exist_ok=True)
    t.to_csv(f"out/reports/protocol_v1/{scene}_auc.csv", index=False)
    st.to_csv(f"out/reports/protocol_v1/{scene}_strata.csv", index=False)


if __name__ == "__main__":
    main()
