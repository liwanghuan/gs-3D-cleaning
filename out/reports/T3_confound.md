# T3 Initialisation confound — truck
Run: 2026-11-10 · config: `configs/T3_confound.yaml` (features from `configs/T1_truck.yaml`, 40 views) · commit: uncommitted, working tree on top of 546c50c

**In one sentence:** restricted to the 89.73 % of Gaussians far from initialisation, the label still separates on `view_frac` (AUC 0.796) and `isolation` (0.690), losing only about 0.035 AUC to the confound. But `contrib_ratio`, the feature the project rests on, separates in the **opposite** direction to the hypothesis (AUC 0.262), and `opacity` carries almost no signal (0.522).

## What I did
I split the Gaussians by distance to the model's own init cloud (`input.ply`), using a radius of 1 × the median init spacing = 0.01129 units. For each group I report `dist_to_reference` and the `unsupported` rate. I then scored the four T4 features against the label on all Gaussians and on far-init only, using a tie-aware rank AUC. The direction counted as "artefact" for each feature was inherited from the starting `make_plots.py` and fixed in the config before running.

## Numbers

**Groups** (N = 2,541,226; radius 0.01129 units; label threshold τ = 0.22589 units)

| Group | N | Share | Unsupported | Rate | dist p5 | p25 | p50 | p75 | p95 |
|---|---|---|---|---|---|---|---|---|---|
| near-init (d ≤ 0.01129) | 260,857 | 10.27 % | 0 | 0.00 % | 0.0018 | 0.0044 | 0.0067 | 0.0089 | 0.0108 |
| far-init (d > 0.01129) | 2,280,369 | 89.73 % | 1,078,846 | 47.31 % | 0.0168 | 0.0761 | 0.2069 | 0.4847 | 1.599 |
| all | 2,541,226 | 100 % | 1,078,846 | 42.45 % | 0.0065 | 0.0422 | 0.1710 | 0.4339 | 1.510 |

**AUC against `unsupported`**
- All Gaussians: N_pos = 1,078,846, N_neg = 1,462,380.
- Far-init only: N_pos = 1,078,846, N_neg = 1,201,523.

| Feature | Artefact if | AUC all | AUC far-init | Δ |
|---|---|---|---|---|
| contrib_ratio | high | 0.2194 | 0.2617 | +0.0423 |
| view_frac | low | 0.8311 | 0.7959 | −0.0352 |
| isolation | high | 0.7260 | 0.6900 | −0.0360 |
| opacity | low | 0.5314 | 0.5224 | −0.0090 |

## What this does and does not show
- **The near/far split is degenerate by construction.** T2 check 5b showed the init cloud is identical to the reference cloud, so distance to init equals `dist_to_reference` (max difference 0). Every near-init Gaussian sits within 1 spacing, and the label needs 20 spacings, so the near-init `unsupported` rate is 0 % automatically. The dist distributions per group are truncated, not independent measurements.
- **The inflation from near-init Gaussians is small.** They are only 10.27 % of the model, all labelled supported. Dropping them moves the AUCs by 0.009 to 0.042. Densification products, the far-init 89.73 %, carry almost all of the signal.
- **This does not remove the circularity.** Within far-init, the label is still a threshold on distance to the same cloud the model grew from. What survives is that features which never touch that cloud (`view_frac`, `isolation`) still differ between the two label groups.
- **`contrib_ratio` runs against the hypothesis, AUC 0.26.** Gaussians the label calls unsupported have *lower* peak-to-mean footprint ratios than supported ones. Either the feature does not mean what §0 assumes, or the label is not measuring floaters here. I have **not** flipped the direction or changed anything, and I have not verified a cause. One untested hypothesis: `unsupported` is dominated by distant background (T1/T2), which is seen from roughly constant distance across views and so has a ratio near 1. Gaussians on the truck are seen at widely varying distances, which inflates their peak-to-mean ratio. If so, `contrib_ratio` partly measures camera-distance variation, not single-view dominance.
- **The label's failure mode in truck points the same way.** `view_frac` and `isolation` separating well is also what you would see if `unsupported` mostly meant "background, sparsely triangulated" rather than "floater". This analysis cannot tell those apart. The laser-scan label inside the official crop (`out/reports/align_truck.md`) could, but using it is pending the professor's decision.
- **Other confounds remain.** `view_frac` comes from 40 views, so it takes only 41 distinct values; ties are handled by the rank AUC. There is no transmittance term. No AUC exceeds 0.98, so the shared-input check in §7 was not triggered.

## What broke
Nothing errored. The first run's console tables were cut off by pandas' column limit. I fixed the display and reran, and the numbers were unchanged. One deviation from the starting code: AUC is the tie-aware Mann–Whitney statistic, not the argsort ROC in `make_plots.py`, because that ROC orders tied scores arbitrarily. T4 should use the same statistic.
