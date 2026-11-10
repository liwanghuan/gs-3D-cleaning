# RESULTS

Running log, newest first. Each entry: three lines. Every number from a committed script + config.

## 2026-11-10 · Depth-stratified AUC · truck · `configs/depth_strata.yaml`
- The unsupported rate rises from 0.13 % (nearest depth decile) to 93.9 % (farthest), each decile N = 253,083, so the label is largely a depth detector here. Report: `out/reports/depth_strata.md`.
- Within depth strata (9 used, N = 2,277,746): view_frac 0.690 and isolation 0.620 still separate in every stratum but lose 0.10–0.14 AUC; opacity 0.518 has no signal.
- contrib_ratio stays inverted (0.397, below 0.5 in 7 of 9 strata). The label barely fires near the cameras, where floaters usually sit.

## 2026-11-10 · Diagnostic: contrib_ratio inversion · truck · `configs/diag_contrib_ratio.yaml`
- No bug, but a definition problem: opacity cancels (max rel. diff 1.5e-7), so the ratio is pure geometry, and it is capped by view_count (0 violations; Spearman 0.797). Report: `out/reports/diag_contrib_ratio.md`.
- Within view_count strata the AUC is 0.514 (N = 1,834,889, 18 strata), against 0.219 pooled. Rank correlation with a distance-only proxy is 0.849.
- Unsupported Gaussians sit a median 22.3 units from their cameras, against 9.8 for supported. Feature and label are both dominated by camera distance; the laser-scan label is needed to tell which is wrong.

## 2026-11-10 · T3 initialisation confound · truck · `configs/T3_confound.yaml`
- 89.73 % of Gaussians (2,280,369 / 2,541,226) are far from init. The near-init 10.27 % are 0 % unsupported by construction, because the init cloud is the reference cloud. Report: `out/reports/T3_confound.md`.
- On far-init only, the label still separates on view_frac (AUC 0.796) and isolation (0.690); inflation is about 0.035 AUC. Opacity has almost no signal (0.522).
- **contrib_ratio runs opposite to the hypothesis (AUC 0.262).** It is flagged per §8 as contradicting the premise; not flipped and not investigated further.

## 2026-11-10 · T2 sanity checks · truck · `configs/T2_checks.yaml`
- All 5 checks plus an added 5b pass: rotations orthonormal to 1.2e-6, isotropic covariance to 1.1e-6, behind-camera view_count 0 (synthetic N = 40; no real case exists), reruns bitwise identical to T1. Report: `out/reports/T2_checks.md`.
- Frame: the p1–p99 boxes overlap (96.64 % of the reference box). The model's init cloud equals COLMAP points3D exactly (136,029 points, max distance 0).
- So the `unsupported` label is built from the exact seed cloud, and T3 must quantify that confound. The Gaussian box is about 3× the reference box, consistent with background Gaussians that the reference doesn't cover.

## 2026-11-03 · Alignment to T&T laser scan · truck · `configs/align_truck.yaml`
- Inria→scan similarity from 251 camera pairs: centre error RMS 3.69 mm (max 16.22 mm), orientation median 0.086°. Report: `out/reports/align_truck.md`.
- Independent check: sparse points inside the official crop (N = 75,481) sit a median 5.6 mm from the scan. A diagnostic ICP, not applied, shifts the transform by 10 mm and 0.06°.
- Good enough for labels at the 0.29 m scale, not for 5 mm F-scores. The scan covers only the crop (55.5 % of the sparse points), so the background has no laser label.

## 2026-10-20 · T1 feature extraction · truck · `configs/T1_truck.yaml`
- 2,541,226 Gaussians × 22 columns from 40 of 219 training views. All range checks pass (0 violations), nothing clipped. Report: `out/reports/T1_features.md`.
- `unsupported` (τ = 20 × 0.01129 = 0.226 units) flags 1,078,846 / 2,541,226 = 42.45 %. That is too high for a high-precision label, probably because the sparse reference barely covers the background.
- Config changes before any metric: full resolution and the 3DGS eval holdout (from `cfg_args`). pycolmap was replaced by a numpy COLMAP reader because there is no wheel for Python 3.15.
