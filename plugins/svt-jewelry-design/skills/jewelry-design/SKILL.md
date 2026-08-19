---
name: jewelry-design
description: Use implicitly for natural-language jewelry design requests from designers, including text, reference images, sketches, prior renders, variants, refinements, and Image-2-ready concepts.
---

# Jewelry Design

## Purpose

Create new jewelry design directions while preserving professional jewelry vocabulary and routing final visuals through the Image-2 skills. The user should not have to know skill names; use this skill naturally when they ask for a jewelry design.

## Trigger Scenarios

- The user wants a new ring, necklace, earrings, bracelet, pendant, brooch, charm, cufflink, or jewelry suite.
- The user wants variations or refinements from a prior generated design.
- The user provides a sketch or photo as inspiration rather than as an exact product to preserve.
- The user provides an unmarked inspiration sketch for a new design. If they need spatial drawing,
  an anchored gemstone, or a marked local change, route to `$jewelry-local-edit` instead.
- The user says ordinary phrases such as "设计一枚戒指", "帮我做一套项链方案", "生成一个珠宝设计", or "做几版高级珠宝方向".
- The user gives a brand, collection, material, or motif style hint, such as Cartier peacock high jewelry, before asking for a new design.
- The user asks for "设计 N 款", "做 N 个类似款", "方案集", "款式集", or "系列延展"; default these to visual design delivery unless they explicitly ask for text only.

## Steps

1. Silently structure the brief. Do not expose internal workflow names unless the user asks.
   If missing information changes product identity or the entire workflow, follow
   `$jewelry-studio`'s `references/conversation-ui-contract.md` and ask one consolidated round.
   Use a structured follow-up form when the host provides one; otherwise ask one concise question.
2. Use reference analysis when images, sketches, or prior renders are present.
   When a sketch is also the interaction surface—freehand drawing, “put it here”, gemstone
   placement, or a local marked region—route to `$jewelry-local-edit` instead of treating it as an
   ordinary inspiration-only reference. Route model-wearing placement to `$jewelry-model-tryon`.
3. If the user provides a brand, collection, material, motif, or style hint, treat it as an
   interpretation unless a user-supplied reference establishes visual facts. If the user explicitly
   asks for online research and the host provides web tools, prefer official sources and save only
   task-relevant references. Do not copy an exact branded product.
4. If the request is type-specific, read `references/design-presets.md` for compact ring, necklace, earrings, bracelet, and material defaults.
5. Define type, silhouette, focal element, metal, gems, cuts, setting, motif, finish, scale, wearer context, and product tier.
6. Add professional construction details: supports, closures, shank or chain structure, setting security, comfort, surface finishing, and manufacturability risks.
7. Create two to four variants when the user has not fixed material or style.
8. For normal designer-facing design requests, assume a visual output is useful. Build a complete professional Image-2 prompt using `$jewelry-studio` prompt guidance and render when available, unless the user explicitly asks for text only.
9. For counted requests, treat the count as committed. "设计 33 款" means create 33 deliverables; do not ask the user to choose IDs or pick a first batch unless they explicitly ask for selection.
10. For option sets, similar styles, style collections, or series extensions, each concept should have enough design detail to support image generation, and image generation should be attempted for the requested count when available. One concept requires one separate image artifact or one recorded generation attempt; a contact sheet, collage, or multi-panel preview is not a substitute unless the user explicitly requested a grid/contact sheet. When an accepted Grill Me brief requests multiple images, preserve its locked facts and compile its named candidate matrix before registering jobs. Every candidate must differ on at least three visible design axes such as silhouette, setting architecture, motif translation, stone layout, negative space, or material craft; changing only adjectives, crop, background, or camera angle does not create a distinct design.
11. If the user asks for a visual, "出图", "生成图片", "render", "画出来", or similar, treat same-turn rendering as required when image generation is available.
12. When the user explicitly requests critique or revision, use `$jewelry-image-review` and preserve
    locked elements in the revision brief. Do not run it automatically after generation.
13. After one to twelve ordinary jewelry-design images exist, call
    `show_jewelry_design_gallery` with `ui://svt-jewelry/design-gallery/v2.html`. Preserve each real
    runner job id and provide concise per-design metadata. A successful Gallery is the final visual
    presentation, so do not repeat the same images inline. If the tool is unavailable, returns an
    error, delivery is incomplete, or more than twelve designs were requested, show every real
    successful image inline and state any missing count. Selection records a neutral stable asset
    context; the designer's next message may route to any supported workflow. It does not approve,
    rank, regenerate, reduce the committed count, or start another job.

## Input Constraints

- Do not require the user to type `$skill` names, JSON, command lines, or developer-facing instructions.
- Do not treat inspiration photos as exact products unless the user asks for preservation.
- Do not invent grading, price, origin, certification, brand ownership, or production readiness.
- Do not claim that a brand or collection reference was inspected unless a readable user attachment
  or cited research source was actually used.
- Keep wearer comfort, stone security, clasp/hinge logic, and scale plausible.
- If the user explicitly says text only or no image, do not render.

## Output Requirements

- Designer-facing concept with `Name`, `Type`, `Design Intent`, `Silhouette`, `Materials`, `Gem Plan`, `Setting`, `Craft Details`, `Variants`, `Risks`, and `Image-2 Prompt Notes`.
- When references are used, include their task-local paths or source citations as inspiration
  evidence for downstream Image-2 work.
- For production option sets, include a recommended `交付等级`, per-style visual direction, and image-generation status for the requested count.
- For a multi-image Grill Me brief, include the candidate branch name, its three or more changed
  axes, and the shared locked facts carried across the set.
- For counted production option sets, track per-design image status. The final answer must not imply completion if fewer than N separate images or N recorded generation attempts exist.
- For one to twelve completed ordinary design images, prefer `show_jewelry_design_gallery`; keep
  full inline delivery as the required fallback and for sets larger than twelve.
- Keep the visible answer concise, but make the hidden or displayed final image prompt complete enough for high-quality rendering.
- State a user-friendly next step such as "我可以继续出图", "我可以做三版变化", or "我可以写商品文案"; do not force skill names on normal users.

## Verification

- Confirm the concept answers the user's requested jewelry type and style.
- Confirm brand or collection hints are labeled as interpretation unless grounded by a real source.
- Confirm materials and construction do not contradict each other.
- Confirm the image prompt notes include enough visual detail for gpt-image-2.
- Confirm a render request is not using a shortened summary instead of the complete professional prompt.
- Confirm a counted production request was not downgraded into an ID-selection workflow.
- Confirm a counted production request was not downgraded into a contact-sheet, collage, or combined-preview workflow unless the user explicitly requested that output shape.
- Confirm multi-image Grill Me candidates are structurally distinct rather than prompt paraphrases
  or presentation-only changes.
- Confirm a successful design Gallery received every completed item with its real runner id and was
  not followed by duplicate inline images.
