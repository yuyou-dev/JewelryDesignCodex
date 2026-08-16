---
name: jewelry-image-review
description: Use only when the user explicitly asks to review, rank, select, critique, or revise generated jewelry images; compare them with the brief and references and provide targeted guidance.
---

# Jewelry Image Review

## Purpose

Evaluate generated jewelry images when the user explicitly requests image review. This skill is
optional and must not run automatically after generation or become a delivery gate.

## Trigger Scenarios

- The user asks to “审图”, rank, select, compare, or strictly critique generated images.
- The user asks what to improve or requests a revision based on visible image issues.
- The user explicitly asks for aesthetic, fidelity, or product-plausibility evaluation.

## Steps

1. Compare the image against the brief, locked product facts, references, and prompt.
2. Inspect jewelry-specific issues: stone count, prongs, setting plausibility, symmetry, metal color, clasp, hinge, scale, and comfort.
3. Inspect image quality: crop, lighting, background, text, reflections, visible distortion, and unwanted props.
4. Explain the comparison or recommendation without changing task completion state.
5. Write a targeted complete revision prompt only when the user asks for revision or regeneration.

## Input Constraints

- Require the generated image or a user description plus the original brief.
- Do not approve a render that violates locked jewelry identity.
- Do not start regeneration solely because the review found a subjective issue; wait for the user's
  explicit revision request.

## Output Requirements

- Review with `Summary`, `Issues`, `Jewelry Fidelity`, `Material Plausibility`, and `Image Quality`.
  Add `Selection` or `Revision Prompt Notes` only when the request needs them.

## Verification

- Confirm every issue maps to a visible defect or brief mismatch.
- Confirm any revision notes were explicitly requested and are specific enough for a new complete
  Image-2 prompt.
- Confirm accepted images satisfy locked product facts.
- Confirm the review did not create a gate, extra task file, or automatic regeneration job.
