---
name: jewelry-remix
description: Create a designer-friendly “爆款二创” workflow from one existing jewelry source image, collecting one structured brief and producing 4 or 8 independent, differentiated Image-2 designs. Use for 爆款二创, 二创, 款式延展, 设计进化, or requests to derive four or eight directions from an existing jewelry image.
---

# Jewelry Remix

## Purpose

Turn one real jewelry source image into 4 or 8 independent, traceable remix designs. Keep the
source responsible for product identity and construction; use other references only for design language.

## Trigger Scenarios

- The user says “爆款二创”, “二创”, “款式延展”, or asks for 4/8 directions from one existing piece.
- The user wants controlled divergence rather than random same-prompt variants.
- The user wants every result compared against the same source image.

## Steps

Before any Apps UI call or fallback in this Skill, read and follow `$jewelry-studio`'s
`references/conversation-ui-contract.md`, especially Apps UI capability resolution.

1. Require one real source jewelry image. Optional style, material, or craft references may be used,
   but do not create a source from text and do not accept a local mask in v1.
2. Choose one task id and follow the repository four-document task contract. Copy every required
   source/reference into the active run workspace before compiling jobs.
3. Decide brief completeness from explicit answers, not from what can be inferred from the source
   image. A complete brief has explicitly answered values for: 4/8 mode; `gold`/`gem_set` design
   system; structure fidelity, change intensity, and fusion strategy; plus theme, morphology, style,
   and material/craft direction. "Explicitly answered" means the value appears in the user's current
   instruction or in stable JSON from an earlier submitted Remix form. Source-image analysis may
   prefill editable form choices and build the identity lock, but it does not make an unanswered
   field complete. Additional direction is optional; a reference role is required only when extra
   references exist.
4. If any required decision group is unresolved, call `ask_jewelry_remix_brief`. If the tool is not
   already callable, discover `ask_jewelry_remix_brief` by its exact name before declaring it
   unavailable. This dedicated product intake may ask for 4 or 8 because that is the selected remix
   mode, not a batch-cost or provider question. Use one compact round. Show any inferred design
   system as an editable prefill; when no system can be inferred, leave it unselected. Only skip the
   form when every required decision group was explicitly answered. If exact-name discovery fails,
   ask the same unresolved fields once in concise chat instead of synthesizing preferences.
5. Read `references/remix-prompt-contract.md` and `references/remix-taxonomy.v2.json`. Analyze the source into a base identity lock, then
   create exactly `REMIX-A` through `REMIX-D` or `REMIX-H`. Give every branch a distinct positioning,
   change scope, theme, morphology, style/material treatment, and use case.
6. Save the structured brief inside the run workspace. Resolve `<plugin-root>` as the installed
   `svt-jewelry-design` directory, two levels above this `SKILL.md`, then run:

   ```bash
   node "<plugin-root>/scripts/jdc.mjs" remix prepare --workspace artifacts/runs/<task-id> --brief artifacts/runs/<task-id>/remix-brief.json
   node "<plugin-root>/scripts/jdc.mjs" image2 add-jobs --workspace artifacts/runs/<task-id> --input artifacts/runs/<task-id>/remix/jobs.json
   node "<plugin-root>/scripts/jdc.mjs" image2 validate-jobs --workspace artifacts/runs/<task-id> --job-manifest remix/jobs.json --requested-count <4-or-8>
   node "<plugin-root>/scripts/jdc.mjs" image2 generate --workspace artifacts/runs/<task-id> --job-manifest remix/jobs.json --only pending,failed --parallel 4
   ```

7. The matrix keeps the designer-facing stable IDs `REMIX-A` through `REMIX-H`; runner job IDs and
   output paths add a batch suffix so repeated Remix rounds in one workspace never overwrite or
   select an earlier round. Always select the exact current `remix/jobs.json` manifest. Verify only
   objective delivery facts: requested count, unique readable files, source attachment, stable IDs,
   and provider outcome. Do not auto-rank, critique, select, or aesthetically regenerate.
8. After all 4 or 8 outputs exist, call `show_jewelry_remix_gallery` with the real source and one
   candidate entry per `REMIX-*`. A successful call is the final visual presentation: do not repeat
   the source and candidate images inline. The Gallery records the chosen stable ID as neutral
   asset context; the next user-authored message chooses the workflow. It must not automatically
   generate another round or preset a next action.
9. If the Gallery tool is unavailable or returns an error, display the source and every successful
   candidate inline and state the missing count. Do not claim a complete delivery unless the
   requested 4 or 8 independent files exist.

## Input Constraints

- Require one source image that is inside the active task workspace.
- Keep source-image identity separate from optional reference roles.
- Use only the v2 taxonomy IDs belonging to the selected `gold` or `gem_set` design system. Use the
  `other` choice plus its matching custom text field for a direction outside the presets.
- Support only 4 or 8 candidates; do not substitute a contact sheet, crop grid, or one prompt with
  multiple random outputs.
- Do not ask the user about provider cost, concurrency, retries, or internal job selection.
- Do not invent brand authorization, gemstone grading, certification, origin, price, or production readiness.

## Output Requirements

- Produce one identity lock, one remix matrix, and 4 or 8 independent full prompts and PNG outputs.
- Preserve stable IDs through retries and presentation.
- Keep `requested_count`, `planned_count`, `done_count`, `failed_count`, and `missing_count` truthful
  in task progress/result documents.
- Treat the Gallery as presentation only; it does not add a deliverable, approve a design, or rank candidates.

## Verification

- Confirm one source image and any optional references are readable inside the active run workspace.
- Confirm the intake was skipped only when every required decision group was explicitly answered;
  source-image inference was used only to prefill editable choices or build the identity lock.
- Confirm exact-name discovery was attempted before treating `ask_jewelry_remix_brief` as unavailable.
- Confirm IDs are exactly `REMIX-A` to `REMIX-D` or `REMIX-H`, with unique prompts and outputs.
- Confirm each prompt repeats the identity lock and states a materially different change scope.
- Confirm the existing project Image-2 runner generated or recorded an attempt for every candidate.
- Confirm a successful Gallery is not followed by duplicate inline images; fallback is used only on
  tool failure or incomplete delivery.
- Confirm no subjective image review or automatic next round occurred without an explicit user request.
