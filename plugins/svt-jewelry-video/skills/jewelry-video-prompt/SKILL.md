---
name: jewelry-video-prompt
description: Use to turn finished jewelry images, model-wearing images, posters, or campaign briefs into reference-first video prompts before optional Dreamina Seedance submission.
---

# Jewelry Video Prompt

## Workflow

1. Collect the readable local files that define the accepted jewelry identity. A finished product
   image is mandatory before provider submission.
2. State the role of every reference: product identity, model pose, styling, environment, or motion.
3. Write a concise shot plan with locked jewelry facts, shot order, camera motion, lighting,
   duration, aspect ratio, and negative constraints.
4. For multiple videos, assign stable job IDs and finish every prompt/reference block before the
   first provider call.
5. If the user requests provider execution, hand the complete reference-first blocks to
   `$jewelry-dreamina-video`.

## Output

For each job provide:

- `Job ID`
- `Prompt`
- `Reference Images and Roles`
- `Locked Product Facts`
- `Shot Plan`
- `Provider Settings`

## Boundaries

- Do not invent a different jewelry design when the reference already defines the product.
- Do not plan text-only jewelry video generation.
- Do not claim that a prompt is a generated video.
- Model compatibility and authorization are checked by the optional provider Skill at execution
  time; do not duplicate a provider version matrix here.
