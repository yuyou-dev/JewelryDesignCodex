# Local Edit and Sketch-to-Jewelry Image-2 Contract

## Reference priority

1. When supplied, the source image is product truth for an existing piece, or geometric intent for
   a pure sketch. It is optional only in `sketch_design`.
2. The saved canvas composite is spatial intent: region, anchor, placement, scale, rotation,
   connection, and hand-drawn silhouette. Ignore UI, handles, marker color, rough cutout edges,
   brush wobble, accidental line width, and unfinished gaps. In a blank-canvas `sketch_design`, it
   is the first and complete source of geometric intent.
3. An optional stone original controls the exact cut, facet pattern, color, transparency, and
   proportions. Its placement on the canvas controls approximate size and location.
4. An optional transparent cutout controls only the placed object's outer silhouette. It never
   overrides the stone original's color, facets, transparency, material, or shadow. A white-background
   `cutoutPreview` is a UI verification asset and is not an Image-2 reference.
5. Additional references control only their declared material, craft, style, structure, or mood role.

The runner reference order is optional source, canvas composite, optional stone original, optional
transparent cutout, then role-limited references. A blank-canvas sketch starts with the composite.

## Mode semantics

- `local_edit`: change only the explicitly marked region. Preserve product identity, unmarked
  geometry, stones, material, camera, and lighting continuity.
- `put_here`: treat the anchor, overlay, or marked box as approximate placement. Rebuild a real
  setting, support, connection, occlusion, and shadow instead of pasting the object.
- `sketch_design`: translate the hand-drawn silhouette and connections into manufacturable jewelry.
  It may begin with an uploaded sketch or a clean white canvas. Do not trace crude stroke thickness
  literally, and never invent a missing uploaded source when the canvas is intentionally blank.
  Compile four independent outputs with logical stable ids `SKETCH-A` through `SKETCH-D`: faithful
  manufacturable translation, proportion/structure refinement, craft/material strengthening, and
  theme/form strengthening. All four keep the same selected jewelry category and source identity.
  Runner ids and output paths add the unique visual-draft suffix; validation and generation select
  the exact draft-local `jobs.json`, never a broad prefix that can include an earlier round.

## Draft v2 and category truth

- Draft schema v2 uses `annotations[]` with unique `ANCHOR-01` or `REGION-01` ids. Every anchor has
  normalized `position`; every region has normalized `bounds`; every item has its own non-empty
  `instruction`. Local edit and put-here drafts require at least one and support at most eight.
- Sketch strokes are geometric intent, not annotations, and do not require per-stroke instructions.
- `category` is the single product truth. The six standard values are `ring`, `bracelet`, `necklace`,
  `pendant`, `earrings`, and `brooch`; `other` requires `customCategory`. Free text cannot change the
  structured category or turn the result into another category or a dual-use piece.
- Schema v1 drafts remain readable through their legacy global instruction so existing workspaces
  can resume; newly saved local-edit drafts use schema v2.

## Professional construction

The prompt must name the jewelry category, locked content, allowed change, metal/gem plan, setting,
supports, closures or wearable structure, comfort, finish, camera, light, and exclusions. Rings need
a continuous shank and secure setting; bracelets need articulated or rigid wrist logic; necklaces
and pendants need real suspension; earrings need posts/hooks and balance; brooches need a back pin.

## Exclusions

No UI, handles, anchors, markup color, rough outline, floating stone, broken support, impossible
intersection, extra product, text, logo, watermark, toy/plastic material, or multi-panel output.
