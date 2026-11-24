# RESULTS

Running log, newest first. Each entry: three lines. Every number from a committed script + config.

## 2026-11-24 · Cluster review, two rounds · truck · `configs/cluster_review*.yaml`
- 12 largest non-wire layer clusters (1,495 Gaussians), judged by the researcher: floater 1,247 (383 on wide views, 864 on narrow views only), second wire segment 185 (C2), object 63 (C9, narrow only). Report: `out/reports/cluster_review.md`.
- All 4 clusters called "object" on adjacent frames that could be re-shown from views 34–65° apart flipped to floater. Human review needs wide-baseline views, a lesson for the agent's human-in-the-loop step.
- The earlier "near-tree = real foliage" reading is overturned. Inside the layer, L2 is right about the reviewed non-wire positives (floaters) and wrong about the two wire segments.

## 2026-11-24 · T4 wire-excluded + cluster review set-up · truck · `configs/T4_floaters_wire_excluded.yaml`, `configs/cluster_review.yaml`
- Excluding the 2,103 human-confirmed wire Gaussians leaves N = 514,388 with 2,882 L2+. Pooled / within-depth AUC: isolation 0.778/0.835 (0 of 5 strata below 0.5), view_frac 0.760/0.705, opacity 0.641/0.618, contrib_ratio 0.221/0.295. Report: `out/reports/T4_floaters_wire_excluded.md`.
- The wire had inflated view_frac (stratum 5: 0.989 → 0.963) and deflated isolation (stratum 5: 0.440 → 0.711). Both uncorrected and corrected results are kept.
- The non-wire layer (1,838) splits into 160 components at 0.10 m. The 12 largest (1,495 Gaussians, 81.3 %) are rendered for human tree/floater judgement; the sheet is `out/reports/cluster_judgements.csv`.

## 2026-11-24 · Matched photo-consistency · truck · `configs/photo_consistency_matched.yaml`
- Same 9 views (000110–000119, test view 000113 excluded) for every group; reference = 5,000 truck-surface Gaussians facing all window cameras within 60°. Report: `out/reports/photo_consistency_matched.md`.
- Reference median colour std fell from 0.196 (unmatched) to 0.116, but the pre-set positive control needed ≤ 0.098: **FAIL**.
- By the rule fixed before running, single-pixel photo-consistency is not used to judge floaters. A patch-based (NCC) version would be one pre-registered further attempt, if agreed.

## 2026-11-24 · Overhead layer: human inspection + split · truck · `configs/layer_split.yaml`
- Researcher's judgement (6 views, region level): the line is a real electric wire; scattered points over the near tree are real foliage; the rest are floaters (background changes between views). Reports: `out/reports/inspect_layer.md`, `out/reports/layer_split.md`.
- A fixed RANSAC rule puts 2,103 of 3,941 layer Gaussians on one 2.82 m horizontal line, so 42 % of the 4,985 in-scope L2 positives are a wire the scanner missed (label failure).
- Photo-consistency without occlusion does not separate (layer rest vs truck surface P = 0.533; the reference is itself inconsistent). It needs a z-buffer, which waits on the professor's "is it rendering" decision.

## 2026-11-24 · T4 floaters (L2) · truck · `configs/T4_floaters.yaml`
- Scope N = 516,491 (in crop, seen; 139 unseen excluded, all L2+), 4,985 L2 positives. AUC vs L2 pooled / within depth: view_frac 0.861/0.710, isolation 0.572/0.780, opacity 0.652/0.615, contrib_ratio 0.142/0.291. Report: `out/reports/T4_floaters.md`.
- contrib_ratio is inverted against the independent laser label as well, so the problem is the feature definition, not the COLMAP label.
- Most L2 positives form one thin layer about 1.5 m above the truck (z ≈ −5.29), including a straight line about 2.8 m long the scanner missed: either a real thin structure (§2 ambiguity) or floaters. A human must inspect it before the AUCs mean "floater detection".

## 2026-11-10 · L2 laser-scan label · truck · `configs/L2_scan_label.yaml`
- Approved by the professor (reported by the user). τ = 0.289 m (the L1 τ converted to metres). Inside the official crop, 5,124 of 516,630 Gaussians (0.99 %) are unsupported_scan; the 2,024,596 outside the crop have no label. Report: `out/reports/L2_scan_label.md`.
- Against L2 inside the crop, L1 has recall 35.23 % and precision 97.57 % (1,805 overlap). The label file is reproducible (identical SHA-256 over two runs).
- All 139 in-crop Gaussians seen by no view are L2 positives, so T4 must fix their handling (exclude or not) in its config before running.

## 2026-11-10 · Near-field checks · truck · `configs/nearfield_checks.yaml`
- The official scan crop covers only the truck: 0 of 219 cameras, 20.33 % of Gaussians (516,630), depth deciles 1–2 almost fully, decile 3 at 17.6 %, deciles 4–10 not at all. Report: `out/reports/nearfield_checks.md`.
- Inside the crop, 75–79 % of Gaussians are within 2 cm of the scan and 0.97 % (4,985) are more than 0.289 m away. L1 agrees with "far from scan" at precision 97.37 % and recall 33.42 %.
- Mean-depth deciles do not isolate near-camera floaters, and the camera ring lies outside the crop. That needs nearest-camera depth or a free-space test (L4), neither run yet.

## 2026-11-10 · Literature review: is the distance confound known? · `out/reports/literature_review.md`
- The mechanism is textbook (triangulation error ∝ depth²). Floaters cluster near cameras (Floaters No More, EGSR 2023). SfM pseudo-GT can invert benchmark rankings (Brachmann et al., ICCV 2021, the closest precedent).
- No paper found uses distance to SfM points as a per-Gaussian artefact label and measures its depth dependence, or evaluates per-Gaussian features within depth strata. The search was not systematic, so any claim must read "to our knowledge".
- ArtifactWorld's taxonomy confirmed: Floaters, Dilation and Needles are in its Geometric Structure domain. Its labels are image-space, not per Gaussian.

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
