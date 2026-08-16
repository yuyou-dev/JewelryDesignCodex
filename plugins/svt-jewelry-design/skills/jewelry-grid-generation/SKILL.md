---
name: jewelry-grid-generation
description: Use to plan jewelry 3x3 contact sheets or 2x2 artistic sets for e-commerce, model showcase, editorial, macro, and campaign gpt-image-2 outputs.
---

# Jewelry Grid Generation

## Purpose

Plan repeatable multi-image jewelry sets that show product identity, scale, material details, and campaign mood.

In designer-facing Chinese, "九图", "模特九图", and "九宫格" normally mean one finished 3x3 grid image. Do not reinterpret those requests as nine separate generations unless the user explicitly asks to split, extract, or redraw individual cells.

## Trigger Scenarios

- The user asks for a nine-grid, four-grid, contact sheet, listing set, or social image set.
- The user asks in Chinese for "九图", "模特九图", "九宫格", "九宫格图", or a "3:4" model grid.
- A product needs main image, angle images, macro, model scale, packaging, and lifestyle shots.
- A generated grid cell needs later redraw or review.

## Steps

Before any Apps UI call or fallback in this Skill, read and follow `$jewelry-studio`'s
`references/conversation-ui-contract.md`, especially Apps UI capability resolution.

1. Use the bundled plugin Image-2 route for still-image grids. External still-image plugins and
   generic MCP image tools are preview-only and out of scope unless the user makes an explicit
   provider request.
2. Choose preset: e-commerce nine-grid, model showcase nine-grid, editorial photo nine-grid, or artistic four-grid.
3. Define the output as one complete grid image, such as one vertical 3:4 3x3 model nine-grid, unless the user explicitly requested separate files.
4. For model nine-grids, read `references/model-nine-grid-contract.md` and follow its output-shape, cell-plan, anti-repetition, and failure-recovery rules.
5. Define each cell's role, view angle, background, scale cue, and locked product facts.
6. Add anti-repetition constraints for model grids: cells must differ clearly in at least three of wardrobe, background, pose, camera distance, lighting, and interaction while preserving the same jewelry identity.
7. Keep factual product references separate from style references.
8. Generate a complete prompt pack using `$jewelry-studio` image-2 prompt guidance; for controlled
   or reference-dependent production, use the runner selection defined by `$jewelry-studio`
   rather than the current session's direct image tool.
   For explicit split/redraw requests, catalog sets, or other separate-file grids, add all independent jobs before generation. Use the same jobs file as `--job-manifest` for validation and one concurrent `generate --only pending,failed` command so continued tasks cannot select older jobs. Keep ordinary "九图/九宫格" as one complete grid image unless the user asked for separate files.
9. Use `$jewelry-grid-redraw` for weak cells or for later split-and-redraw requests.
11. After one or more real grid outputs exist, call `show_jewelry_creation_gallery` with
    `workflow: grid`, stable `GRID-*` ids, and every completed file. A successful Gallery is the
    final visual presentation; do not repeat the same images inline. If the tool is unavailable,
    returns an error, or lacks an output, show every real successful grid inline and state the gap.

## Input Constraints

- A source product, design brief, or accepted render is required.
- Do not change the jewelry identity across cells.
- Do not split a grid request into nine separate images unless the user explicitly says to split, extract, redraw, upscale, or generate separate cells.
- Avoid fake certificates, fake brand marks, or unsupported model claims.
- Do not use external still-image plugins or generic MCP image tools for ordinary grid routing
  without an explicit provider request in the current user message.

## Output Requirements

- Grid plan with `Preset`, `Cell List`, `Shared Product Facts`, `Style Rules`, `Forbidden Changes`, and `Image-2 Prompt Notes`.
- For nine-grid requests, the prompt notes must state "one complete 3x3 grid image" or an equivalent phrase.
- For model nine-grids, the prompt notes must include anti-repetition rules for wardrobe, background, pose, camera distance, lighting, and interaction.

## Verification

- Confirm every cell has a distinct purpose.
- Confirm the output shape matches the user request: one grid image for "九图/九宫格", separate files only for explicit split/redraw requests.
- Confirm product consistency rules apply to all cells.
- Confirm the plan supports review and targeted redraw.
- Confirm any later video workflow uses the generated grid as a reference image, not as a text-only prompt substitute.
- Confirm a successful grid Gallery contains every real completed output and is not followed by duplicate inline images.
- If a user says the grid looks like the same image repeated, evaluate visually and redo the grid with stronger cell differences; do not argue from filenames, hashes, or dimensions.
