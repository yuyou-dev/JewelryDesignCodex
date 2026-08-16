---
name: jewelry-model-tryon
description: Use for visual jewelry model try-on by locally cutting out a real product, dragging it onto a model, and using that placement as a gpt-image-2 reference. V1 covers rings, bracelets, necklaces, pendants, earrings, and brooches.
---

# Jewelry Model Try-On

## Purpose

Create a realistic model-wearing image from one real jewelry image and one real model image. The
Apps UI records approximate position, scale, rotation, and earring pairing; Image-2 rebuilds the
final perspective, anatomy-aware occlusion, contact, material, and light.

## Trigger Scenarios

- The user wants a ring or bracelet placed on a model's hand or wrist.
- The user wants a necklace, pendant, earrings, or brooch worn by a supplied model.
- The user wants to drag a cutout into position before generation.
- The user says “模特佩戴”, “上身效果”, “试戴”, or “把这件首饰放到模特上”.

## Steps

Before any Apps UI call or fallback in this Skill, read and follow `$jewelry-studio`'s
`references/conversation-ui-contract.md`, especially Apps UI capability resolution.

1. Create/resume one design task. Copy the exact jewelry product and model images into
   `artifacts/runs/<task-id>/references/` before opening the UI.
2. Read `references/model-tryon-image2-contract.md`. Infer the category when objective; ask one
   concise question only if ring/bracelet/necklace/pendant/earrings/brooch cannot be determined.
3. Call `open_jewelry_tryon_editor` with the task-local absolute jewelry and model paths. Use its
   project-local basic cutout, drag, scale, rotation, and optional paired-earring control. The canvas
   is an approximate composition reference, not a finished composite.
4. After the UI saves a stable draft, resolve `<plugin-root>` as the installed
   `svt-jewelry-design` directory, two levels above this `SKILL.md`, then compile and generate:

   ```bash
   node "<plugin-root>/scripts/jdc.mjs" visual-workbench prepare-tryon --workspace artifacts/runs/<task-id> --draft artifacts/runs/<task-id>/visual-workbench/<draft-id>/draft.json --job-id TRYON-A
   node "<plugin-root>/scripts/jdc.mjs" image2 add-jobs --workspace artifacts/runs/<task-id> --input artifacts/runs/<task-id>/visual-workbench/<draft-id>/jobs.json
   node "<plugin-root>/scripts/jdc.mjs" image2 validate-jobs --workspace artifacts/runs/<task-id> --job-manifest visual-workbench/<draft-id>/jobs.json --requested-count 1
   node "<plugin-root>/scripts/jdc.mjs" image2 generate --workspace artifacts/runs/<task-id> --job-manifest visual-workbench/<draft-id>/jobs.json --only pending,failed --parallel 1
   ```

5. Verify the output preserves both identities. Present completed outputs through
   `show_jewelry_creation_gallery` with workflow `tryon` and stable `TRYON-*` ids. If unavailable or
   erroring, show every real completed image inline.
6. Do not auto-rank, approve, retouch, or start a second pose without explicit instruction.

## Input Constraints

- Require one readable task-local jewelry image and one readable task-local model image.
- V1 supports rings, bracelets, necklaces, pendants, earrings, and brooches.
- Basic local cutout is only a placement aid. Do not promise pixel-perfect alpha or use a different image backend.
- Keep the jewelry's design identity and the model's identity, anatomy, pose, clothing, and background stable.

## Output Requirements

- Save one stable draft with a flattened composite and optional cutout, then produce one full prompt,
  one Image-2 runner job, and one final wearing image or truthful failed attempt.
- Reference order must be jewelry original, model original, placement composite, then optional cutout.
- The final image must rebuild real perspective, lighting, contact shadow, material response, and occlusion.

## Verification

- Confirm both source images and draft assets are readable inside the run workspace.
- Confirm the category-specific wearing rule appears in the prompt.
- Confirm the final image did not change the jewelry design or model identity and has no duplicate/floating product.
- Confirm a successful Gallery is not followed by duplicate inline images.
- Confirm no aesthetic review or unrequested regeneration occurred.
