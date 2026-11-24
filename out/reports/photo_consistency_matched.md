# Matched photo-consistency — truck
Run: 2026-11-24 · config: `configs/photo_consistency_matched.yaml` · commit: 677b576 (code that produced these numbers)

**In one sentence:** matching the view set and keeping only camera-facing truck surface lowered the reference's colour variation from 0.196 to 0.116, but not to the pre-set 0.098. So the positive control **fails**, and by the rule fixed before running, this method is not used to judge floaters.

## What I did
The design was agreed with the researcher before running (2026-11-24). No rendering was used.
- **View window:** the 9 training views named 000110–000119. 000113 is a held-out test view and is excluded.
- **Equal view count:** every point must be in frame in all 9 views, so every point uses the same 9 views.
- **Reference:** in-scope L2-negative Gaussians (truck surface) whose normal faces every window camera within 60°. The normal is the smallest-scale axis, oriented away from the centroid of the in-crop Gaussians. 5,000 were sampled with seed 0.
- **Score:** colour std across the 9 views, nearest pixel on the published half-resolution images, RGB mean (0..1).
- **Positive control:** the matched reference median must be ≤ 0.098, half the unmatched 0.196.

## Numbers

**View window:** 000110, 000111, 000112, 000114, 000115, 000116, 000117, 000118, 000119.

**Reference eligibility:** 511,506 in-scope L2− candidates; 33,109 are in frame and facing in all 9 views; 5,000 sampled.

| Group | N | N in frame in all 9 views | p25 | Median | p75 |
|---|---|---|---|---|---|
| Wire | 2,103 | 1,858 | 0.022 | 0.117 | 0.191 |
| Layer rest (tree + floaters) | 1,838 | 306 | 0.019 | 0.093 | 0.212 |
| Truck surface (matched reference) | 5,000 | 5,000 | 0.054 | **0.116** | 0.174 |

- **Positive control:** reference median 0.1156 against the threshold of 0.098 → **FAIL**.
- P(std of the wire part > reference) = 0.473. P(std of the layer rest > reference) = 0.475. Both are no difference, but they are not interpretable, because the control failed.

## What this does and does not show
- **Matching helped, but not enough.** The reference's median variation fell by about 41 % (0.196 → 0.116), so the mismatched view sets were a real part of the problem, as the researcher suspected. But real, camera-facing truck surface is still not colour-consistent at the single-pixel level across 9 neighbouring views.
- **Per the pre-set rule, this result is not used to judge floaters, and the threshold is not adjusted after the fact (§1.2).**
- **Possible reasons, none tested:**
  - nearest-pixel sampling on half-resolution images of a textured surface (rust, wood planks), where a sub-pixel error changes the colour;
  - occlusion by other objects such as poles, which the back-face test cannot detect;
  - specular paint and exposure changes between frames;
  - centre-only sampling of Gaussians that cover several pixels.
- **Only 306 of the 1,838 layer-rest Gaussians are in frame in all 9 views,** so even a passing control would have covered a small subset.
- **A standard multi-view-stereo version** compares small patches with normalised cross-correlation rather than single pixels, and would address the first and third reasons. It would be a new, pre-registered attempt. The risk is retrying variants until one "works" (§1.8), so it should only be run if agreed in advance as the one further attempt.

## What broke
Nothing errored. The control failed and is reported as found.
