#!/usr/bin/env python3
"""
T4 floaters: AUC of each feature against the L2 laser-scan label inside the
official crop, pooled and within depth strata, with L1 on the same Gaussians
for comparison; then where the label-positive Gaussians that the best
feature calls clearly real actually sit.

Usage:
    python src/floaters_t4.py --config configs/T4_floaters.yaml
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import yaml
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_features import load_gaussians, load_colmap, select_views  # noqa: E402
from confound import auc_mann_whitney  # noqa: E402
from diagnose_contrib_ratio import per_view_geometry  # noqa: E402
from align_reference import apply  # noqa: E402
from layer_split import layer_wire_rest  # noqa: E402
import make_plots as mp  # noqa: E402  (figure size, dpi, palette)
import matplotlib.pyplot as plt  # noqa: E402


def roc_curve(score, y):
    """ROC with tied scores grouped into one step (no arbitrary tie order)."""
    order = np.argsort(-score, kind="mergesort")
    s, yy = score[order], y[order]
    last = np.r_[np.nonzero(np.diff(s))[0], len(s) - 1]   # end of each tie group
    tp = np.cumsum(yy)[last]
    fp = (last + 1) - tp
    return np.r_[0, fp / fp[-1]], np.r_[0, tp / tp[-1]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    fcfg = yaml.safe_load(open(cfg["features_config"]))
    lcfg = yaml.safe_load(open(cfg["label_config"]))
    acfg = yaml.safe_load(open(cfg["align_config"]))
    proj = fcfg["projection"]
    feats = cfg["features"]

    df = pd.read_parquet(fcfg["out"])
    lab = pd.read_parquet(lcfg["out"])
    assert np.array_equal(df.gaussian_id.to_numpy(), lab.gaussian_id.to_numpy())

    in_crop = lab.in_crop.to_numpy()
    seen = df.view_count.to_numpy() > 0
    unseen_in_crop = int((in_crop & ~seen).sum())
    unseen_pos = int(((lab.unsupported_scan == 1).to_numpy(na_value=False) & ~seen).sum())
    scope = in_crop & (seen if cfg["exclude_unseen"] else True)
    if cfg.get("exclude_wire_config"):
        wire_idx, _ = layer_wire_rest(cfg["exclude_wire_config"])
        wire_mask = np.zeros(len(df), bool); wire_mask[wire_idx] = True
        print(f"excluded as human-confirmed wire: {int((scope & wire_mask).sum()):,} "
              f"(all L2-positive: {bool(np.all((lab.unsupported_scan[wire_mask] == 1).to_numpy(dtype=bool, na_value=False)))})")
        scope &= ~wire_mask
    print(f"N = {len(df):,}; in crop = {int(in_crop.sum()):,}; "
          f"excluded unseen in crop = {unseen_in_crop:,} ({unseen_pos:,} of them L2-positive)")

    d = df[scope].reset_index(drop=True)
    y2 = lab.unsupported_scan[scope].astype(int).to_numpy()
    y1 = d.unsupported.to_numpy()
    print(f"scope N = {len(d):,}; L2 positives = {int(y2.sum()):,} ({y2.mean() * 100:.2f}%); "
          f"L1 positives = {int(y1.sum()):,}")

    def score(sub, f):
        s = sub[f].to_numpy(np.float64)
        return s if feats[f] == "high" else -s

    # depth strata inside the scope
    g = load_gaussians(fcfg["ply"])
    cams, _ = load_colmap(fcfg["colmap"], proj["train_max_width"], fcfg["eval_holdout"])
    cams = select_views(cams, fcfg["max_views"])
    acc = per_view_geometry(g, cams, proj)
    assert np.array_equal(acc["seen_n"], df.view_count.to_numpy())
    depth = (acc["z_sum"][scope] / d.view_count.to_numpy())
    edges = np.quantile(depth, np.linspace(0, 1, cfg["n_strata"] + 1))
    strat = np.clip(np.searchsorted(edges, depth, side="right") - 1, 0, cfg["n_strata"] - 1)

    # ---- AUC table
    rows, strata_rows = [], []
    for f in feats:
        s = score(d, f)
        a2 = auc_mann_whitney(s, y2)[0]
        a1 = auc_mann_whitney(s, y1)[0]
        ws, aucs = [], []
        for k in range(cfg["n_strata"]):
            m = strat == k
            npos, nneg = int(y2[m].sum()), int(m.sum() - y2[m].sum())
            a = auc_mann_whitney(s[m], y2[m])[0] if min(npos, nneg) >= cfg["min_per_class"] else np.nan
            strata_rows.append(dict(feature=f, stratum=k + 1, depth_lo=edges[k], depth_hi=edges[k + 1],
                                    N=int(m.sum()), n_pos=npos, auc_L2=a))
            if not np.isnan(a):
                ws.append(m.sum()); aucs.append(a)
        within = float(np.average(aucs, weights=ws)) if ws else np.nan
        rows.append(dict(feature=f, artefact_if=feats[f], auc_L2_pooled=a2,
                         auc_L2_within_depth=within, strata_used=len(ws),
                         strata_below_0_5=int(np.sum(np.array(aucs) < 0.5)),
                         auc_L1_same_gaussians=a1))
    t = pd.DataFrame(rows)
    st = pd.DataFrame(strata_rows)
    fmt = dict(display_width=250)
    with pd.option_context("display.width", 250, "display.max_columns", None,
                           "display.float_format", "{:.4f}".format):
        print("\n[1] AUC against L2 (pooled and within depth), and against L1 on the same Gaussians")
        print(t.to_string(index=False))
        print("\n    per stratum (L2):")
        print(st.pivot(index=["stratum", "depth_lo", "depth_hi", "N", "n_pos"],
                       columns="feature", values="auc_L2").reset_index().to_string(index=False))
    thr = cfg["suspicious_auc"]
    hi = t[(t.auc_L2_pooled > thr) | (t.auc_L2_within_depth > thr)]
    hs = st[st.auc_L2 > thr]
    print(f"\n    AUC > {thr} (pooled or depth-weighted): {'none' if hi.empty else ', '.join(hi.feature)}")
    print(f"    AUC > {thr} in any single stratum: "
          + ("none" if hs.empty else "; ".join(f"{r.feature} stratum {r.stratum} ({r.auc_L2:.4f})"
                                               for r in hs.itertuples())))

    # ---- ROC figure (pooled, L2)
    fig, ax = plt.subplots(figsize=mp.FIGSIZE, dpi=mp.DPI)
    colours = [mp.ACCENT, mp.VERIF, mp.MUTED, mp.INK]
    for (f, c) in zip(feats, colours):
        fpr, tpr = roc_curve(score(d, f), y2)
        a = t.set_index("feature").auc_L2_pooled[f]
        ax.plot(fpr, tpr, color=c, lw=1.8, label=f"{f}  (AUC {a:.3f})")
    ax.plot([0, 1], [0, 1], color=mp.RULE, lw=1, ls="--")
    ax.set_xlabel("false positive rate"); ax.set_ylabel("true positive rate")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_title(f"L2 laser-scan label, inside crop, seen  (N = {len(d):,}; positives {int(y2.sum()):,})",
                 fontsize=10, color=mp.MUTED, loc="left")
    ax.legend(frameon=False, loc="lower right", fontsize=9.5)
    fig.tight_layout(); fig.savefig(cfg["figure"], dpi=mp.DPI); plt.close(fig)
    print(f"\n    wrote {cfg['figure']}")

    # ---- false-positive diagnostic
    best = t.sort_values("auc_L2_within_depth", ascending=False).feature.iloc[0]
    sb = score(d, best)
    real = sb <= np.percentile(sb, cfg["clearly_real_pct"])
    fp = (y2 == 1) & real
    other_pos = (y2 == 1) & ~real
    neg = y2 == 0
    print(f"\n[2] best feature by within-depth AUC: {best}")
    print(f"    clearly real = {best} artefact score <= p{cfg['clearly_real_pct']} "
          f"({int(real.sum()):,} Gaussians)")
    print(f"    studied set: L2-positive AND clearly real = {int(fp.sum()):,} "
          f"of {int(y2.sum()):,} L2 positives ({fp.sum() / max(y2.sum(), 1) * 100:.2f}%)")

    # colour: sh_dc_norm (spec) and neighbour colour std (beyond spec)
    all_xyz = g["xyz"]
    idx_scope = np.nonzero(scope)[0]
    _, nb = cKDTree(all_xyz).query(all_xyz[idx_scope], k=cfg["texture_knn"] + 1, workers=-1)
    tex = g["sh_dc"][nb[:, 1:]].std(axis=1).mean(axis=1)

    T = np.loadtxt(acfg["out_matrix"])
    xyz_gt = apply(T, d[["x", "y", "z"]].to_numpy(np.float64))
    dist = lab.dist_to_scan_m[scope].to_numpy()

    grp = {"L2+ & clearly real (studied)": fp, "other L2+": other_pos, "L2-": neg}
    rows = []
    for name, m in grp.items():
        rows.append(dict(group=name, N=int(m.sum()),
                         dist_to_scan_med=np.median(dist[m]),
                         sh_dc_norm_med=np.median(d.sh_dc_norm[m]),
                         nbr_colour_std_med=np.median(tex[m]),
                         scan_z_p10=np.percentile(xyz_gt[m, 2], 10),
                         scan_z_med=np.median(xyz_gt[m, 2]),
                         scan_z_p90=np.percentile(xyz_gt[m, 2], 90),
                         depth_med=np.median(depth[m]),
                         view_count_med=np.median(d.view_count[m])))
    with pd.option_context("display.width", 250, "display.max_columns", None,
                           "display.float_format", "{:.4g}".format):
        print(pd.DataFrame(rows).to_string(index=False))

    # tests: studied set vs L2 negatives
    for col, vals in (("sh_dc_norm", d.sh_dc_norm.to_numpy()), ("nbr_colour_std", tex)):
        a = auc_mann_whitney(-vals[fp | neg], fp[fp | neg].astype(int))[0]
        print(f"    P({col} lower in studied set than in L2-) = {a:.4f}  (0.5 = no difference)")
    # spatial clustering: nearest studied neighbour vs nearest L2- neighbour distance
    if fp.sum() > 1:
        dd, _ = cKDTree(xyz_gt[fp]).query(xyz_gt[fp], k=2)
        rng = np.random.default_rng(0)
        pick = rng.choice(np.nonzero(neg)[0], size=int(fp.sum()), replace=False)
        dn, _ = cKDTree(xyz_gt[pick]).query(xyz_gt[pick], k=2)
        print(f"    spatial clustering: median NN distance within studied set {np.median(dd[:, 1]):.4f} m "
              f"vs equal-size random L2- sample {np.median(dn[:, 1]):.4f} m (seed 0)")

    # top view + height figure
    fig, (a1, a2) = plt.subplots(1, 2, figsize=mp.FIGSIZE, dpi=mp.DPI,
                                 gridspec_kw=dict(width_ratios=[1.4, 1]))
    sub = np.random.default_rng(0).choice(len(d), size=min(60000, len(d)), replace=False)
    a1.scatter(xyz_gt[sub, 0], xyz_gt[sub, 1], s=0.3, c=mp.RULE, lw=0, label="in scope (sample)")
    a1.scatter(xyz_gt[other_pos, 0], xyz_gt[other_pos, 1], s=2, c=mp.VERIF, lw=0, label="other L2+")
    a1.scatter(xyz_gt[fp, 0], xyz_gt[fp, 1], s=2, c=mp.ACCENT, lw=0, label="L2+ but clearly real")
    a1.set_aspect("equal"); a1.set_xlabel("scan x (m)"); a1.set_ylabel("scan y (m)")
    a1.legend(frameon=False, fontsize=8, markerscale=4, loc="upper right")
    bins = np.linspace(np.percentile(xyz_gt[:, 2], 0.5), np.percentile(xyz_gt[:, 2], 99.5), 40)
    for m, c, lbl in ((neg, mp.RULE, "L2-"), (other_pos, mp.VERIF, "other L2+"), (fp, mp.ACCENT, "studied")):
        a2.hist(xyz_gt[m, 2], bins=bins, density=True, histtype="step", color=c, lw=1.6, label=lbl)
    a2.set_xlabel("scan z (m)"); a2.set_ylabel("density"); a2.legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(cfg["figure_fp"], dpi=mp.DPI); plt.close(fig)
    print(f"    wrote {cfg['figure_fp']}")


if __name__ == "__main__":
    main()
