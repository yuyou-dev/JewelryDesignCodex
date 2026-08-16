---
name: jewelry-studio
description: Natural-language jewelry design router for non-developers. Use implicitly for jewelry design, variants, remix, retouch, sketch-to-jewelry, model try-on, grids, catalogs, posters, display images, or explicit image review.
---

# Jewelry Studio

## Purpose

Give designers one conversational entry point for the core JewelryDesignCodex still-image
workflows. Route internally; never require the user to know Skill names or shell commands.

## Task workspace

Before the first task write or provider-preparation command, choose one stable task ID. Follow
`references/design-task-contract.md`:

- `artifacts/design-tasks/<task-id>/` contains exactly `proposal.md`, `progress.md`, `result.md`, and
  `handoff.md`.
- `artifacts/runs/<task-id>/` contains prompts, references, generated media, reports, provider state,
  logs, and task-local helpers.

Resume an existing task from those two roots. Never claim an asset exists unless its file exists and
is readable.

## Routing

1. Read the request, attachments, and any selected Gallery asset before asking questions.
2. Use the ordinary consolidated Apps UI form when the workflow is known but an identity-changing
   field is missing. If workflow, product identity, and output family are all unknown, or the user
   explicitly asks for deeper guided creation, route to `$jewelry-grill-me`. A clear brief executes
   without a mandatory form.
3. Route by user intent:
   - ordinary jewelry concept or render: `$jewelry-design`;
   - 4/8 source-identity extensions or “爆款二创”: `$jewelry-remix`;
   - marked local change, “put it here”, freehand sketch, or gemstone-assisted drawing:
     `$jewelry-local-edit`;
   - model-wearing placement from jewelry and model images: `$jewelry-model-tryon`;
   - product retouch: `$jewelry-retouch`;
   - 3x3 contact sheet: `$jewelry-grid-generation`;
   - separate redraws from grid cells: `$jewelry-grid-redraw`;
   - repeatable SKU set: `$jewelry-catalog`;
   - product display imagery: `$jewelry-display`;
   - campaign poster or ecommerce layout: `$jewelry-poster`;
   - explicit critique, ranking, selection, or revision advice: `$jewelry-image-review`;
   - explicit request to observe reusable workflow improvements: `$jewelry-evolution-observer`.
4. Treat an uploaded or Gallery-selected image as neutral asset context. The next user message may
   route it into any compatible workflow; “选择此款继续” never approves, ranks, or regenerates by
   itself.
5. A brand or collection name is a style hint, not proof of a local reference. Use user-provided
   references as source truth. If the user explicitly asks for online research and host web tools
   are available, prefer official sources and attach only the task-relevant result; otherwise ask
   for a reference image or proceed with a clearly labeled general style interpretation.

## Clarification and Apps UI

Read `references/conversation-ui-contract.md` before a form or visual result call.

- Resolve the exact registered Apps UI tool before falling back to chat text.
- Ordinary partial ambiguity gets one consolidated round.
- `$jewelry-grill-me` is a narrow multi-round exception with at most four unresolved fields per
  round and an explicit brief confirmation before generation.
- Do not use a form to offload delivery count, batch size, cost, or internal job selection.
- Do not emit fake interactive HTML or JSON.

After real outputs exist, use the matching Gallery/comparison UI. A successful specialized Apps UI
is the final media presentation and must not be followed by duplicate inline images. If the UI tool
is unavailable, errors, or omits an output, show every real successful image inline and state every
missing item.

## Image-2 execution

1. Resolve `<plugin-root>` as the installed `svt-jewelry-design` directory, two levels above this
   `SKILL.md`.
2. Use the bundled cross-platform dispatcher for controlled generation:

   ```text
   node "<plugin-root>/scripts/jdc.mjs" image2 <subcommand> ...
   ```

   Remix and visual workbench preparation use:

   ```text
   node "<plugin-root>/scripts/jdc.mjs" remix <subcommand> ...
   node "<plugin-root>/scripts/jdc.mjs" visual-workbench <subcommand> ...
   ```

3. Keep the current workspace as the task root and pass `artifacts/runs/<task-id>` as the runner
   workspace. Do not assume the public source repository is the current directory.
4. Read `references/professional-image2-prompt.md` and save the complete final Chinese design prompt
   under the run workspace. Remove workflow/API instructions from the provider prompt.
5. For batch work, register all independent jobs first, validate the same job manifest, then run one
   bounded concurrent `generate --only pending,failed`. Never select unrelated pending jobs from an
   older task.
6. Attach task-local references to every source-dependent or edit job. Do not replace the bundled
   runner with an unrelated image plugin or generic MCP tool.
7. Real provider operations use the user's own Codex login and gpt-image-2 access. If unavailable,
   record the blocker rather than presenting a text plan as completed visual delivery.

## Delivery rules

- Unless the user explicitly requests text only, a jewelry design request is visual delivery.
- “Design N pieces/styles” commits to N independent image deliverables or recorded attempts. A
  contact sheet counts as one file unless the user explicitly requested a grid.
- Sketch mode produces four independent `SKETCH-A` through `SKETCH-D` images; local edit and
  put-it-here produce one.
- The user-selected product category is the sole category truth. Never inject a pendant, brooch, or
  dual-use default that contradicts it.
- Use aesthetic defaults for non-identity choices, but ask when the missing choice changes the
  product or workflow.
- Display every generated result inline unless a successful specialized Apps UI already presents
  it. A file path alone is only fallback metadata.
- Verify requested count, readable files, requested category, references, and provider outcome.
  Do not automatically rank or regenerate for aesthetic reasons.
- Task-local helpers stay under `artifacts/runs/<task-id>/tools/` or `scratch/`. Production work must
  not edit repository Skills, docs, scripts, tests, or package files.

## Core package boundary

This core plugin contains still-image design and Apps UI only. Web reference-library search,
Dreamina/Seedance execution, and Feishu delivery are not implied capabilities. Optional video and
Feishu plugins must be separately installed, authorized, and explicitly requested.

## Verification

- The user never had to know a Skill name or command.
- Clarification followed the Apps UI contract and collected only unresolved fields.
- The full prompt and references map to the correct task and stable output IDs.
- Counted work has one independent artifact or honest attempt per committed deliverable.
- Visual output is actually visible, and no duplicate inline media follows successful Apps UI.
- No unsupported grade, origin, certification, price, stock, or brand claim was invented.
- No aesthetic review or subjective regeneration ran without an explicit request.
