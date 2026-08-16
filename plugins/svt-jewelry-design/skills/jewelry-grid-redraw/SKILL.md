---
name: jewelry-grid-redraw
description: Use to redraw one jewelry grid cell or storyboard slice into a higher-quality single image while preserving the product or accepted design.
---

# Jewelry Grid Redraw

## Purpose

Repair or improve one weak grid cell without changing the jewelry identity established by the source image, reference sheet, or accepted design.

Also handle explicit split-and-redraw requests after a grid exists, such as "拆成九张图", "拆单图", "分别高清重绘", or "放大每张". In that case, the source grid provides each cell's model pose and scene, while the original product image or accepted render provides jewelry structure and identity.

## Trigger Scenarios

- One cell in a contact sheet has distorted stones, poor lighting, bad crop, wrong product, or unclear composition.
- A user wants a single grid cell upgraded into a standalone image.
- A user wants a finished nine-grid split into nine standalone images and each image redrawn or upscaled.
- A catalog or poster workflow needs one replacement image.

## Steps

Before any Apps UI call or fallback in this Skill, read and follow `$jewelry-studio`'s
`references/conversation-ui-contract.md`, especially Apps UI capability resolution.

1. Use the bundled plugin Image-2 route for still-image redraw work. External still-image plugins and
   generic MCP image tools are preview-only and out of scope unless the user makes an explicit
   provider request.
2. Identify the target cell and its role.
3. List product facts that must remain locked.
4. List the defects to fix and the allowed improvements.
5. Write a focused `$imagegen` / `gpt-image-2` revision prompt, then render when requested.
6. For split-and-redraw requests, first identify the latest accepted grid, extract the named cells in reading order, and treat each extracted cell as a scene reference only.
7. For every redrawn cell, combine two references in the prompt: the cell's model pose, wardrobe, crop, and background from the grid; and the jewelry silhouette, material, stone placement, setting, chain, and charm details from the original product or accepted render.
8. Preserve each source cell's aspect ratio for split-and-redraw unless the user requests a new crop.
   If the user asks for a fresh standalone product redesign rather than preserving a cell scene,
   ordinary design defaults apply and the output can be square `1:1`.
9. For batch split-and-redraw production, create one runner job per cell and use the runner
   selection defined by `$jewelry-studio` for `add-jobs` followed by `generate`, so each cell has
   explicit prompt, references, output path, logs, and recovery evidence.
10. After the real standalone outputs exist, call `show_jewelry_creation_gallery` with
    `workflow: grid_redraw`, stable `REDRAW-*` ids in reading order, and every completed file. A
    successful Gallery replaces duplicate inline presentation; on tool error or missing output,
    show every real successful redraw inline and state the gap.

## Input Constraints

- Require the original product/design reference and the weak cell description or image.
- Do not rebuild the entire grid.
- Do not change stone count, product type, metal color, or silhouette unless requested.
- Do not treat a split cell as sufficient product truth when an original product image or accepted render exists; use the original product reference to correct jewelry structure.
- Do not use external still-image plugins or generic MCP image tools for ordinary redraw routing
  without an explicit provider request in the current user message.

## Output Requirements

- Redraw brief with `Target Cell`, `Original Role`, `Defects`, `Locked Product Facts`, `Allowed Changes`, `Aspect Ratio`, and `Image-2 Revision Prompt Notes`.
- For split-and-redraw work, output or save each standalone image in stable reading order and name or describe cells consistently, such as `cell_01` through `cell_09`.

## Verification

- Check the replacement still matches the source product.
- Check only the named cell is being changed.
- Check the revision prompt is narrow and testable.
- For split-and-redraw work, check every output preserves both the cell scene and the original jewelry identity.
- Confirm the Gallery preserves stable reading order and receives every completed redraw.
