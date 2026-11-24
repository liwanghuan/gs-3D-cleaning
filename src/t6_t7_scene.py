#!/usr/bin/env python3
"""
Protocol v1, T6 (dilation) and T7 (coverage) for one scene.

T6: median shift (unsupported minus supported, in decades of log10) of
    volume, scale_max, anisotropy, and the raw shift of planarity, with a
    percentile bootstrap CI (protocol: n, seed, ci). Seen Gaussians only,
    as for every label comparison in protocol v1. Correlational only.
T7: cumulative distribution of view_frac, share seen by fewer than
    `few_views_threshold` views (all Gaussians, unseen included, since
    coverage is the point), and the distribution of angular_spread and
    max_parallax_deg from the _extra parquet.

Figures go to out/figures/protocol_v1/<scene>_{3_dilation,4_coverage}.png
at 7.4 x 4.3 in, 200 dpi.

Usage:
    python src/t6_t7_scene.py --config configs/T1_<scene>.yaml
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_plots import FIGSIZE, DPI, INK, ACCENT, VERIF, MUTED, RULE  # noqa: E402,F401

PROTOCOL = "configs/protocol_v1.yaml"


def boot_median_shift(a, b, n, rng, ci):
    """Percentile bootstrap CI of median(b) - median(a)."""
    est = np.median(b) - np.median(a)
    out = np.empty(n)
    for i in range(n):
        out[i] = (np.median(rng.choice(b, len(b))) - np.median(rng.choice(a, len(a))))
    lo, hi = np.percentile(out, [(100 - ci) / 2, 100 - (100 - ci) / 2])
    return est, lo, hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    P = yaml.safe_load(open(PROTOCOL))
    scene = cfg["scene"]
    B, C = P["dilation_T6"], P["coverage_T7"]

    df = pd.read_parquet(cfg["out"], columns=["volume", "scale_max", "anisotropy",
                                               "planarity", "view_count", "view_frac",
                                               "unsupported"])
    ex = pd.read_parquet(cfg["out"].replace(".parquet", "_extra.parquet"),
                         columns=["angular_spread", "max_parallax_deg"])
    N = len(df)
    os.makedirs("out/figures/protocol_v1", exist_ok=True)
    os.makedirs("out/reports/protocol_v1", exist_ok=True)

    # ---------------- T6
    seen = df.view_count.to_numpy() > 0
    d = df[seen]
    lab = d.unsupported.to_numpy().astype(bool)
    print(f"[{scene}] T6 scope: seen {int(seen.sum()):,} of {N:,}; "
          f"unsupported {int(lab.sum()):,}, supported {int((~lab).sum()):,}")
    rng = np.random.default_rng(B["bootstrap_seed"])
    rows = []
    for f, log in (("volume", True), ("scale_max", True), ("anisotropy", True),
                   ("planarity", False)):
        x = d[f].to_numpy(np.float64)
        if log:
            x = np.log10(np.maximum(x, 1e-30))
        est, lo, hi = boot_median_shift(x[~lab], x[lab], B["bootstrap_n"], rng, B["ci"])
        rows.append(dict(scene=scene, feature=f, unit="decades" if log else "raw",
                         median_supported=np.median(x[~lab]), median_unsupported=np.median(x[lab]),
                         shift=est, ci_lo=lo, ci_hi=hi,
                         n_unsupported=int(lab.sum()), n_supported=int((~lab).sum())))
        print(f"  {f:<11} shift {est:+.3f} {'dec' if log else 'raw'}  "
              f"{B['ci']}% CI [{lo:+.3f}, {hi:+.3f}]")
    t6 = pd.DataFrame(rows)
    t6.to_csv(f"out/reports/protocol_v1/{scene}_T6.csv", index=False)

    v = np.log10(np.maximum(d.volume.to_numpy(), 1e-30))
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    bins = np.linspace(np.percentile(v, 0.5), np.percentile(v, 99.5), 70)
    ax.hist(v[~lab], bins=bins, color=VERIF, alpha=0.6, density=True,
            label=f"supported (N={int((~lab).sum()):,})")
    ax.hist(v[lab], bins=bins, color=ACCENT, alpha=0.6, density=True,
            label=f"L1 unsupported (N={int(lab.sum()):,})")
    for m, c in ((np.median(v[~lab]), VERIF), (np.median(v[lab]), ACCENT)):
        ax.axvline(m, color=c, lw=1.6, ls="--")
    r = t6.iloc[0]
    ax.set_title(f"{scene}: median shift {r["shift"]:+.2f} decades "
                 f"[{r.ci_lo:+.2f}, {r.ci_hi:+.2f}]", fontsize=11, color=MUTED, loc="left")
    ax.set_xlabel(r"$\log_{10}$ Gaussian volume  $s_x s_y s_z$")
    ax.set_ylabel("density")
    ax.legend(frameon=False, fontsize=10)
    fig.tight_layout()
    fig.savefig(f"out/figures/protocol_v1/{scene}_3_dilation.png", dpi=DPI)
    plt.close(fig)

    # ---------------- T7
    k = C["few_views_threshold"]
    vc = df.view_count.to_numpy()
    few = (vc < k)
    sp = ex.angular_spread.to_numpy()
    par = ex.max_parallax_deg.to_numpy()
    has = ~np.isnan(sp)
    print(f"\n[{scene}] T7: N = {N:,}; seen by < {k} of {cfg['max_views']} views: "
          f"{int(few.sum()):,} ({few.mean() * 100:.2f}%); unseen {int((vc == 0).sum()):,}")
    q = [10, 25, 50, 75, 90]
    sq = np.percentile(sp[has], q)
    pq = np.percentile(par[vc >= 2], q)
    print(f"  angular_spread (seen, N={int(has.sum()):,}) p{q}: "
          + ", ".join(f"{x:.4f}" for x in sq))
    print(f"  max_parallax_deg (seen by >= 2, N={int((vc >= 2).sum()):,}) p{q}: "
          + ", ".join(f"{x:.2f}" for x in pq))
    # many views but nearly parallel rays: the case raw view count misses
    many = vc >= C["many_views"]
    narrow = many & (par < C["narrow_parallax_deg"])
    print(f"  seen by >= {C['many_views']} views but max parallax < {C['narrow_parallax_deg']} deg: {int(narrow.sum()):,} "
          f"({narrow.sum() / max(many.sum(), 1) * 100:.2f}% of N={int(many.sum()):,})")
    t7 = pd.DataFrame([dict(scene=scene, N=N, few_views_threshold=k,
                            n_few=int(few.sum()), pct_few=few.mean() * 100,
                            n_unseen=int((vc == 0).sum()),
                            **{f"spread_p{a}": b for a, b in zip(q, sq)},
                            **{f"parallax_p{a}": b for a, b in zip(q, pq)},
                            n_many=int(many.sum()), n_many_narrow=int(narrow.sum()))])
    t7.to_csv(f"out/reports/protocol_v1/{scene}_T7.csv", index=False)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=FIGSIZE, dpi=DPI)
    vf = np.sort(df.view_frac.to_numpy())
    a1.plot(vf, np.arange(1, N + 1) / N * 100, color=ACCENT, lw=2)
    a1.axhline(few.mean() * 100, color=MUTED, lw=1, ls="--")
    a1.set_title(f"{few.mean() * 100:.1f}% seen in < {k} views (N={N:,})",
                 fontsize=9.5, color=MUTED, loc="left")
    a1.set_xlabel("view fraction"); a1.set_ylabel("cumulative % of Gaussians")
    a1.set_ylim(0, 100)
    a2.hist(par[vc >= 2], bins=np.linspace(0, 180, 61), color=VERIF, alpha=0.8)
    a2.set_title(f"max parallax, seen by ≥ 2 (N={int((vc >= 2).sum()):,})",
                 fontsize=9.5, color=MUTED, loc="left")
    a2.set_xlabel("max parallax angle (deg)"); a2.set_ylabel("Gaussians")
    fig.tight_layout()
    fig.savefig(f"out/figures/protocol_v1/{scene}_4_coverage.png", dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    main()
