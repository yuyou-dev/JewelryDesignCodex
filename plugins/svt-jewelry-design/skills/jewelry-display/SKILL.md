---
name: jewelry-display
description: Use to create product-focused high-jewelry display images with image-2, including white gallery product shots, editorial still life, hand-wearing product macros, craft closeups, and ecommerce display scenes, while staying distinct from campaign poster work.
---

# Jewelry Display

## Purpose

Create high-end product display imagery for jewelry. This skill is for showing the jewelry clearly,
truthfully, and luxuriously: product gallery images, ecommerce display scenes, editorial still life,
hand-wearing product macros, craft details, botanical negative-space scenes, and asymmetric product
compositions. It is distinct from `$jewelry-poster`: use this skill when the main job is product
display, not campaign layout, advertising typography, or poster systems.

The system prompt source of truth is `references/product-display-image2-system-prompt.md`. Detailed
display grammar lives in `references/display-grammar.md`, and the mode library lives in
`references/display-modes.json`. `references/review-rubric.md` is optional and is read only when the
user explicitly asks for critique or revision. Do not copy these into other skills or scripts.

## Trigger Scenarios

- The user asks for jewelry display images, product display, ecommerce product visuals, PDP product
  scenes, gallery images, SKU display, clean luxury product shots, still-life product images, or
  hand-wearing product closeups.
- A finished jewelry design needs multiple product-facing scene variants rather than a campaign
  poster.
- A designer asks for "高级展示图", "产品展示图", "电商展示", "白底主图", "场景展示", or "佩戴展示"
  and does not ask for a poster, magazine layout, ad campaign, or typography-led board.
- A future knowledge base should strengthen product display judgment without changing runner logic.

## Steps

Before any Apps UI call or fallback in this Skill, read and follow `$jewelry-studio`'s
`references/conversation-ui-contract.md`, especially Apps UI capability resolution.

1. Keep the output product-focused. If the user asks for a poster, campaign, cover, magazine page,
   typography system, product card layout, or ecommerce homepage, route to `$jewelry-poster`
   instead. If the user asks for a SKU catalog set, coordinate with `$jewelry-catalog`.
2. Resolve `<plugin-root>` as the installed `svt-jewelry-design` directory, two levels above this
   `SKILL.md`, then use `node "<plugin-root>/scripts/jdc.mjs" image2 ...`, `$imagegen`, and
   `gpt-image-2`. Do not use external still-image
   plugins or generic MCP image tools unless the user makes an explicit provider request in the
   current message; record that exception in `progress.md`.
3. Read `references/product-display-image2-system-prompt.md`, then load the relevant V2 references:
   `references/display-grammar.md` and `references/display-modes.json`.
4. Classify exactly one display mode:
   - `white_gallery_product`: clean white or pale gray gallery product image.
   - `botanical_negative_space`: one flower, petal, branch, leaf, or stem creates generous quiet
     space while the jewelry remains the sharp product signal.
   - `botanical_support_still_life`: one flower, petal, branch, shell, or vase acts as a cradle,
     rail, hook, or frame.
   - `asymmetric_suspended_display`: chain, bracelet, ring, or earring is draped, hung, threaded, or
     lightly supported by a flower, vase, branch, silk ribbon, or sculptural prop.
   - `silk_suspension_display`: translucent silk, organza, or ribbon provides motion and support
     without covering the jewelry.
   - `editorial_still_life`: stone, glass, paper, shell, wood, or textile prop scene.
   - `hand_wearing_product_macro`: elegant hand model or wearing detail where the jewelry stays the
     focal product.
   - `craft_macro`: close crop showing setting, metal, stone surface, prongs, carving, or enamel.
5. Define product truth before styling: category, silhouette, ring closure or wearable structure,
   metal, gem material, stone count, stone hierarchy, setting, support/gallery, proportions, and
   locked references.
6. Generate a task-local shot plan before the final image prompt. Save one complete prompt per shot
   under the active media workspace and register each as an independent Image-2 job.
7. The shot plan must name product truth, display mode, composition blueprint, support physics,
   lighting/camera, negative-space/background plan, and forbidden elements. Do not skip directly
   from a product brief to a decorative scene prompt.
8. Build one complete image-2 prompt per independent output from the shot plan. Repeat the product
   truth lock, display mode, aspect ratio, camera, lighting, background, prop hierarchy, material
   facts, support contact point, occlusion limits, and negative constraints inside every prompt.
9. Keep typography out by default. Do not ask image-2 to generate readable brand names, prices,
   labels, QR codes, watermarks, social handles, certificates, or random logos unless exact text is
   supplied and necessary.
10. For counted product-display requests, create one independent Image-2 job or generation attempt
   per requested display image. Do not count a contact sheet, collage, or poster board as multiple
   product-display images unless the user explicitly asked for a combined sheet.
11. Check only objective delivery facts needed to present the work: requested count, readable image
   files, task-local paths, and a clear mapping from each requested display to its output. Missing,
   empty, corrupt, or provider-rejected files are execution failures and may be retried locally.
12. Do not start aesthetic scoring, ranking, selection, or regeneration after generation. Read
   `references/review-rubric.md` and route to `$jewelry-image-review` only when the user explicitly
   asks for critique or revision; keep that feedback in the existing four task documents.
13. When display mode, aspect ratio, scene intensity, or background remains workflow-defining, call
    `ask_jewelry_creation_brief` with workflow `display`; skip it when the brief already resolves
    those choices. After real display files exist, call `show_jewelry_creation_gallery`. A successful
    Gallery is the final media presentation; on error, fall back to every real display image and
    report any missing output.

## Input Constraints

- Require either a clear jewelry brief, an accepted render, or product/reference images.
- Do not redesign the jewelry unless the user asks for design changes.
- Do not invent brand, price, certification, origin, grade, stock, URL, or social claims.
- Props must not hide key stones, prongs, ring shank, chain structure, clasp, bail, or wearing logic.
- In botanical or suspended displays, petals, silk, stems, branches, and vases may touch or sit behind
  jewelry, but they must not cover the main stone, setting, clasp, ring shank, or earring attachment.
- Hand-wearing images must keep natural hand anatomy, clean nails, realistic scale, and the jewelry
  as the focal point.
- Avoid poster-led composition: large typography, campaign copy, price blocks, magazine panels, and
  heavy collage layout belong to `$jewelry-poster`.
- Preserve the project-local image-2 route; external still-image plugins and generic MCP image tools
  require an explicit provider request.

## Output Requirements

- State the chosen display mode and aspect ratio when useful.
- Provide or save the shot plan: product truth, display mode, composition blueprint, support
  physics, camera/lighting, background, prop hierarchy, occlusion limits, and forbidden elements.
- For renderable work, produce or save a complete `$imagegen` / `gpt-image-2` prompt built from
  `references/product-display-image2-system-prompt.md` and the V2 mode/grammar references.
- For runner-based generation, save prompts under the active task media workspace and use
  `node "<plugin-root>/scripts/jdc.mjs" image2 ...` with one job per independent product-display image.
- Generated files must be runner-recovered `$imagegen` / `gpt-image-2` PNG outputs when the runner
  is used, and designer-facing responses should display the images inline when available.
- Put delivery links and any missing output in `result.md`; do not add task documents.
- If this role's system prompt changes, update only `references/product-display-image2-system-prompt.md`
  first; scripts and future plugin glue should consume that file instead of maintaining copies.

## Verification

- Confirm the output is product display rather than a poster, campaign, or typography-led layout.
- Confirm the jewelry remains the first visual signal and is not hidden by props, hands, text, or
  background.
- Confirm negative space is intentional: quiet areas are clean and breathable, asymmetry feels
  balanced, and the jewelry is not reduced to a tiny decorative accent.
- Confirm metal, gemstones, jade, enamel, pearls, or other materials are visually plausible and not
  plastic, melted, or over-saturated.
- Confirm wearable structure is plausible: ring shanks close, prongs/bezels support stones, links
  connect, earrings have backs/hooks when visible, and bracelet/necklace geometry is continuous.
- Confirm every independent requested display image has a separate prompt/job or recorded attempt.
- Confirm every runner prompt starts with `$imagegen` and includes the instruction to only return the
  generated image without writing files, creating jobs, updating task state, assembling reports,
  or performing post-processing.
- Confirm no automatic aesthetic review or subjective regeneration ran without an explicit request.
- Confirm the project-local image-2 route was used unless an explicit provider exception was recorded.
- Confirm `node "<plugin-root>/scripts/jdc.mjs" --help` and the Image-2 validation path pass after changing display
  grammar, modes, rubric, or examples.
- Confirm any future knowledge-base additions strengthen the single reference source instead of
  creating a second system prompt.
