# T8 — Cross-scene, protocol v1 — truck, bicycle, garden, room, playroom
Run: 2026-11-24 · config: `configs/protocol_v1.yaml` (+ generated `configs/T1_<scene>.yaml`) · commit: 52cab86

## What I did
Ran one frozen pipeline (`src/run_scene.sh`: T1 features → pre-registered extra signals → T3/T4 evaluation → T6/T7) unchanged on five scenes, and scored 8 signals against the COLMAP label L1 (`unsupported` = distance to nearest sparse point > 20 × median sparse spacing). The protocol was signed off by the researcher before any new scene was downloaded. AUC is the tie-aware Mann–Whitney statistic over Gaussians seen by ≥ 1 of 40 sampled training views, pooled and as an N-weighted mean within 10 equal-count strata of mean camera depth (a stratum counts only with ≥ 1,000 per class). The cross-scene verdict uses the pre-registered rule: a feature is *stable* only if its within-depth AUC is on the same side of 0.5 on all five scenes. T5 (needles) uses option B, chosen by the researcher before it ran: near ≤ 1 × median COLMAP spacing, far > 20 × (= L1 τ), ambiguous in between.

## Numbers

### Scope and label per scene
| scene | dataset | Gaussians N | unseen (excluded) | seen N | L1+ (seen) | L1+ % | strata used |
|---|---|---|---|---|---|---|---|
| truck | T&T | 2,541,226 | 10,397 | 2,530,829 | 1,068,450 | 42.22 | 9 / 10 |
| bicycle | Mip-NeRF 360 | 6,131,954 | 60,391 | 6,071,563 | 1,962,278 | 32.32 | 8 / 10 |
| garden | Mip-NeRF 360 | 5,834,784 | 132,875 | 5,701,909 | 529,539 | 9.29 | 8 / 10 |
| room | Mip-NeRF 360 | 1,593,376 | 221,676 | 1,371,700 | 119,026 | 8.68 | 8 / 10 |
| playroom | Deep Blending | 2,546,116 | 820 | 2,545,296 | 187,112 | 7.35 | 10 / 10 |

Training views: truck 219, bicycle 169, garden 161, room 272, playroom 196 (every 8th held out, cfg_args eval=True); 40 sampled per scene. Training resolution from the images the model was trained on (`configs/train_image_sizes.yaml`). L1 τ (scene units): truck 0.226, bicycle 0.675, garden 0.425, room 0.285, playroom 0.500.

### Within-depth AUC against L1 (the primary number)
| scene | contrib_ratio | view_frac | isolation | opacity | max_parallax | sh_rest_ratio | contrib_F1 | contrib_F2 |
|---|---|---|---|---|---|---|---|---|
| truck | 0.397 | 0.690 | 0.620 | 0.518 | 0.704 | 0.474 | 0.698 | 0.381 |
| bicycle | 0.395 | 0.703 | 0.587 | 0.489 | 0.640 | 0.456 | 0.705 | 0.355 |
| garden | 0.271 | 0.845 | 0.639 | 0.505 | 0.815 | 0.437 | 0.845 | 0.248 |
| room | 0.328 | 0.835 | 0.715 | 0.602 | 0.774 | 0.557 | 0.836 | 0.321 |
| playroom | 0.437 | 0.703 | 0.659 | 0.498 | 0.491 | 0.484 | 0.709 | 0.428 |

Pooled AUCs and the far-from-init (T3) AUCs are in `out/reports/protocol_v1/T8_tables.md`; per-stratum AUCs in `out/reports/protocol_v1/<scene>_strata.csv`.

### Stability verdict (pre-registered rule)
| feature | direction = artefact | within-depth range | scenes > 0.5 | verdict |
|---|---|---|---|---|
| view_frac | low | 0.690 – 0.845 | 5/5 | stable |
| contrib_F1 | high | 0.698 – 0.845 | 5/5 | stable, but **a re-expression of view_count** (ρ −0.69 to −0.98, below) |
| isolation | high | 0.587 – 0.715 | 5/5 | stable |
| max_parallax_deg | low | 0.491 – 0.815 | 4/5 | **not stable** (playroom 0.491) |
| opacity | low | 0.489 – 0.602 | 3/5 | **not stable** |
| sh_rest_ratio | high | 0.437 – 0.557 | 1/5 | **not stable** |
| contrib_ratio | high | 0.271 – 0.437 | 0/5 | stable, **inverted** on every scene |
| contrib_F2 | high | 0.248 – 0.428 | 0/5 | stable, **inverted** on every scene |

### Redundancy (Spearman ρ with view_count, seen Gaussians, random 500,000 per scene, seed 0; `src/redundancy.py`)
| signal | truck | bicycle | garden | room | playroom |
|---|---|---|---|---|---|
| contrib_F1 | −0.797 | −0.979 | −0.964 | −0.808 | −0.687 |
| max_parallax_deg | +0.873 | +0.822 | +0.977 | +0.616 | +0.642 |
| contrib_ratio | +0.794 | +0.737 | +0.732 | +0.525 | +0.563 |
| contrib_F2 | +0.777 | +0.790 | +0.850 | +0.510 | +0.439 |
| isolation | −0.328 | −0.413 | −0.310 | −0.093 | −0.017 |

### T3 per scene (near-init = within 1 × median init spacing of an `input.ply` point)
| scene | far-init share | L1+ near-init | view_frac AUC far-init | isolation AUC far-init |
|---|---|---|---|---|
| truck | 89.73 % | 0 | 0.794 | 0.691 |
| bicycle | 83.12 % | 0 | 0.760 | 0.637 |
| garden | 82.46 % | 0 | 0.897 | 0.740 |
| room | 85.49 % | 0 | 0.871 | 0.661 |
| playroom | 83.50 % | 0 | 0.677 | 0.618 |

Init cloud vs reference: max |d_init − d_ref| = 0 on four scenes, 3.95e−6 on bicycle (float32 rounding). On every scene the label still separates when restricted to far-from-init Gaussians (all stable features keep AUC > 0.6 there).

### T5 needles: top 2 % by anisotropy (all Gaussians), split by distance to the nearest COLMAP point
| scene | subset n | anisotropy threshold | near (≤ 1 × spacing) | **ambiguous** | far (> 20 × spacing = L1+) |
|---|---|---|---|---|---|
| truck | 50,825 | 4.77e4 | 312 (0.61 %) | **18,470 (36.34 %)** | 32,043 (63.05 %) |
| bicycle | 122,640 | 3,643 | 37,523 (30.60 %) | **69,497 (56.67 %)** | 15,620 (12.74 %) |
| garden | 116,696 | 9,089 | 21,311 (18.26 %) | **86,204 (73.87 %)** | 9,181 (7.87 %) |
| room | 31,868 | 1,761 | 5,069 (15.91 %) | **25,105 (78.78 %)** | 1,694 (5.32 %) |
| playroom | 50,923 | 2,347 | 3,289 (6.46 %) | **33,958 (66.68 %)** | 13,676 (26.86 %) |

Median opacity in the subset is 0.02–0.14 on every scene and group (`<scene>_T5_stdout.txt`). 20 ambiguous Gaussians per scene (seed 0), raw attributes, **not classified**: `out/reports/protocol_v1/<scene>_T5_sample.csv`. Figures: `out/figures/protocol_v1/<scene>_2_needle_split.png`.

### T6 dilation: median shift, L1+ minus L1− (seen; decades of log10; planarity raw; 95 % bootstrap CI, 1,000 resamples, seed 0)
| scene | volume | scale_max | anisotropy | planarity |
|---|---|---|---|---|
| truck | +0.728 [+0.721, +0.734] | +0.209 [+0.208, +0.210] | −0.010 [−0.014, −0.007] | −0.033 [−0.033, −0.032] |
| bicycle | +1.280 [+1.276, +1.283] | +0.223 [+0.223, +0.224] | −0.368 [−0.370, −0.366] | +0.089 [+0.089, +0.090] |
| garden | +1.774 [+1.769, +1.780] | +0.314 [+0.313, +0.316] | −0.564 [−0.567, −0.560] | +0.041 [+0.040, +0.042] |
| room | +1.170 [+1.161, +1.179] | +0.220 [+0.218, +0.222] | −0.207 [−0.212, −0.203] | +0.108 [+0.105, +0.110] |
| playroom | +0.413 [+0.404, +0.422] | +0.259 [+0.258, +0.261] | +0.289 [+0.283, +0.294] | −0.062 [−0.063, −0.062] |

N per group: the L1+/L1− seen counts in the scope table.

### T7 coverage (all Gaussians; 40 sampled views)
| scene | N | seen by < 3 views | median angular spread | max parallax p10 / p50 (deg, seen by ≥ 2) | ≥ 10 views but parallax < 5° |
|---|---|---|---|---|---|
| truck | 2,541,226 | 7.77 % | 0.005 | 5.7 / 19.8 | 1,642 of 1,317,986 |
| bicycle | 6,131,954 | 15.95 % | 0.005 | 5.4 / 16.9 | 0 of 1,850,721 |
| garden | 5,834,784 | 19.96 % | 0.016 | 12.0 / 32.8 | 0 of 3,136,227 |
| room | 1,593,376 | 23.19 % | 0.101 | 14.2 / 102.8 | 0 of 761,201 |
| playroom | 2,546,116 | 10.98 % | 0.085 | 34.4 / 59.7 | 0 of 11,632 |

Figures: `out/figures/protocol_v1/<scene>_3_dilation.png`, `<scene>_4_coverage.png` (7.4 × 4.3 in, 200 dpi).

## What this does and does not show
- **The label is weak supervision, not ground truth.** L1 is high-precision / low-recall (on truck, against the laser scan: precision 97.6 %, recall 35.2 %), and it tracks camera distance and camera coverage. Every AUC above measures agreement with "no COLMAP point nearby". Measured here: the L1+ rate rises with depth on truck (0.1 % → 93.9 % across strata) and garden (0.0 % → 57.0 %; the deepest stratum holds 61.4 % of garden's L1+), is flat at 33–59 % from stratum 4 outwards on bicycle, and stays low with no clear depth trend on room (0.6–22.8 %) and playroom (2.1–16.0 %) (`T8_tables.md`). In garden, L1+ also marks regions outside the camera ring seen by one or two cameras (below). Not measured, but a known failure mode that plausibly applies to room and playroom: textureless walls, ceilings and floors get no COLMAP points, so real surface there is labelled unsupported. Nothing here checks how much of L1+ is real geometry on any scene other than truck.
- **Garden's AUC > 0.98 flag is a shared cause, not a shared column.** In garden depth stratum 3 (depth 6.19–7.74, 1,409 L1+), view_frac 0.993, max_parallax 0.995 and F1 0.996. 1,408 of the 1,409 positives lie outside the camera ring (median 1.22 × ring radius) and 1,359 are seen by ≤ 2 sampled views (`out/reports/protocol_v1/garden_suspicious_stratum3.txt`). Few cameras see that region, so COLMAP has no points there *and* view-based features are low: label and features are both read off camera coverage. The stratum is reported, not removed; garden's within-depth averages include it.
- **Only two features survive as independent, stable evidence: view_frac and isolation.** F1 is stable but is view_count re-expressed (ρ down to −0.98). max_parallax is mostly view_count too (ρ up to +0.98) and fails on playroom (0.491). isolation is the one stable signal nearly uncorrelated with view_count (|ρ| ≤ 0.41), so it carries something view coverage does not; it is also the weakest of the stable ones (0.587–0.715).
- **contrib_ratio is inverted on all five scenes**, and the distance-corrected variant F2 is inverted too. The truck explanation (opacity cancels; the ratio is capped by view_count and grows with view count) carries over: contrib_ratio and F2 correlate *positively* with view_count on every scene. The per-view-peak hypothesis is not supported anywhere, under either label.
- **The pre-registered SH signal does not separate** (0.437–0.557, 1/5 above 0.5). View-dependent colour energy does not mark L1-unsupported Gaussians.
- **T5: distance to verified geometry cannot place most needle-like Gaussians.** 36–79 % of the top-2 % most anisotropic Gaussians sit between 1 and 20 median spacings from a COLMAP point: neither on verified geometry nor L1-unsupported. That is the empirical size of the set geometry-by-distance does not resolve, on these five scenes. Two caveats on what it measures. (1) The number depends on the band width, which the protocol fixed at 1×–20× spacing; a different (also valid) band gives a different fraction. (2) The top 2 % by anisotropy are extreme ratios (thresholds 1.8e3–4.8e4) with median opacity 0.02–0.14: mostly near-transparent, degenerate Gaussians, not necessarily the visible spikes AGENTS.md calls needles. Real thin structures (wires, branches, bicycle spokes) and needle artefacts are both in this set; nothing here separates them, and per AGENTS.md §2 no attempt is made.
- **T6 is correlational.** L1+ Gaussians are larger on every scene (volume +0.41 to +1.77 decades, scale_max +0.21 to +0.31), but anisotropy also moves on four of five scenes (−0.21 to −0.56 decades on bicycle, garden, room; +0.29 on playroom), and only on truck is it near zero. By the T6 rule, that means floaters or background are leaking into the comparison; a likely contributor is that the L1+ group is weighted towards far background, where Gaussians are larger; this report does not test that explanation. The causal version needs a pose-perturbation retrain, out of scope.
- **T7:** the case raw view count misses — many views, nearly parallel rays — is rare under 40 sampled views (0 on four scenes at the pre-set 10-view / 5° threshold). Under-coverage is the common failure instead: 8–23 % of Gaussians are seen by fewer than 3 of 40 views.
- Remaining confounds: no transmittance (occluded Gaussians count as seen); 40 of 161–272 views sampled; L1 uses the same COLMAP cloud the model was initialised from (T3: no L1+ within one spacing of an init point on any scene, by construction).

## What broke
- **Protocol change before running (logged in `configs/protocol_v1.yaml` `changes`):** the training resolution rule "from cameras.json" was wrong for Mip-NeRF 360 (cameras.json holds the COLMAP size, 4946 px for bicycle; the model trained on images_4, 1237 px). Replaced by the measured image size, found while generating configs, before any feature of a new scene was computed.
- **T5 band redefined before running (logged in protocol `changes`).** The original band (35th–65th percentile of distance *within the top-2 % subset*) fixes the ambiguous fraction at ≈ 30 % by construction. The researcher chose option B (spacing multiples already in the protocol) before T5 ran on any scene.
- Room: 13.9 % of Gaussians (221,676) are seen by none of the 40 sampled views (truck 0.4 %); 150,907 of them are L1+. They are excluded from every AUC, as the protocol says, which removes a large share of room's L1+ before scoring.
- The download tool was rewritten mid-run (single streamed range request, size + CRC verified) because the first version issued one HTTP request per 1 MB read; no data effect.
- `src/t6_t7_scene.py` crashed once on a plotting typo (`r.shift` is a pandas method); fixed and re-run, numbers unchanged.
- angular_spread has a minimum of −1.3e−7 on truck (float rounding of 1 − |mean|); not clipped.
