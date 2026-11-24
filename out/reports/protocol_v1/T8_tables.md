## Scope and label per scene

| scene | N_seen | n_pos | L1_pos_pct | strata_used |
|---|---|---|---|---|
| truck | 2,530,829 | 1,068,450 | 42.22 | 9 |
| bicycle | 6,071,563 | 1,962,278 | 32.32 | 8 |
| garden | 5,701,909 | 529,539 | 9.29 | 8 |
| room | 1,371,700 | 119,026 | 8.68 | 8 |
| playroom | 2,545,296 | 187,112 | 7.35 | 10 |

## L1+ rate per depth stratum (% of stratum, seen Gaussians; stratum 1 = nearest)

| scene | s1 | s2 | s3 | s4 | s5 | s6 | s7 | s8 | s9 | s10 | deepest_share_of_L1+ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| truck | 0.1 | 0.6 | 18.1 | 33.9 | 51.5 | 46.3 | 41.0 | 58.9 | 77.9 | 93.9 | 22.2 |
| bicycle | 0.0 | 0.0 | 8.4 | 44.5 | 44.2 | 44.3 | 45.1 | 32.6 | 44.9 | 59.1 | 18.3 |
| garden | 0.0 | 0.0 | 0.2 | 2.2 | 2.5 | 5.2 | 6.4 | 9.1 | 10.2 | 57.0 | 61.4 |
| room | 1.9 | 0.8 | 0.6 | 0.6 | 1.4 | 3.5 | 15.7 | 22.5 | 22.8 | 16.9 | 19.5 |
| playroom | 2.1 | 4.0 | 8.2 | 16.0 | 10.4 | 4.7 | 5.8 | 5.5 | 6.2 | 10.5 | 14.3 |

## Within-depth AUC (N-weighted mean over used strata)

| scene | contrib_ratio | view_frac | isolation | opacity | max_parallax_deg | sh_rest_ratio | contrib_F1 | contrib_F2 |
|---|---|---|---|---|---|---|---|---|
| truck | 0.397 | 0.690 | 0.620 | 0.518 | 0.704 | 0.474 | 0.698 | 0.381 |
| bicycle | 0.395 | 0.703 | 0.587 | 0.489 | 0.640 | 0.456 | 0.705 | 0.355 |
| garden | 0.271 | 0.845 | 0.639 | 0.505 | 0.815 | 0.437 | 0.845 | 0.248 |
| room | 0.328 | 0.835 | 0.715 | 0.602 | 0.774 | 0.557 | 0.836 | 0.321 |
| playroom | 0.437 | 0.703 | 0.659 | 0.498 | 0.491 | 0.484 | 0.709 | 0.428 |

## Pooled AUC (seen Gaussians)

| scene | contrib_ratio | view_frac | isolation | opacity | max_parallax_deg | sh_rest_ratio | contrib_F1 | contrib_F2 |
|---|---|---|---|---|---|---|---|---|
| truck | 0.222 | 0.829 | 0.726 | 0.531 | 0.860 | 0.423 | 0.739 | 0.206 |
| bicycle | 0.263 | 0.818 | 0.699 | 0.477 | 0.800 | 0.408 | 0.814 | 0.212 |
| garden | 0.147 | 0.915 | 0.765 | 0.486 | 0.914 | 0.338 | 0.913 | 0.113 |
| room | 0.179 | 0.883 | 0.685 | 0.655 | 0.884 | 0.540 | 0.839 | 0.166 |
| playroom | 0.454 | 0.680 | 0.647 | 0.500 | 0.506 | 0.481 | 0.691 | 0.438 |

## Pooled AUC on far-from-init Gaussians (T3)

| scene | contrib_ratio | view_frac | isolation | opacity | max_parallax_deg | sh_rest_ratio | contrib_F1 | contrib_F2 |
|---|---|---|---|---|---|---|---|---|
| truck | 0.264 | 0.794 | 0.691 | 0.522 | 0.830 | 0.444 | 0.717 | 0.246 |
| bicycle | 0.313 | 0.760 | 0.637 | 0.475 | 0.738 | 0.442 | 0.756 | 0.268 |
| garden | 0.165 | 0.897 | 0.740 | 0.482 | 0.896 | 0.347 | 0.895 | 0.133 |
| room | 0.187 | 0.871 | 0.661 | 0.644 | 0.869 | 0.560 | 0.823 | 0.179 |
| playroom | 0.446 | 0.677 | 0.618 | 0.504 | 0.499 | 0.489 | 0.681 | 0.446 |

## Stability verdict (pre-registered rule: within-depth AUC on the same side of 0.5 on all scenes)

| feature | min | max | scenes_above_0_5 | rank_per_scene | verdict |
|---|---|---|---|---|---|
| contrib_ratio | 0.271 | 0.437 | 0/5 | 7 7 7 7 7 | stable, INVERTED (runs opposite to hypothesis) |
| view_frac | 0.690 | 0.845 | 5/5 | 3 2 2 2 2 | stable, separates as hypothesised |
| isolation | 0.587 | 0.715 | 5/5 | 4 4 4 4 3 | stable, separates as hypothesised |
| opacity | 0.489 | 0.602 | 3/5 | 5 5 5 5 4 | NOT stable |
| max_parallax_deg | 0.491 | 0.815 | 4/5 | 1 3 3 3 5 | NOT stable |
| sh_rest_ratio | 0.437 | 0.557 | 1/5 | 6 6 6 6 6 | NOT stable |
| contrib_F1 | 0.698 | 0.845 | 5/5 | 2 1 1 1 1 | stable, separates as hypothesised |
| contrib_F2 | 0.248 | 0.428 | 0/5 | 8 8 8 8 8 | stable, INVERTED (runs opposite to hypothesis) |

rank_per_scene order: truck, bicycle, garden, room, playroom

AUC > 0.98 flags (pooled or any stratum): garden/view_frac, garden/max_parallax_deg, garden/contrib_F1

## T6 median shift, unsupported minus supported (decades; planarity raw), 95% bootstrap CI

| scene | volume | scale_max | anisotropy | planarity |
|---|---|---|---|---|
| truck | +0.728 [+0.721, +0.734] | +0.209 [+0.208, +0.210] | -0.010 [-0.014, -0.007] | -0.033 [-0.033, -0.032] |
| bicycle | +1.280 [+1.276, +1.283] | +0.223 [+0.223, +0.224] | -0.368 [-0.370, -0.366] | +0.089 [+0.089, +0.090] |
| garden | +1.774 [+1.769, +1.780] | +0.314 [+0.313, +0.316] | -0.564 [-0.567, -0.560] | +0.041 [+0.040, +0.042] |
| room | +1.170 [+1.161, +1.179] | +0.220 [+0.218, +0.222] | -0.207 [-0.212, -0.203] | +0.108 [+0.105, +0.110] |
| playroom | +0.413 [+0.404, +0.422] | +0.259 [+0.258, +0.261] | +0.289 [+0.283, +0.294] | -0.062 [-0.063, -0.062] |

## T5 needles (option B: near <= 1 x spacing, far > 20 x spacing)

| scene | N | n_subset | anisotropy_thr | n_near | pct_near | n_amb | pct_amb | n_far | pct_far | n_unseen |
|---|---|---|---|---|---|---|---|---|---|---|
| truck | 2,541,226 | 50,825 | 4.769e+04 | 312 | 0.6139 | 18,470 | 36.34 | 32,043 | 63.05 | 0 |
| bicycle | 6,131,954 | 122,640 | 3643 | 37,523 | 30.6 | 69,497 | 56.67 | 15,620 | 12.74 | 3 |
| garden | 5,834,784 | 116,696 | 9089 | 21,311 | 18.26 | 86,204 | 73.87 | 9,181 | 7.867 | 12 |
| room | 1,593,376 | 31,868 | 1761 | 5,069 | 15.91 | 25,105 | 78.78 | 1,694 | 5.316 | 465 |
| playroom | 2,546,116 | 50,923 | 2347 | 3,289 | 6.459 | 33,958 | 66.68 | 13,676 | 26.86 | 6 |

## T7 coverage

| scene | N | n_unseen | n_few | pct_few | spread_p50 | parallax_p10 | parallax_p50 | n_many | n_many_narrow |
|---|---|---|---|---|---|---|---|---|---|
| truck | 2,541,226 | 10,397 | 197,473 | 7.771 | 0.005 | 5.724 | 19.840 | 1,317,986 | 1,642 |
| bicycle | 6,131,954 | 60,391 | 977,773 | 15.946 | 0.005 | 5.431 | 16.877 | 1,850,721 | 0 |
| garden | 5,834,784 | 132,875 | 1,164,836 | 19.964 | 0.016 | 12.014 | 32.812 | 3,136,227 | 0 |
| room | 1,593,376 | 221,676 | 369,427 | 23.185 | 0.101 | 14.222 | 102.756 | 761,201 | 0 |
| playroom | 2,546,116 | 820 | 279,620 | 10.982 | 0.085 | 34.381 | 59.671 | 11,632 | 0 |
