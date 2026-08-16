---
name: jewelry-retouch
description: Use to plan jewelry photo cleanup into clean product references while preserving exact design, silhouette, stone placement, metal structure, and identity.
---

# Jewelry Retouch

## Purpose

Improve source jewelry imagery for downstream design, catalog, grid, poster, or review work without changing the product.

## Trigger Scenarios

- The user has a rough product photo needing white background, cleaner reflections, or luxury e-commerce polish.
- A source image should become a stronger factual reference for Image-2 prompts.
- A generated image has lighting or background issues but the jewelry design should remain locked.

## Steps

Before any Apps UI call or fallback in this Skill, read and follow `$jewelry-studio`'s
`references/conversation-ui-contract.md`, especially Apps UI capability resolution.

1. State the product features that must be preserved.
2. Define allowed cleanup: background, dust, lighting, reflection control, crop, contrast, and shadow.
3. Define forbidden changes: stone count, shape, setting, metal color, silhouette, logo, scale, or motif changes.
4. Build a complete Image-2 retouch prompt with preservation rules repeated, then render if an image is requested.
5. For multiple independent retouch outputs, prepare one full-preservation prompt per source/output and add all jobs first through one jobs file. Use that file as `--job-manifest` for validation and one concurrent `generate --only pending,failed` command so continued tasks cannot select older jobs. Check objective file and identity-preservation facts; do not start aesthetic review unless the user requests it.
6. After one or more real source/output pairs exist, call `show_jewelry_retouch_comparison` when
   available as the final visual presentation. Pass multiple pairs together with stable sequential
   ids `RETOUCH-A` through `RETOUCH-H`; the App uses a vertical pair rail and one active draggable
   comparison. If the tool returns a non-error result, do not repeat the source and retouched images
   inline afterward. If the tool is unavailable or returns an error, show every real pair inline as
   the fallback. Its continue action records the selected post-retouch image as neutral asset
   context for the next user-authored instruction. The comparison is presentation only: it does
   not approve the retouch, add a deliverable, or trigger aesthetic review.

## Input Constraints

- Source image or prior render is required for product-preserving retouch.
- Do not turn retouching into redesign.
- Do not remove intentional engravings, hallmarks, or design details unless the user asks.

## Output Requirements

- Retouch brief with `Preserve Exactly`, `Allowed Cleanup`, `Forbidden Changes`, `Background`, `Lighting`, `Crop`, and `Image-2 Notes`.
- For completed visual retouch work, use one presentation path: the successful draggable comparison, or both actual images inline when the comparison tool is unavailable or fails.

## Verification

- Check every design-preservation rule is explicit.
- Check the output asks for product cleanup, not a new concept.
- Check `$jewelry-image-review` was used only if the user explicitly requested critique or revision.
- Check multi-image retouch work was queued before generation and each output was checked for
  objective product-identity preservation.
- Check each comparison receives one or more existing local source/output pairs from the same retouch
  task; never use mock previews or claim the comparison itself is user approval.
- Check a successful comparison tool call is not followed by duplicate inline before/after images.
