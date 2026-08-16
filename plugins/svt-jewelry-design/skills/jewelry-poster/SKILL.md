---
name: jewelry-poster
description: Use to plan white-background angle sheets, high-end jewelry campaign posters, ecommerce hero visuals, lookbook boards, magazine pages, and collage posters for Codex CLI image-2 generation.
---

# Jewelry Poster

## Purpose

Create poster-ready art direction that can become luxury campaign imagery, ecommerce homepage
visuals, PDP hero images, lookbook boards, editorial magazine pages, social covers, gallery images,
seasonal gift campaigns, or multi-angle reference sheets.

## Trigger Scenarios

- The user asks for a jewelry poster, campaign visual, hero image, ecommerce homepage visual, PDP
  header, lookbook board, angle sheet, magazine page, collage poster, or editorial product image.
- A product render should become marketing material.
- A reference sheet or catalog set needs a more emotional campaign image.
- The user provides layout references, model references, mood references, or product images and asks
  for a brand presentation board or commercial visual.

## Steps

Before any Apps UI call or fallback in this Skill, read and follow `$jewelry-studio`'s
`references/conversation-ui-contract.md`, especially Apps UI capability resolution.

1. Use the bundled Image-2 route for poster and ecommerce still-image outputs. Resolve
   `<plugin-root>` as the installed `svt-jewelry-design` directory, two levels above this `SKILL.md`,
   then use `node "<plugin-root>/scripts/jdc.mjs" image2 ...`. If it is unavailable, report a
   blocker. Do not call `svt_jewelry.run_poster`, provider
   proxy routes, external still-image plugins, or generic MCP image tools unless the user makes an
   explicit provider request in the current message.
2. Read `$jewelry-studio` `references/poster-ecommerce-image2-prompt.md` and
   `references/poster-template-knowledge-base.md` before writing final image prompts. For multi-SKU,
   ecommerce-poster, customer-review, or gallery campaigns, also read
   `references/high-jewelry-poster-campaign.md`.
3. Classify reference roles: layout reference, jewelry truth reference, natural/mood reference, and
   prior accepted render. Layout references only teach layout, negative space, hierarchy, typography,
   and display logic; jewelry truth references define the product.
4. Run template selection before prompt writing: understand request, extract constraints, choose a
   template card, use `default advanced jewelry poster` when no named card clearly matches, then
   write the full prompt. Template matching is semantic and design-led, not keyword replacement.
   Every prompt must include `Chosen poster template`, `Template reason`, `Required layout modules`,
   and `Poster differentiation`.
5. Choose one poster mode: angle sheet, editorial presentation board, luxury ecommerce homepage,
   torn-paper campaign, left-right split poster, Japanese magazine catalog page, American fashion
   collage, minimalist gallery, festive gift campaign, or default advanced jewelry poster.
6. Define product fidelity before art direction: jewelry category, outline, proportions, stone count,
   stone positions, metal color, gem color, setting, flower/leaf/chain/bail/connector counts,
   wearing structure, and locked copy.
7. Define focal composition, model crop, product cutout, product card, art scene, background,
   lighting, props, typography, CTA/labels, aspect ratio, and forbidden changes.
   Poster and ecommerce presets own their aspect ratio; do not inherit the ordinary jewelry-design
   `1:1` default unless the user explicitly asks for a square poster.
8. Keep typography controlled. If exact text is supplied, preserve it exactly. If no text is
   supplied, use minimal elegant text only; do not invent prices, URLs, QR codes, social handles,
   random brands, watermarks, or extra logos.
9. For multiple requested posters, treat each as one independent poster output or generation
   attempt: one poster equals one Image-2 job. Do not combine N posters into one N-up contact sheet
   unless the user explicitly asks for a combined sheet.
10. For broad requests such as "几张高级海报", create a complementary template set instead of
   repeated still-life variants. A four-poster set should normally include distinct cards such as
   editorial presentation board, torn-paper campaign, Japanese magazine catalog page, and American
   fashion collage, replacing model-heavy cards with default advanced jewelry poster when needed.
   For broad ecommerce campaign requests over multiple source designs, default to a three-slot set
   per source design: `PDP Hero / Luxury Ecommerce Homepage`, `Editorial Board / Lookbook
   Presentation`, and `Macro Detail / Magazine Catalog`.
11. Do not use generic mode names such as `high-jewelry still-life campaign poster` alone as the
   final template. If a still-life direction is appropriate, expand it through `default advanced
   jewelry poster` with at least two visible poster-layout modules beyond the jewelry object.
12. When a canvas selection or product reference is supplied, pass every jewelry truth reference to
   the runner with `--reference`; layout-only and mood references must be labeled as such in the
   prompt.
13. For campaign poster sets, use the existing Image-2 jobs/state mapping for every `poster_id`,
    source design, slot, prompt, and output. Do not create a second campaign manifest.
14. Build complete `$imagegen` / `gpt-image-2` prompts using the poster/ecommerce prompt contract,
   render through the Image-2 runner, and recover the PNG outputs from `$imagegen` / `gpt-image-2`.
   Route to `$jewelry-image-review` only when the user explicitly requests critique or revision.
15. When a missing template family, aspect ratio, composition, or typography policy would change the
    whole poster workflow, call `ask_jewelry_creation_brief` with workflow `poster`; skip the form
    when those choices are already explicit. After real poster files exist, call
    `show_jewelry_creation_gallery`. A successful Gallery replaces duplicate inline poster media;
    tool failure falls back to every real poster image and a clear missing-item note.

## Input Constraints

- Require a product/design reference or clear design brief.
- Do not add brand names, logos, certifications, or price claims unless supplied.
- Avoid props that obscure the jewelry.
- Product fidelity is more important than poster creativity. Do not redesign the jewelry, change the
  jewelry category, alter stone count, add/remove chains, flowers, leaves, pearls, logos, or change
  metal/gem colors.
- Every poster in a campaign must repeat the product truth lock in its own prompt: source design id,
  source image, category, silhouette, stone hierarchy, metal direction, setting logic, and allowed
  photographic/layout-only changes.
- Match wearing location to product category: necklace/pendant uses neck, collarbone, and pendant
  area; earrings use ear, side face, jawline, and neck edge; rings use hand and fingers; bracelets
  use wrist and cuff area.
- Model crops must serve the jewelry. Do not let hair, clothing, hands, props, or layout panels hide
  key product details.
- Do not use `svt_jewelry.run_poster`, provider proxy routes, external still-image plugins, or
  generic MCP image tools for ordinary poster routing without an explicit provider request in the
  current user message.
- A poster prompt must read as a designed poster layout, not a plain product still life. Do not
  collapse the composition into a centered necklace on a simple background when the user asked for
  a high-end poster.
- Do not add approval or review states unless the user explicitly requests critique, selection, or
  revision.

## Output Requirements

- Poster brief with `Mode`, `Aspect Ratio`, `Reference Roles`, `Hero Composition`,
  `Product Fidelity`, `Layout Modules`, `Lighting`, `Props`, `Typography`, `Forbidden Elements`, and
  `Image-2 Notes`.
- The runner job must include the chosen poster/ecommerce ratio, such as `3:4`, `9:16`, or another
  user-specified value; omit it only when the prompt itself already states the preset ratio.
- Each prompt must include `Chosen poster template`, `Template reason`, `Required layout modules`,
  and `Poster differentiation`.
- For ecommerce homepage or PDP-style visuals, include `Hero`, `Product Cards`, `Model Detail`,
  `Art Scene`, `Navigation/CTA`, and `Commercial Use` notes as applicable.
- For counted poster requests, include one prompt or generation status per independent poster.
- For ecommerce poster campaigns, include a three-slot plan per source design unless the user
  requests a different slot count: `PDP Hero`, `Editorial Board`, and `Macro Detail / Catalog`.
- Generated poster files must come from runner-recovered `$imagegen` / `gpt-image-2` PNG outputs and
  be displayed inline in the response.

## Verification

- Check the jewelry remains the first visual signal.
- Check poster mood does not contradict product facts.
- Check any text is exact and short enough for image rendering.
- Check product fidelity against the jewelry truth reference: category, outline, stone count,
  setting, metal/gem color, and wearing logic.
- Check typography does not invent random brands, prices, URLs, QR codes, social handles, watermarks,
  or extra logos.
- Check each requested poster is one independent poster, not an unintended multi-poster grid.
- Check template execution: selected template card, template reason, required layout modules, and
  anti-still-life-degeneration are present and visible in the prompt/result.
- For campaigns, check source count times posters per source equals saved file count; each source
  has the requested slot count; prompt/source/provider/status metadata exists in runner jobs/state.
- Check the execution path used the repository runner or the bundled plugin runner; if no Image-2
  runner was available, confirm the task stopped as a blocker instead of falling back to
  `svt_jewelry.run_poster`.
