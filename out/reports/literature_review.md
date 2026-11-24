# Literature review — is "the label is mostly a distance detector" known?
Run: 2026-11-10 · method: 17 web searches and 4 full-page reads · commit: 677b576 (code that produced these numbers)

## Question
The depth-stratified analysis (`out/reports/depth_strata.md`) found that, in truck, the `unsupported` label is driven mostly by camera distance: 0.13 % unsupported in the nearest depth decile against 93.9 % in the farthest. View-based features, `contrib_ratio` in particular, share that dependence. Does existing work report this, or something close to it?

## Short answer
- **The mechanism is textbook.** Triangulation error grows with the square of depth.
- **The pieces around it are known**, each on its own:
  - floaters cluster near the cameras;
  - SfM pseudo ground truth can bias benchmark rankings;
  - confounded labels produce shortcut correlations.
- **No paper found does what we did.** None uses distance to SfM points as a per-Gaussian artefact label and then measures how far that label is driven by camera depth. None evaluates per-Gaussian artefact features within depth strata either.
- **The closest methodological precedent** is Brachmann et al. (ICCV 2021), on SfM pseudo ground truth in camera re-localisation.

The search was not systematic (see Limitations), so any novelty claim should read "to our knowledge".

## Findings by theme

### A. The mechanism: triangulation precision falls with depth (known)
- Stereo and SfM depth error ≈ z²·ε / (b·f), where z is depth, b the baseline, f the focal length and ε the matching error. This is the standard result, stated for example in [Gallup et al., CVPR 2008](https://www.cvlibs.net/projects/autonomous_vision_survey/literature/Gallup2008CVPR.pdf), and in [recent lecture notes](https://arxiv.org/pdf/2608.03496) as "depth resolution decreases quadratically with distance".
- **What it explains here:** in a loop around an object, the baseline is fixed by the loop size. Far background therefore gets fewer and less precise sparse points, and the COLMAP-distance label fires there.
- **Not measured here:** a full SfM covariance analysis. The stereo formula is only an approximation for SfM.

### B. Floaters live near the cameras (known, and it matters for us)
- [Floaters No More (Philip & Deschaintre, EGSR 2023)](https://arxiv.org/abs/2305.02756) traces NeRF floaters to "background collapse" caused by the higher sample density near cameras, and fixes it by scaling gradients by distance.
- [Nerfbusters (Warburg et al., ICCV 2023)](https://openaccess.thecvf.com/content/ICCV2023/html/Warburg_Nerfbusters_Removing_Ghostly_Artifacts_from_Casually_Captured_NeRFs_ICCV_2023_paper.html) argues that the standard every-8th-frame evaluation misses floaters, and records a second trajectory for evaluation.
- **Why it matters:** our label is close to blind exactly where these papers say floaters form (0.13–0.56 % unsupported in the nearest 20 % of Gaussians). That is independent support for treating the near-field blindness as a failure of the label, not as evidence that the near field is clean.
- **Caveat:** both papers are about NeRF. Whether 3DGS floaters show the same near-camera concentration is plausible but not established by these sources.

### C. Pseudo ground truth from a reference algorithm biases evaluation (known, different task)
- [Brachmann, Humenberger, Rother & Sattler, ICCV 2021](https://openaccess.thecvf.com/content/ICCV2021/html/Brachmann_On_the_Limits_of_Pseudo_Ground_Truth_in_Visual_Camera_ICCV_2021_paper.html) show that re-localisation benchmarks partly measure how well a method reproduces its reference algorithm. Switching the pseudo ground truth from depth-SLAM to SfM *inverts* method rankings.
- **Closest precedent to our finding.** Our COLMAP label also rewards whatever correlates with how SfM behaves (distance, view count). Their recommendation, to account for the reference algorithm when interpreting results, carries over directly.

### D. 3DGS geometry and floater evaluation uses scanned ground truth, not SfM (practice)
- [FeatureGS](https://arxiv.org/html/2501.17655) measures floaters indirectly, as an all-points Chamfer distance against the DTU structured-light reference. It gives no formal floater definition and no camera-distance analysis.
- ["When 3DGS Recovers Real Surfaces" (2026)](https://arxiv.org/pdf/2608.30054) compares Gaussian centres to ground-truth meshes after Umeyama + ICP alignment, the same procedure as our `align_reference.py`. It truncates distances at the 99th percentile to limit floater influence.
- [A building-accuracy study of Gaussian splatting](https://www.researchgate.net/publication/408407310_A_Comprehensive_Evaluation_of_the_Spatial_Accuracy_of_Building_Gaussian_Splatting) reports threshold-based floater percentages, and reports that cleaning the COLMAP cloud reduced floaters. The full text was not accessible (HTTP 403), so its reference geometry and thresholds are **not verified**.
- [Textureless-Splatter](https://www.tandfonline.com/doi/full/10.1080/20964471.2026.2634534) and [a museum-artefact study](https://www.nature.com/articles/s40494-026-02330-z) evaluate against laser scans.
- **Reading:** the field evaluates geometry against scans when it can, which supports option L2. I found no paper that argues *against* SfM-distance labels with measurements.

### E. Per-Gaussian scores in the literature do not control for depth (gap)
- [Vis4GS (IEEE VIS 2026 short paper)](https://arxiv.org/abs/2606.26985) scores per-Gaussian View Coverage (close to our `view_frac`) and needle and blur artefacts. Its floater case study traces a floater to a peripheral, weakly covered ancestor Gaussian. The evaluation is a user study only, and its score definitions were not visible in the abstract.
- [PUP 3D-GS (CVPR 2025)](https://openaccess.thecvf.com/content/CVPR2025/papers/Hanson_PUP_3D-GS_Principled_Uncertainty_Pruning_for_3D_Gaussian_Splatting_CVPR_2025_paper.pdf) suspects that LightGaussian's visibility score is biased towards large Gaussians, citing size histograms. The authors flag this as speculation. It is the nearest published example of a per-Gaussian score carrying a geometric bias.
- Uncertainty methods ([Bayes' Rays](https://arxiv.org/pdf/2309.03185), [Stochastic GS](https://arxiv.org/html/2403.18476), [WarpRF](https://arxiv.org/pdf/2506.22433)) report calibration, but none I found stratifies by depth.
- **Gap:** no per-Gaussian artefact or uncertainty score found is evaluated with camera depth held fixed.

### F. Labelled artefact datasets are image-space (context)
- [ArtifactWorld (ACM MM 2026)](https://arxiv.org/html/2604.12251) has 4 domains and 9 types. **Geometric Structure** contains Floaters, Dilation, Needles and Cracks, which confirms that the three AGENTS.md class names come from this taxonomy. The artefacts are simulated by perturbing Gaussian parameters, but the labels and heatmaps are in image space, not per Gaussian.
- [GaussFlaw-80K](https://arxiv.org/abs/2611.02767) has 80,049 pixel-masked artefact regions with 8 flaw labels. A public release is not stated.

### G. The general pattern has names in ML and in depth estimation (framing)
- **Shortcut learning** ([Geirhos et al., 2020](https://alphaxiv.org/overview/2004.07780v5)): a model, or here an evaluation, rewards a feature that correlates with the label in this data but is not the target concept. Distance is that feature here.
- **Subpopulation and stratified evaluation** ([Yang et al., ICML 2023](https://proceedings.mlr.press/v202/yang23s/yang23s.pdf)): pooled metrics hide failures on minority groups, so report per group.
- **Depth-binned evaluation** ([Gruber et al., "Pixel-Accurate Depth Evaluation"](https://arxiv.org/pdf/1906.08953)): depth benchmarks bin errors by distance because point density and error change with range. That is the same remedy as our depth strata, in a different task.

## What looks new, scoped to this search
1. Showing, with numbers, that a distance-to-SfM per-Gaussian artefact label in an orbit capture is mostly a camera-distance label: 0.13 % → 93.9 % across depth deciles, each decile N = 253,083.
2. Showing that the per-Gaussian evidence features proposed for artefact detection share the confound. Their AUC changes substantially once depth is held fixed: `view_frac` 0.829 → 0.690, `isolation` 0.727 → 0.620. `contrib_ratio` stays inverted (0.397).
3. Showing that the label is nearly blind in the near field, where B says floaters form.

**Suggested framing:** a methodological finding plus an evaluation protocol (depth-stratified AUC, scan-based labels where available), in the spirit of Brachmann et al. Not a new detection method. One scene only, so generality waits for T8.

## Limitations of this review
- About 17 web searches and 4 full-text reads, done in one session. This is not a systematic database search (no Google Scholar or Semantic Scholar query log, no forward citation chase).
- Several items were read only at abstract or summary level: Vis4GS, the building-accuracy paper (403), arXiv 2602.06830 (a 2026 pruning paper on foreground/background Gaussians, not read) and GaussFlaw.
- The search engine is US-only and English-only. Chinese-language venues were not covered.

## Part 2 (2026-11-24): ideas for replacing `contrib_ratio`
Ten more web searches, looking for per-Gaussian signals that capture "a floater only matters in a few views". Each idea is a **hypothesis**. None has been run. Any that are adopted must be fixed in a config before running (§1.8).

| Idea | Source | What it suggests for us | Fits the rules? |
|---|---|---|---|
| Max over views of the **true** ray contribution, with transmittance | [RadSplat](https://arxiv.org/pdf/2403.13806): importance = max over all training rays of each Gaussian's exact contribution, "rather than opacity" and "max rather than mean" | Our max/mean idea is valid only with real contribution. Ours lacked transmittance, so it degraded to footprint area. | Needs occlusion ordering, close to rendering. Professor's call. |
| Rank within each ray, not across the scene | [SafeguardGS (WACV 2026)](https://arxiv.org/html/2405.17793v2): pixel-level ranking beats scene-level; best score = colour similarity × blending weight | Normalise per view or per pixel, not per scene. That removes the camera-distance effect by construction. | Same occlusion question |
| **Max parallax angle** between the rays of the views that see a point | [Lee & Civera 2020](https://arxiv.org/abs/2008.01258): triangulation uncertainty = f(number of cameras, reprojection error, max parallax angle); COLMAP filters by minimum triangulation angle; [aerial view planning](https://arxiv.org/pdf/1805.00506) uses 5–20° | A small max parallax means depth is poorly constrained, which is how a floater can exist. A principled version of T7's "angular diversity". | Yes: camera centres + Gaussian positions only |
| **Free-space violation**: a Gaussian in front of the surface a view sees | [Merrell et al., ICCV 2007](https://paulmerrell.org/wp-content/uploads/2021/06/Merrell_DepthMapFusion07.pdf) (free-space violations in depth fusion); [SparseGS](https://arxiv.org/html/2312.00206v3) prunes Gaussians in front of the per-pixel mode depth | The physical definition of a floater. Against the scan it is the L4 label. Against the model's own dominant surface it would be a feature. | Against the scan: needs scan depth maps. Against the model: needs a z-buffer. Professor's call. |
| Floaters persist because their colour **cancels background error**, so their gradients vanish | [StableGS](https://arxiv.org/html/2503.18458v3) | Floaters are colour compensators. AGENTS.md §2 also says floaters often fake specular highlights. Candidate: view-dependent colour energy (higher-order SH norm relative to DC). | Yes: read from the .ply |
| Disagreement between two independently trained models | [CoR-GS (ECCV 2024)](https://arxiv.org/pdf/2405.12110) | A Gaussian with no counterpart in a second model is suspect | No: needs training |
| Multi-view consistency + spatial isolation + learned importance | [TIDI-GS](https://arxiv.org/html/2601.09291v1) | Supports keeping `isolation` and combining it with a view-based signal | Combination only by a fixed rule; a learned score is not allowed (§0) |
| Effective rank of the covariance | [Hyung et al., NeurIPS 2024](https://arxiv.org/abs/2406.11672): needles converge to effective rank 1 | A continuous needle score for T5, more principled than max/min scale | Yes: from scales |
| Densification lineage: floaters trace to weakly covered peripheral ancestors | [Vis4GS](https://arxiv.org/abs/2606.26985) | Compare the published iteration-7000 and iteration-30000 models: Gaussians with no early counterpart in weakly covered areas | Possibly (both checkpoints are published). Speculative. |

**Most promising within the current rules:** max parallax angle, view-dependent colour energy, and effective rank (for T5). The occlusion-aware ideas (RadSplat, SafeguardGS, free-space) look strongest, but each needs the professor to rule on whether a CPU z-buffer of Gaussian centres counts as "rendering".

## Suggested next steps
1. Run a systematic search on Google Scholar / Semantic Scholar with fixed keywords, and chase forward citations of Brachmann et al. 2021, Floaters No More and Nerfbusters.
2. Read in full: Vis4GS (score definitions), the building-accuracy paper (reference and thresholds) and arXiv 2602.06830 (foreground/background pruning).
3. Ask the professor whether they know of evaluation-methodology papers in 3DGS cleaning.
