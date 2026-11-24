# Human inspection: overhead layer from T4 — truck
Run: 2026-11-24 · config: `configs/inspect_layer.yaml` · commit: 677b576 (code that produced these numbers)

## What I did
I projected the T4 overhead layer into the training images so a human can judge what it is. The layer is defined as L2-positive Gaussians that are seen and have scan z > −6.0 m; this cut was chosen **post hoc**, from the T4 height histogram, to select views for inspection only. No metric is computed from it, and nothing is classified (AGENTS.md §2).

The six training views with the most layer Gaussians in frame were rendered as overlays: full image, unmarked zoom, and marked zoom. There is no occlusion test. The images are in `out/inspection/overhead_layer/`, which is gitignored because they are derived from dataset images.

## Numbers

| Quantity | Value |
|---|---|
| Layer Gaussians | 3,941 |
| Training views with ≥ 1 layer Gaussian in frame | 132 of 219 |
| Views rendered (most in frame) | 000111 (3,259), 000110 (3,126), 000112 (2,844), 000119 (2,836), 000118 (2,767), 000116 (2,693) |
| COLMAP camera model / published image size | 1957 × 1091 / 979 × 546 px (published images are downsampled by about 2; pixel coordinates scaled accordingly) |

## What this does and does not show
- **The projection is geometrically consistent.** Across separate views, the line-shaped part of the layer lands on the same continuous image structure in every view. That checks the alignment and projection, not the meaning of the structure.
- **The human judgement is pending:**
  - What is the image structure under the line-shaped marks?
  - What is under the scattered marks near the top of the frame?
  - Are these real scene content or artefacts?

  Record the answer here, with who made it and the date. It decides whether stratum 5 of T4 measures label failure (real structure the scanner missed) or real floaters.

## Human judgement (recorded 2026-11-24)
Made by the project researcher (the user), from the six rendered views, **at region level, not per Gaussian**:

| Part of the layer | Judgement |
|---|---|
| Line-shaped part | **A real electric wire.** The laser scan does not contain it, so these L2 positives are **label failures**: a real thin structure, the §2 wire/needle ambiguity in practice. |
| Scattered points over the tree close to the truck | On the tree near the truck; read as real foliage. |
| Remaining scattered points | **Floaters.** The background behind them changes clearly between views: mostly white sky and green trees in views 000110–000112, mostly a white building and trees in views 000116–000119. |

**Update (same day):** the cluster-level review with wide-angle views (`out/reports/cluster_review.md`) overturned the "real foliage" reading. Every near-tree cluster that could be re-checked from views 34–65° apart was judged a floater.

Not yet done at that point: assigning individual Gaussians to these parts. That needs a rule fixed before it is applied (`configs/layer_split.yaml`). The professor has not reviewed this judgement yet.

## What broke
- The first run failed with an index error: the nullable `Int8` label column converted to an object array. Fixed with an explicit `dtype=bool`. The same pattern in `src/floaters_t4.py` was only used inside a sum, so its result (139) is unaffected.
- Surprise: the published Inria images (979 × 546) are half the resolution of the COLMAP cameras (1957 × 1091). The model was trained at 1957 px according to `cameras.json` (author's local images), so T1 features are unaffected. Only these overlays needed rescaling.
