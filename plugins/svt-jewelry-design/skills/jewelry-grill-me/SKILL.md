---
name: jewelry-grill-me
description: Clarify an extremely vague jewelry idea through a deliberate multi-round structured interview before routing it to production. Use when the user explicitly asks for “Grill Me 珠宝”, “你到底想要设计什么”, or deeper guided creation, or when none of the jewelry workflow, product identity, and output family can be inferred from the request or attachments. Do not use for an otherwise clear workflow that is merely missing one or two fields.
---

# Jewelry Grill Me

## Purpose

Turn a genuinely unformed jewelry idea into one confirmed, executable brief without making the
designer understand internal skills, providers, or job planning. Use four purposeful discovery
rounds plus a separate confirmation round, preserve every answer, then return the confirmed brief
to `$jewelry-studio`.

## Trigger Scenarios

- The user explicitly asks for “Grill Me 珠宝”, a deep interview, or help discovering what to design.
- The request is so vague that its workflow family, jewelry identity, and output family are all unknown.
- A casual prompt such as “帮我做个珠宝” has no attachment or usable product/design clues.

Do not trigger for “开启随手画”, “做爆款二创”, “精修这张图”, or another known workflow
that only lacks a category, source role, design system, or similar field. Route those requests to one
ordinary consolidated follow-up form.

## Steps

Before any Apps UI call or fallback in this Skill, read and follow `$jewelry-studio`'s
`references/conversation-ui-contract.md`, especially Apps UI capability resolution.

1. Read `references/design-frontier.md` and establish only the unresolved decision frontier. Reuse
   facts already present in the current conversation, attachments, or selected Gallery asset.
2. Complete four discovery stages before confirmation: foundation, meaning, design language, then
   variation and delivery. Each stage is one submitted Apps UI round. When a stage's obvious facts
   are already known, use its deeper unresolved decisions instead of repeating them or skipping the
   stage. The final brief confirmation is a separate round and does not count as discovery.
3. Ask no more than four currently answerable fields in one round. Every Grill Me question round
   with unresolved fields must use `ask_jewelry_followup_questions` as its primary interaction
   surface. If the tool is not already callable, discover `ask_jewelry_followup_questions` by its
   exact name before any prose fallback. Only use another real host-provided structured form when
   exact-name discovery confirms absence, or concise chat questions after structured discovery
   fails or an actual form call returns an error. Never emit fake interactive HTML or JSON.
4. Use stable field ids and localized labels. Offer `other` plus a free-text path for off-list product
   types or directions. In the foundation stage, ask `delivery_count` when the user has not supplied
   a count; offer 1, 2, 4, and 8 plus a custom count. This is the Grill Me visual-exploration scope,
   not provider or batch planning. Never ask for provider, concurrency, cost, or internal job ids.
5. After every submission, restate the newly established facts in one short paragraph, preserve the
   earlier answers, and ask only the next unresolved frontier. Never answer the designer's side of
   the interview yourself.
6. In the variation stage, distinguish locked facts from flexible axes. For two or more images,
   create a named candidate matrix in which every candidate changes at least three visible axes
   such as silhouette, setting architecture, motif translation, stone layout, negative space, or
   material craft. Keep the confirmed product identity and story coherent across the set.
7. After all four discovery rounds, present one concise shared brief and explicitly ask the designer to confirm or correct it. Include the committed `delivery_count` and candidate variation plan. Do not
   create provider jobs, generate images, or claim execution before confirmation.
8. After confirmation, route the brief back through `$jewelry-studio` to the matching specialist
   Skill and continue normally. Do not keep Grill Me active after the shared brief is accepted.

## Input Constraints

- Accept ordinary Chinese or English, partial thoughts, attachments, and Gallery selection context.
- Treat an explicit Grill Me request as sufficient even when some initial design facts are already known.
- Treat a known workflow with missing product category as ordinary clarification, not extreme ambiguity.
- Keep each round to at most four fields and keep prior answers immutable unless the user corrects them.
- Preserve an explicit delivery count. Otherwise collect it once with stable values `count_1`,
  `count_2`, `count_4`, `count_8`, and `other`; the accepted number becomes a committed delivery count.
- Do not invent gemstone grade, origin, certification, price, brand facts, or absent reference content.

## Output Requirements

- Produce a short running summary after each round, not a long questionnaire transcript.
- End with one designer-readable brief covering workflow, product, design direction, essential
  materials or source roles, output family, delivery count, locked facts, and candidate variation plan.
- Require a clear confirmation or correction before handing the brief to execution.
- Use the user's language for questions, summaries, and confirmation.

## Verification

- Confirm the trigger was explicit or the original request had no inferable workflow, product, and output.
- Confirm four discovery rounds were submitted before the separate confirmation round.
- Confirm no round exceeded four fields and no already-resolved field was asked again.
- Confirm a missing delivery count was collected once and every multi-image brief defines visibly
  separated candidate branches before provider jobs are created.
- Confirm every question round used the dynamic Apps UI form, or records a real discovery/call
  failure before a structured-host or prose fallback.
- Confirm ordinary partial ambiguity did not become a multi-round Grill Me session.
- Confirm no provider work started before the shared brief was confirmed.
- Confirm the accepted brief returned to `$jewelry-studio` and the matching production workflow.
