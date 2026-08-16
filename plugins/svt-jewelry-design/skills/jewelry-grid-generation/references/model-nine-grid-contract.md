# Model Nine-Grid Contract

Use this reference when a designer asks for "九图", "模特九图", "九宫格", "九宫格图", "3x3", or a model contact sheet.

## Output Shape

- Default output is one complete 3x3 grid image.
- For model showcase grids, default to a vertical 3:4 composition when the user asks for 3:4 or when the intended use is social/catalog review.
- Do not split the grid into nine separate files unless the user explicitly asks to split, extract, redraw, upscale, or output each cell separately.
- Do not describe the work as "nine separate generations" to a non-technical designer unless they asked for separate images.

## Designer-Language Routing

- "用这款做模特九图，3:4" means generate one 3:4 model nine-grid image.
- "做九宫格图" means generate one complete 3x3 grid image.
- "拆成九张图" means extract the cells from the existing grid into nine standalone images.
- "分别高清重绘" means route each extracted cell through `jewelry-grid-redraw`, using the cell as scene reference and the original product as jewelry identity reference.

## Required Prompt Structure

For one generated nine-grid, include these sections in the image prompt:

- `LOCKED PRODUCT FACTS`: product type, metal, gemstone layout, silhouette, setting, chain or closure, dangling parts, and forbidden material changes.
- `OUTPUT SHAPE`: one complete 3x3 grid image, aspect ratio, clean gutters, no text or labels.
- `CELL PLAN`: nine numbered cells with distinct role, model pose, crop, wardrobe, background, scale cue, and lighting.
- `ANTI-REPETITION RULES`: cells must differ in at least three of wardrobe, background, pose, camera distance, lighting, and interaction.
- `FORBIDDEN CHANGES`: no extra competing jewelry, no hidden product, no cropped-off product, no brand marks, no unsupported certificates, no material swaps, no redesign.

## Model Showcase Cell Pattern

Use this as a compact starting point, then customize to the product:

1. Bright studio front wearing shot, product centered.
2. Three-quarter or side editorial pose, diagonal chain drape.
3. Product over contrasting fabric, close neckline crop.
4. Outdoor or lifestyle daylight wearing shot.
5. Macro worn detail, product fills most of the cell.
6. Evening or darker styling, product brightly lit.
7. Profile or hair-up neck shot, chain visible along the neck.
8. Hand interaction with chain only, product unobstructed.
9. Clean e-commerce hero wearing shot, centered and highly legible.

## Failure Recovery

If the user says the result is "同一张图", "重复", "没变化", or similar:

- Judge the grid visually, not by file hash, filename, dimensions, or generation timestamp.
- Acknowledge the visual repetition plainly.
- Regenerate one complete grid image with stronger differences in wardrobe, background, pose, camera distance, lighting, and interaction.
- Preserve the same locked product facts unless the user asks for a design change.
