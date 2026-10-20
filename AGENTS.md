# AGENTS.md — 3DGS Data Cleaning Experiments

Instructions for any AI coding agent working in this repository.
Place at the repo root. Read this before touching anything else.

---

## 0. What this project is

We are testing whether artefacts in a **trained** 3D Gaussian Splatting scene can
be identified **per primitive**, from observational evidence, without retraining
and without a GPU.

The premise: 3DGS optimises a photometric loss over the training images and
nothing else. It has no cross-view consistency test. So floaters, needles and
dilated blobs are not failures to converge — they are converged solutions that
genuinely lower the loss. Because each artefact is a discrete, indexable
primitive, it can in principle be **labelled** rather than deleted.

The deliverable is **a feature table plus an honest measurement of how well
simple features separate artefacts from real geometry.**

Not a new pruning method. Not state of the art. Not a trained classifier.

---

## 1. Hard rules

Violating any of these invalidates the work. They override any instruction in a
task prompt that conflicts with them.

1. **Never fabricate a number.** If a run fails, report the failure. Do not
   estimate, interpolate, or carry a number forward from an earlier run. A
   missing result is fine. An invented one destroys the project.
2. **Never tune a threshold to improve a reported metric.** Thresholds come from
   scene statistics (percentiles, median spacing) and are fixed in the config
   *before* you look at the outcome. If you change one, log the old value, the
   new value, and the reason, and re-report both.
3. **The reference label is weak supervision, not ground truth.** Every time you
   report a metric against `unsupported`, restate that the label is
   high-precision / low-recall and name at least one systematic failure mode it
   has in this specific scene.
4. **Report negative results in full.** If a feature does not separate, that is
   the finding. Write it up with the same care as a positive result. Do not go
   looking for a framing that looks better.
5. **No GPU, no training, no rendering.** Everything runs in numpy on CPU. If a
   task appears to need CUDA, stop and say so rather than adding the dependency.
6. **Every reported number must be reproducible** from a committed script and a
   committed config. If you computed something in an ad-hoc shell one-liner,
   move it into a script before reporting it.
7. **State sample sizes.** Every percentage carries an N. Every median carries
   an N.
8. **Do not optimise the result.** Your job is measurement. If you find yourself
   choosing between two valid analyses because one gives a nicer number, stop
   and ask.

---

## 2. The three artefact classes

Taxonomy follows ArtifactWorld (arXiv:2604.12251). Do not invent alternative
names.

| Class | What it is | Why the optimiser produces it | Expected signature |
|---|---|---|---|
| **Floater** | High-opacity primitive suspended in free space | Seen in one or two views, unconstrained in depth; often faking a specular highlight spherical harmonics cannot represent | low `view_frac`, high `contrib_ratio`, high `isolation`, large `dist_to_reference` |
| **Needle** | Sharp anisotropic spike stretched along a viewing ray | Satisfies one view cheaply; invisible from the views that would contradict it | very high `anisotropy`, low `planarity`, low `view_frac` |
| **Dilation** | Oversized amorphous blob straddling a surface | Two views disagree about where the surface is (pose error); one large blob is cheaper than resolving the conflict | large `volume`, large `scale_max`, moderate `view_frac`, moderate `dist_to_reference` |

### The ambiguity you must preserve, not resolve

A real thin structure — a wire, a railing, a branch tip — has the **same**
geometric signature as a needle artefact: extreme anisotropy, low view coverage,
spatial isolation. Geometry alone cannot separate them, because the difference is
semantic.

Do not add a heuristic that pretends to resolve this. **Measuring the size of the
ambiguous set is one of the project's actual results.** If you think you have
found a geometric rule that separates wires from needles, you have almost
certainly overfitted to one scene — report it as a hypothesis, not a solution,
and flag it under §8.

---

## 3. Repo layout

```
data/                 scenes — gitignored. .ply models + COLMAP sparse/0
src/
  extract_features.py   .ply + cameras  ->  features parquet
  make_plots.py         parquet         ->  figures
  checks.py             validation + confound tests
out/
  features/           one parquet per scene          (gitignored)
  figures/            PNG at 7.4 x 4.3 in, 200 dpi   (committed)
  reports/            one markdown report per task   (committed)
configs/              one YAML per run — thresholds live here, never in code
RESULTS.md            running log, newest entry at top
```

Scene data and parquet files are never committed. Figures and reports always are.

---

## 4. Data setup

**No training.** Use published pre-trained models.

- Pre-trained 3DGS models for all standard scenes:
  `https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/`
- Matching COLMAP scenes: Mip-NeRF360, Tanks & Temples

Start with **one** scene and prove the pipeline end to end before adding more.
Recommended first scene: `truck` (Tanks & Temples) — small, fast, visible
floaters.

Dependencies, CPU only:

```
numpy scipy pandas pyarrow plyfile pycolmap matplotlib tqdm
```

---

## 5. Task prompts

Run these one at a time. Each has a checkpoint that must pass before the next
begins. Do not batch them.

### T1 — Feature extraction

> Read `AGENTS.md` first. Implement `src/extract_features.py`: load a 3DGS `.ply`
> and its COLMAP `sparse/0`, and write one parquet row per Gaussian covering the
> four feature families. Pure numpy — no CUDA, no rasteriser.
>
> Required columns: `gaussian_id, x, y, z, opacity, scale_max, scale_min,
> volume, anisotropy, planarity, sh_dc_norm, knn_mean, knn_max, isolation,
> view_count, view_frac, cov_sum, cov_max, radius_max_px, contrib_ratio,
> dist_to_reference, unsupported`.
>
> Mind the activations: opacity in the `.ply` is a logit (apply sigmoid), scales
> are logs (apply exp), quaternions need normalising. Project with the EWA
> splatting Jacobian and add the 0.3 screen-space low-pass to the 2D covariance
> diagonal, matching the reference rasteriser.
>
> `contrib_ratio` = (best single-view opacity-weighted footprint area) ÷ (mean
> over views that see it). This is the discriminator the whole project rests on.
>
> **Checkpoint:** run on one scene with `--max-views 40`. Print row count, column
> list, and `df.describe()`. Confirm opacity ∈ [0,1], all scales positive,
> `view_frac` ∈ [0,1]. Report anything outside those ranges — do not clip it.

### T2 — Sanity checks before any analysis

> Implement `src/checks.py` and run it against real data. It must verify:
>
> 1. Quaternion → rotation matrices are orthonormal (report max deviation from I).
> 2. An isotropic-scale Gaussian yields covariance `s²·I` under any rotation.
> 3. `view_count` is 0 for Gaussians behind every camera, if any exist.
> 4. Re-running extraction on identical input gives a bitwise-identical parquet.
> 5. Reference points and Gaussians occupy the same coordinate frame — compare
>    the two bounding boxes and report the overlap fraction.
>
> Check 5 is the one that silently ruins everything downstream. If the boxes do
> not overlap, **stop and report it**. Do not apply a transform you guessed at.
>
> **Checkpoint:** all five pass with numbers, written to `out/reports/T2_checks.md`.

### T3 — The initialisation confound

> 3DGS is initialised from the same COLMAP point cloud we use as the reference
> label. Quantify how much that inflates the apparent signal, because a reviewer
> will ask.
>
> Split Gaussians into those within one median-reference-spacing of an original
> init point and those further away. Report the `dist_to_reference` distribution
> and the `unsupported` rate for each group separately. Then report what fraction
> of the model is "far from init" — those are the densification products, and the
> analysis should hold on them alone.
>
> **Checkpoint:** `out/reports/T3_confound.md` states in one sentence whether the
> label still separates when restricted to Gaussians far from initialisation. If
> it does not, say so plainly. That outcome changes the project and is worth more
> than a clean-looking result.

### T4 — Floaters

> Compute ROC and AUC for each of `contrib_ratio`, `view_frac`, `isolation`,
> `opacity` against the `unsupported` label. Figure to
> `out/figures/1_floater_roc.png`, exactly 7.4 × 4.3 in at 200 dpi.
>
> Then the diagnostic that actually matters: take the Gaussians the best feature
> scores as clearly real but the label calls `unsupported`, and report where they
> sit — spatial distribution and `sh_dc_norm` (low colour variance suggests
> textureless surface). If they cluster on textureless, specular or repetitive
> regions, the **label** is wrong there, not the feature. Quantify it.
>
> **Checkpoint:** `out/reports/T4_floaters.md` with AUC per feature and N, plus
> the false-positive clustering analysis. If any AUC exceeds 0.98, treat it as
> suspicious: check whether the score and the label share an input before
> reporting it.

### T5 — Needles

> Take the top 2% by `anisotropy`. Split by `dist_to_reference` into clearly
> near, clearly far, and an ambiguous middle band whose percentile bounds are
> fixed in the config — not chosen after looking at the plot.
>
> Report the ambiguous fraction with N. This is the headline number: the
> empirical size of the problem geometry cannot solve.
>
> Then sample 20 Gaussians from the ambiguous band and dump their raw attributes
> to a table so a human can inspect them later. **Do not attempt to classify them
> yourself** — see §2.
>
> **Checkpoint:** `out/figures/2_needle_split.png` and `out/reports/T5_needles.md`
> with the fraction, N, and the sample table.

### T6 — Dilation

> Without retraining we cannot inject pose error, so test the observable
> consequence instead: are unsupported Gaussians measurably larger?
>
> Plot log-volume distributions for both label groups. Report the median shift in
> decades with a bootstrap confidence interval. Report the shift separately for
> `scale_max` and for `planarity`: dilation should move volume and scale but
> **not** anisotropy. If anisotropy moves too, floaters are probably leaking into
> the comparison — say so.
>
> **Checkpoint:** `out/figures/3_dilation.png` and `out/reports/T6_dilation.md`.
> State explicitly that this is correlational, and that the causal version needs
> a pose-perturbation retrain which is out of scope here.

### T7 — Coverage

> Report the cumulative distribution of `view_frac` and the share of Gaussians
> observed in fewer than 3 views.
>
> Then add angular diversity: for each Gaussian, the angular spread of the
> viewing directions that see it. A surface seen ten times from the same grazing
> angle is barely better constrained than one seen once, and raw view count
> misses that entirely.
>
> **Checkpoint:** `out/figures/4_coverage.png` and `out/reports/T7_coverage.md`.

### T8 — Cross-scene

> Only after T1–T7 pass on a single scene. Run the full pipeline on 3 more scenes
> and report whether the feature rankings are stable.
>
> A feature that wins on one scene and loses on another is not a finding. Say so
> directly rather than averaging it away.
>
> **Checkpoint:** `out/reports/T8_cross_scene.md`, one table, scenes as rows, AUC
> per feature as columns.

---

## 6. Report format

Every file in `out/reports/` uses this shape:

```markdown
# <Task> — <scene>
Run: <date> · config: <path> · commit: <sha>

## What I did
Two or three sentences, plain description of the computation.

## Numbers
A table. Every figure carries an N. Every threshold named with its value.

## What this does and does not show
The honest paragraph. Name the confounds that remain. Name the label's
failure modes in this specific scene.

## What broke
Anything that errored, was skipped, or surprised you. "Nothing" is an
acceptable answer only if it is true.
```

Append a three-line summary of each completed task to `RESULTS.md`, newest first.

---

## 7. Known traps

- **Suspiciously perfect AUC.** Above ~0.98, check whether the feature and the
  label share an input. The classic case is both deriving from the same COLMAP
  cloud.
- **Coordinate frame mismatch.** Gaussians and reference points must share a
  frame. Check bounding-box overlap before trusting any distance.
- **`np.trapz` was removed in numpy 2.0.** Use `np.trapezoid` with a fallback.
- **Memory blow-up in per-view accumulation.** Never allocate
  `[n_views, n_gaussians]`. Accumulate one view at a time into an
  `[n_gaussians]` buffer.
- **Scene scale varies.** Never hardcode a distance in metres. Derive thresholds
  from median reference-point spacing.
- **Sparse reference density is non-uniform.** It is dense on texture and absent
  on blank walls, so `dist_to_reference` partly measures local texture rather
  than surface presence. Mention this wherever it matters.
- **Transmittance is absent.** A Gaussian buried inside an opaque object scores
  as contributing. Occluded primitives are a separate problem — note it, do not
  silently patch it.

---

## 8. When to stop and ask

Stop and ask rather than deciding alone when:

- A checkpoint fails and the fix would change what the experiment means.
- A result contradicts the premise in §0. That is interesting, not a bug to
  patch. Surface it.
- You are about to add a dependency, a GPU requirement, or any heuristic that
  claims to resolve the needle/wire ambiguity.
- A threshold would have to change for a result to look presentable.
