---
name: jewelry-catalog
description: Use to plan repeatable jewelry catalog images for product pages, marketplace listings, SKU sets, main white images, angles, macro details, scale wearing, packaging, and lifestyle shots.
---

# Jewelry Catalog

## Purpose

Turn one or more jewelry SKUs or accepted designs into consistent commerce image sets.

## Trigger Scenarios

- The user wants Shopify, marketplace, PDP, lookbook, or catalog outputs.
- Each source image or design represents one SKU.
- The user needs main image, angle views, macro details, packaging, scale, and lifestyle imagery.

## Steps

Before any Apps UI call or fallback in this Skill, read and follow `$jewelry-studio`'s
`references/conversation-ui-contract.md`, especially Apps UI capability resolution.

1. Identify SKU count and channel goal.
2. Choose profile: core five-image set or expanded seven-image set.
3. Define shared catalog standards: background, shadow, crop, scale, color accuracy, and allowed props.
4. Create per-slot image directions with complete product facts repeated in every slot.
5. Build final Image-2 prompts using `$jewelry-studio` prompt guidance and render when
   requested. Use `$jewelry-image-review` only when the user explicitly asks to review, rank, select,
   critique, or revise the results.
6. Preserve accepted catalog and model images as task-local source-of-truth assets for any later,
   separately requested workflow.
7. When the user has not already specified catalog slots or channel format, call
   `ask_jewelry_creation_brief` with workflow `catalog`; core-five versus expanded-seven is a
   catalog profile, not permission to reduce an explicit count. After real slot images exist, call
   `show_jewelry_creation_gallery`. On success, do not repeat the same images inline; on tool error,
   show every real slot and name any missing output.

## Input Constraints

- Require SKU reference images, accepted renders, or precise design briefs.
- Do not mix SKU identities.
- Do not invent dimensions, grades, warranties, or channel compliance claims.

## Output Requirements

- Catalog plan with `SKU`, `Channel`, `Slots`, `Shared Style`, `Product Facts`, `Forbidden Changes`, and `Image-2 Prompt Notes`.

## Verification

- Check every slot has a commerce purpose.
- Check product identity remains consistent across images.
- Check commercial claims remain conservative and do not invent dimensions, grades, warranties, or channel compliance.
- Check any video handoff uses accepted catalog/model images as references.
