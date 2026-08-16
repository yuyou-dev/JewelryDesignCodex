---
name: jewelry-reference-sheet
description: Use to plan a 2x2 white-background jewelry reference sheet for consistent structure, proportions, stone placement, and viewing angles in Codex CLI image-2 workflows.
---

# Jewelry Reference Sheet

## Purpose

Create a multi-view reference plan that helps later renders preserve jewelry identity across catalog, poster, grid, redraw, or revision work.

## Trigger Scenarios

- A single source image is not enough to preserve product structure.
- A new design needs front, side, top, and macro views before downstream renders.
- A later image-2 prompt should attach or describe a consistency sheet.

## Steps

Before any Apps UI call or fallback in this Skill, read and follow `$jewelry-studio`'s
`references/conversation-ui-contract.md`, especially Apps UI capability resolution.

1. Use the bundled plugin Image-2 route for still-image reference sheets. External still-image
   plugins and generic MCP image tools are preview-only and out of scope unless the user makes an
   explicit provider request.
2. Identify the jewelry identity to preserve: silhouette, stones, settings, metal, motifs, proportions.
3. Choose four views: hero front, side/profile, top/flat, and macro detail.
4. Define white-background lighting and consistent scale. A standard 2x2 reference sheet defaults
   to square `1:1`; use another ratio only when the user or downstream preset specifies it.
5. Build a complete `$imagegen` / `gpt-image-2` sheet prompt using `$jewelry-studio` image-2 prompt guidance, then render when requested.
6. After one or more real reference-sheet outputs exist, call `show_jewelry_creation_gallery` with
   `workflow: reference_sheet`, stable `SHEET-*` ids, and every completed file. A successful
   Gallery is the final visual presentation; on tool error or missing output, show every real
   successful sheet inline and state the gap.

## Input Constraints

- Use source images or design brief as factual reference.
- Do not redesign the jewelry while creating the reference sheet unless asked.
- Do not add unseen logos, certificates, hands, faces, or props.
- Do not use external still-image plugins or generic MCP image tools for ordinary reference-sheet
  routing without an explicit provider request in the current user message.

## Output Requirements

- 2x2 sheet brief with `View 1`, `View 2`, `View 3`, `View 4`, `Preserve`, `Lighting`, `Background`, `Aspect Ratio`, and `Image-2 Notes`.

## Verification

- Confirm all four views serve a downstream consistency purpose.
- Confirm preservation targets are explicit.
- Confirm the prompt notes can become a `$imagegen` request.
- Confirm the Gallery contains every completed sheet and is not followed by duplicate inline images.
