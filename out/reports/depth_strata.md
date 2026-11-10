# Depth-stratified AUC — truck
Run: 2026-11-10 · config: `configs/depth_strata.yaml` (features from `configs/T1_truck.yaml`, 40 views) · commit: 21d2640 (code that produced these numbers)

**In one sentence:** the `unsupported` label is strongly driven by distance from the cameras (0.13 % in the nearest tenth of Gaussians, 93.9 % in the farthest). With depth held roughly fixed, `view_frac` (0.690) and `isolation` (0.620) still separate in every stratum but lose 0.10–0.14 AUC. `contrib_ratio` stays inverted (0.397, below 0.5 in 7 of 9 strata), and `opacity` has no signal (0.518).

## What I did
For every Gaussian seen by at least one of the 40 views, I took its depth to be the mean camera-space depth over the views that see it. The views and projection are the same as T1, and the code asserts the per-view pass reproduces T1's `view_count` exactly. I split the Gaussians into 10 equal-count strata of that depth and computed the tie-aware rank AUC of the four T3 features within each stratum, with the same inherited directions. A stratum was used only if both label classes had at least 1,000 members. All of this was fixed in the config before running.

## Numbers

N = 2,541,226. Seen by at least one view: 2,530,829. Excluded for having no depth: 10,397. Strata used: 9 of 10, covering 2,277,746 Gaussians.

| Stratum | Depth (units) | N | Unsupported | contrib_ratio | view_frac | isolation | opacity |
|---|---|---|---|---|---|---|---|
| 1 | 3.05 – 3.81 | 253,083 | 0.13 % (333) | — | — | — | — |
| 2 | 3.81 – 4.38 | 253,083 | 0.56 % (1,410) | 0.276 | 0.811 | 0.809 | 0.655 |
| 3 | 4.38 – 9.49 | 253,083 | 18.11 % | 0.215 | 0.842 | 0.602 | 0.580 |
| 4 | 9.49 – 11.43 | 253,083 | 33.91 % | 0.246 | 0.825 | 0.523 | 0.505 |
| 5 | 11.43 – 13.19 | 253,082 | 51.50 % | 0.432 | 0.698 | 0.532 | 0.511 |
| 6 | 13.19 – 17.71 | 253,083 | 46.27 % | 0.408 | 0.691 | 0.605 | 0.483 |
| 7 | 17.71 – 20.95 | 253,083 | 40.98 % | 0.476 | 0.651 | 0.650 | 0.474 |
| 8 | 20.95 – 24.50 | 253,083 | 58.90 % | 0.522 | 0.557 | 0.610 | 0.485 |
| 9 | 24.50 – 33.19 | 253,083 | 77.91 % | 0.544 | 0.540 | 0.628 | 0.482 |
| 10 | 33.19 – 89.60 | 253,083 | 93.90 % | 0.456 | 0.594 | 0.623 | 0.486 |

Stratum 1 was skipped because it has 333 positives, below the 1,000 minimum.

| Feature | Artefact if | AUC pooled* | AUC within depth (N-weighted) | Δ | Strata < 0.5 | Range |
|---|---|---|---|---|---|---|
| contrib_ratio | high | 0.2215 | 0.3970 | +0.176 | 7 of 9 | 0.215 – 0.544 |
| view_frac | low | 0.8294 | 0.6900 | −0.140 | 0 of 9 | 0.540 – 0.842 |
| isolation | high | 0.7265 | 0.6203 | −0.106 | 0 of 9 | 0.523 – 0.809 |
| opacity | low | 0.5314 | 0.5178 | −0.014 | 5 of 9 | 0.474 – 0.655 |

\* The pooled AUCs here exclude the 10,397 unseen Gaussians, so they differ slightly from T3 (for example `contrib_ratio` 0.2194 there).

## What this does and does not show
- **The label is largely a depth detector in truck.** The `unsupported` rate rises from 0.13 % to 93.9 % across depth deciles. This matches the expected SfM mechanism: points far away relative to the camera baseline are triangulated less often and less accurately. That mechanism was not measured directly here.
- **Distance explains part, not all, of `view_frac` and `isolation`.** Both drop by 0.10–0.14 AUC within strata but stay above 0.5 in every stratum. Some of their T3 signal was distance; the rest is not explained by depth.
- **`contrib_ratio` stays inverted within depth.** It is strongest in the near strata (0.215–0.276), where the `view_count` cap from the diagnostic still applies. It never exceeds 0.544 in any stratum. Holding depth fixed does not rescue it.
- **The label barely fires near the cameras.** Only 0.13–0.56 % of the nearest 20 % of Gaussians are labelled unsupported. Classic floaters often sit close to cameras, so this label cannot measure them where they are most likely to be. It is a failure mode of the label, not evidence that the near field is clean.
- **This does not separate "real artefact" from "label error".** Within a stratum, the label is still distance to the seed cloud. The strata are also wide at the extremes: stratum 3 spans 4.4–9.5 units and stratum 10 spans 33–90.

## What broke
Nothing errored. For this task I moved the per-view pass out of `src/diagnose_contrib_ratio.py` into a shared `per_view_geometry()`. Rerunning the diagnostic gave byte-identical output (`diff` empty).
