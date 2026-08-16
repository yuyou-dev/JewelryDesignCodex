---
name: jewelry-evolution-observer
description: Use when the user wants to preserve a successful jewelry agent result, analyze why it worked, extract reusable lessons, and propose updates to skills, agent instructions, docs, references, scripts, or checks without applying changes until confirmed.
---

# Jewelry Evolution Observer

## Purpose

Turn unusually successful jewelry agent sessions into reviewable improvement proposals. The observer captures why a result worked, separates reusable lessons from one-off taste, and prepares a scoped update plan for the parts of the agent system that should learn from it.

Skills are the primary entrypoint and the most common improvement surface, but they are not the only one. The observer may propose changes to local skills, skill references, agent instructions, README or docs, validation scripts, or other text/script surfaces that shape the ideal jewelry agent.

This skill is advisory by default. It proposes changes and waits for user confirmation before any repository files are edited.

## Trigger Scenarios

- The user says "呼出观察者", "沉淀这次效果", "把这次成功经验变成 agent 增强方案", "把这次成功经验变成 skill 增强方案", "分析这次为什么好", or similar.
- A generated jewelry image, poster, grid, catalog set, retouch, or video prompt has a notably strong result that should be easier to reproduce later.
- A repeated creative, review, routing, verification, documentation, or operating-rule pattern appears across sessions and may deserve a skill, reference, docs, or validation update.
- The user asks whether a successful case should update `jewelry-studio`, `jewelry-design`, `jewelry-poster`, `jewelry-catalog`, `jewelry-image-review`, another local skill, `AGENTS.md`, README, docs, scripts, or delivery guidance.
- During a jewelry task, a temporary prompt, helper script, delivery method, interaction tactic, or review pattern works especially well and may deserve promotion later.
- A design task incorrectly asks the user to choose IDs after a counted request, or presents visual delivery as complete without image generation attempts.

## Steps

1. Collect the case context: user brief, accepted output, visible review notes, reference images if available, the final render or revision prompt, and the user's stated reason for liking the result.
2. Identify what worked:
   - jewelry identity and silhouette
   - material and gemstone language
   - setting, construction, and scale choices
   - camera view, lighting, background, and styling
   - negative constraints and prompt ordering
   - routing behavior across design, render, review, catalog, poster, grid, retouch, or video skills
   - agent behavior, including when it asked questions, made tasteful defaults, preserved constraints, or avoided overclaiming
   - verification, review, and handoff behavior that made the outcome easier to repeat or trust
   - failure behavior, including unsolicited ID selection, planning-only delivery, skipped image generation, or completion claims without visual artifacts
3. Separate reusable lessons from accidental or case-specific details. Avoid overfitting a single style, product type, gemstone, model pose, or lighting setup into a global rule.
4. Read `references/evaluation-rubric.md` when judging whether a lesson is durable enough to propose.
5. Read `references/proposal-template.md` and write a proposal with concrete target files, proposed edits, risks, and verification.
6. For delivery-originated lessons, keep the proposal advisory and artifact-local. Name the temporary method, why it worked, candidate promotion location (`skill`, `docs`, `scripts`, or `tests`), risks, and suggested verification.
7. Recommend one of these dispositions:
   - `apply-to-skill`: update one or more existing skills.
   - `add-reference`: add an example, preset, rubric, or prompt pattern under a skill's `references/`.
   - `update-agent-instructions`: update `AGENTS.md` or another durable agent instruction file when the lesson is cross-cutting and concise.
   - `update-docs`: update README or docs when the lesson is human-facing, conceptual, or operational.
   - `add-validator`: update scripts only when the lesson is mechanical and checkable.
   - `record-case-only`: keep the case as inspiration without changing reusable instructions.
   - `defer`: wait for more examples before changing the system.
8. Treat GUI, visual app, dashboard, or interactive product ideas as long-range notes by default. Mention them only as future possibilities unless the user explicitly asks to plan GUI work.
9. Stop at the proposal unless the user explicitly confirms execution. If confirmed, classify the
   implementation as a separate repository-development request and make the approved edits through the normal
   repository-development workflow; no special development run is required.

## Input Constraints

- Accept chat context, attached images, local image paths, prompts, review notes, or a concise user description of what made the result excellent.
- If the final prompt or image is unavailable, state the limitation and infer only from visible context.
- Do not copy private generated media, credentials, or ignored artifacts into committed skill files.
- Do not require the user to provide JSON, formal ratings, or developer terminology.
- Do not steer the project toward GUI implementation unless the user explicitly asks; keep GUI ideas as deferred strategy notes.

## Output Requirements

- Default output is an `Agent Evolution Proposal` with:
  - `Case Summary`
  - `What Worked`
  - `Reusable Lessons`
  - `Recommended Disposition`
  - `Proposed System Changes`
  - `Risks`
  - `Verification Plan`
  - `Awaiting Confirmation`
- For delivery-originated temporary methods, explicitly include `Candidate Promotion Location`, `Risks`, and `Suggested Verification`.
- Proposed changes must name exact target files and the intent of each edit.
- Include enough detail for the next implementation pass to patch the relevant skill, reference, doc, or script safely, but do not paste large replacement files unless the user asks.
- Keep designer-facing language readable; put repository mechanics in the proposal sections, not in the creative critique.

## Verification

- Confirm the proposal does not directly mutate repository files.
- Confirm a jewelry-task proposal remains advisory and does not promote helper scripts, prompts, or docs into repo-level files automatically.
- Confirm every proposed change traces back to observed case evidence or a repeated pattern.
- Confirm global agent or skill changes are not based only on a one-off aesthetic preference.
- Confirm the plan preserves the core provider boundary: still images use the bundled Image-2
  runner and optional providers are not silently introduced.
- Confirm GUI work is deferred unless explicitly requested.
- Confirm the proposal includes a verification plan for testing the strengthened agent behavior with realistic jewelry creation prompts.
- Confirm counted visual-delivery failures are treated as contract issues, not user preference.
