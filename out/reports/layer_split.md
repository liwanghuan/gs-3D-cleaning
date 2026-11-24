# Overhead layer split and photo-consistency — truck
Run: 2026-11-24 · config: `configs/layer_split.yaml` (layer from `configs/inspect_layer.yaml`) · commit: uncommitted

**In one sentence:** a fixed RANSAC line rule puts 2,103 of the 3,941 layer Gaussians (53.4 %) on one nearly horizontal line 2.82 m long, which is the part the researcher judged to be a real electric wire. Photo-consistency without an occlusion test does **not** separate anything: the truck-surface reference is itself colour-inconsistent across views.

## What I did
- **Wire split:** the 3D line with the most layer Gaussians within 0.05 m, by RANSAC (2,000 iterations, seed 0) on scan-frame centres. The rule was fixed before running.
- **Photo-consistency:** for each Gaussian in the wire part, the rest of the layer, and a random reference of 5,000 in-scope L2-negative Gaussians (truck surface, seed 0), I took the nearest pixel colour in every training view that has the centre in frame. The score is the per-channel standard deviation across those views, averaged over RGB (0..1), using only Gaussians with at least 3 such views.
- **No class threshold was set.**

## Numbers

**Split** (layer N = 3,941)

| Part | N | Share |
|---|---|---|
| Wire (RANSAC line inliers, 0.05 m) | 2,103 | 53.4 % |
| Rest (tree near the truck + floaters, per the human judgement) | 1,838 | 46.6 % |

Line extent: 2.82 m. Direction in the scan frame: (−0.927, −0.374, 0.020), so nearly horizontal.

**Photo-consistency** (colour std across views in frame, no occlusion test)

| Group | N | N used (≥ 3 views) | Median views in frame | p25 | Median | p75 |
|---|---|---|---|---|---|---|
| Wire | 2,103 | 2,103 | 30 | 0.070 | 0.142 | 0.229 |
| Layer rest | 1,838 | 1,066 | 18 | 0.093 | 0.215 | 0.284 |
| Truck surface (L2−, reference) | 5,000 | 5,000 | 190 | 0.172 | 0.196 | 0.228 |

- P(std of the wire part > reference) = 0.318.
- P(std of the layer rest > reference) = 0.533. That is no difference.

## What this does and does not show
- **The geometric rule matches the human judgement on the line.** Half the layer lies on one straight, nearly horizontal 2.8 m line, consistent with the wire the researcher identified. Together with the 4,985 in-scope L2 positives from T4:
  - **2,103 (42 %) of all L2 positives are a real wire the scanner missed.** That is label failure, not floaters.
- **Photo-consistency is inconclusive here and should not be used as evidence.**
  - The reference group, real truck surface, is about as colour-inconsistent as the layer rest (median 0.196 against 0.215). Without an occlusion test, a surface point projects onto whatever occludes it in many of its 190 in-frame views.
  - The wire's lower variation (0.142) most likely reflects the sky behind a 1–2 px wire at half resolution, not the wire itself.
  - So this test measures occlusion and background, not whether a Gaussian is real. A meaningful version needs an occlusion test (a CPU z-buffer), which is the same open "is this rendering?" question for the professor.
- **The tree-versus-floater split of the remaining 1,838 is still only at region level** (human judgement). No rule assigns individual Gaussians. 772 of them are in frame in fewer than 3 views, consistent with poorly constrained Gaussians, but that is not proof.
- **1,044 L2 positives outside the layer** (4,985 − 3,941) have not been inspected.

## What broke
Nothing errored. The photo-consistency test ran as specified, and its negative result is reported as found.
