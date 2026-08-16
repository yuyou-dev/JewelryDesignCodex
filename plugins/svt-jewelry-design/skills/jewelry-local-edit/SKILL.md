---
name: jewelry-local-edit
description: Use for visual jewelry local redraw, “put it here” placement, annotated corrections, freehand sketch-to-jewelry, or a gemstone placed into a rough sketch before gpt-image-2 generation.
---

# Jewelry Local Edit

## Purpose

Turn an empty canvas, product image, pure freehand sketch, or gemstone-plus-sketch composite into
one controlled jewelry result. Record spatial intent in the Apps UI canvas, then compile a complete
Image-2 prompt without treating rough strokes, UI controls, or cutout edges as literal design detail.

## Trigger Scenarios

- The user asks to change only one part of an existing piece.
- The user says “放这里”, “put it here”, “围绕这颗主石画”, or marks a target position.
- The user uploads a pure line sketch and wants a manufacturable jewelry render.
- The user uploads a gemstone and wants to position it before sketching the surrounding structure.
- The user wants to open a blank canvas and draw the jewelry directly without uploading an image.

## Steps

Before any Apps UI call or fallback in this Skill, read and follow `$jewelry-studio`'s
`references/conversation-ui-contract.md`, especially Apps UI capability resolution.

1. Create/resume the active design task and copy any supplied source, gemstone, and reference images
   into `artifacts/runs/<task-id>/references/`. Keep the four design-task documents exact.
2. Read `references/local-edit-image2-contract.md`. Decide the mode from the user's request:
   `local_edit`, `put_here`, or `sketch_design`. Ask only if the jewelry category itself is unknown.
3. Call `open_jewelry_local_editor` with the exact run workspace and any task-local absolute image
   paths. Always pass an explicit mode and category; use `other` plus `customCategory` for a
   non-standard product type. For `sketch_design`, omit `sourcePath` to open a clean white canvas.
   When a gemstone is the movable design anchor, pass it as `stonePath`; reserve `sourcePath` for an
   actual uploaded sketch or background canvas and never duplicate the same gemstone into both roles.
   A gemstone-assisted sketch confirms the local cutout before drawing. Local-edit anchors and
   marked regions each require their own instruction; sketch strokes remain geometry only.
4. After the UI returns a stable visual draft id/path, resolve `<plugin-root>` as the installed
   `svt-jewelry-design` directory, two levels above this `SKILL.md`, then compile it:

   ```bash
   node "<plugin-root>/scripts/jdc.mjs" visual-workbench prepare-local-edit --workspace artifacts/runs/<task-id> --draft artifacts/runs/<task-id>/visual-workbench/<draft-id>/draft.json --job-id LOCAL-EDIT-A
   node "<plugin-root>/scripts/jdc.mjs" image2 add-jobs --workspace artifacts/runs/<task-id> --input artifacts/runs/<task-id>/visual-workbench/<draft-id>/jobs.json
   # sketch_design:
   node "<plugin-root>/scripts/jdc.mjs" image2 validate-jobs --workspace artifacts/runs/<task-id> --job-manifest visual-workbench/<draft-id>/jobs.json --requested-count 4
   node "<plugin-root>/scripts/jdc.mjs" image2 generate --workspace artifacts/runs/<task-id> --job-manifest visual-workbench/<draft-id>/jobs.json --only pending,failed --parallel 4
   # local_edit or put_here:
   node "<plugin-root>/scripts/jdc.mjs" image2 validate-jobs --workspace artifacts/runs/<task-id> --job-manifest visual-workbench/<draft-id>/jobs.json --requested-count 1
   node "<plugin-root>/scripts/jdc.mjs" image2 generate --workspace artifacts/runs/<task-id> --job-manifest visual-workbench/<draft-id>/jobs.json --only pending,failed --parallel 1
   ```

5. For `sketch_design`, verify exactly four independent logical `SKETCH-A` through `SKETCH-D`
   outputs using the current draft's exact jobs manifest. Runner IDs and output paths add the draft
   suffix so a second edit or sketch in the same workspace cannot collide with an earlier round. Use
   `--requested-count 4` and `--parallel 4`, then call `show_jewelry_design_gallery` with
   `sourceWorkflow: sketch_design`. For `local_edit` and `put_here`, verify the one output and call
   `show_jewelry_retouch_comparison`. On successful UI presentation, do not repeat the same images
   inline; otherwise show every real output inline.
6. Do not start aesthetic review or another redesign without an explicit user request.

## Input Constraints

- `local_edit` and `put_here` require one readable task-local source image.
- `sketch_design` may use a task-local sketch, a sketch containing a placed stone, or no source
  image at all. With no source, the saved canvas composite becomes the first geometry reference.
- A separate main-stone image is optional. Other references must have one limited role: material,
  craft, style, structure, or mood.
- The local cutout is preparation only. Do not promise production-quality clipping or replace the
  project's Image-2 provider with another image backend.
- Do not treat rough line width, wobble, gaps, UI controls, or cutout artifacts as literal jewelry.

## Output Requirements

- Save one stable visual draft under the active run workspace. `sketch_design` produces four full
  prompts, four runner jobs, and four independent final images; the other modes remain one job.
- Preserve task-local reference order: optional source, canvas composite, optional stone, then
  role-limited references. A blank-canvas task starts with the canvas composite.
- Keep unmarked source regions stable in local-edit mode. In sketch mode, preserve geometric intent
  while translating it into wearable construction.

## Verification

- Confirm every referenced path is readable inside the active run workspace.
- Confirm the visual draft, prompt, job, and output share stable identifiers.
- Confirm the prompt distinguishes product truth, spatial intent, gemstone truth, and optional references.
- Confirm four sketch outputs or one local-edit/put-here output exists before showing the matching UI,
  or record the real blocker.
- Confirm no automatic critique, ranking, or regeneration occurred.
