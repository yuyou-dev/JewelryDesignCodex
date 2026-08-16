# Design Task Contract

A designer-facing jewelry task is a lightweight, resumable group of four Markdown documents plus a
separate media workspace. It is not a lifecycle state machine.

## Identity And Roots

Choose one safe `<task-id>` before the first task write and reuse it in both roots:

- `artifacts/design-tasks/<task-id>/`: human-readable task documents.
- `artifacts/runs/<task-id>/`: prompts, references, generated images/videos, reports, provider
  state and logs, downloads, tools, and scratch files.

The task id must be a single path segment. Do not accept absolute paths, `..`, separators, symlink
escapes, or another task's path.

## Media Retention

The media workspace holds the task's durable inputs, outputs, and continuation context.

- Keep `outputs/`, referenced source media, prompts needed for continuation, reports, delivery
  records, and the small job/state manifests while `result.md` or `handoff.md` depends on them.
- Task-local `.codex-home`, `.codex-home-*`, and `.codex-home-requeue` directories are disposable
  worker runtimes. After all workers for that task have stopped, they may be deleted with exact,
  task-scoped paths without deleting the task or its delivered media.
- Logs and scratch files may be pruned after completion when they are not the only evidence of a
  blocker or promised provider outcome.
- Never clear all of `artifacts/runs/` as application cleanup. To retire a whole task, first copy
  its exported ZIP outside both task roots and verify its SHA-256, or explicitly choose to discard
  the deliverables; then remove both same-ID roots with explicit scope.

## Exact Four-File Contract

`artifacts/design-tasks/<task-id>/` contains exactly these files and no directories:

### `proposal.md`

```markdown
# <Task Title>

## Goal

## Deliverables

## Design Direction

## Constraints
```

The top-level heading is the human task title. Update this document directly when the requested
outcome or direction changes. Do not create a decision log or assumptions sidecar.

### `progress.md`

```markdown
# Progress

## Current

## Checklist

## Blocked

## Next
```

Use it as a concise current-work view. Checklist items and blockers describe reality but are not
phase gates or finalize requirements.

### `result.md`

```markdown
# Result

## Summary

## Deliverables

## Missing
```

Embed or link the real images and reports. State the actual delivered
count. Put objective missing items or failed provider outcomes under `Missing`; never use promised
or planned assets as completion evidence.

### `handoff.md`

```markdown
# Handoff

## Current State

## Continue From

## Open Items

## Key Paths
```

Refresh it before ending a working turn so another conversation can continue from the current
documents and media paths without reconstructing a hidden lifecycle.

## Loop

```text
Proposal -> Execute/Update Progress -> Present Result -> Handoff -> Continue
```

Create all four files as one operation; a failed creation must not leave a partial task directory.
Resume by reading the four documents and media workspace. No other task state, document, directory,
completion action, or mandatory post-generation review belongs to this contract.

Objective checks such as requested count, file readability, jewelry type, reference presence, and
provider outcome may update `progress.md` or `result.md`. Subjective
aesthetic review runs only when the user explicitly requests review, ranking, selection, critique,
or revision; it does not add files or gates to the task contract.

## Delivery Rules

- Text-only work occurs only when the user explicitly asks for no image or concept only.
- Otherwise a design request moves toward real visual delivery. A failed or unavailable provider is
  reported under `Blocked` and `Missing`, not replaced by a plan or prompt.
- “Design N pieces/styles” means N separate deliverables or recorded attempts. A contact sheet or
  combined preview counts as one asset unless the user requested that exact shape.
- Technical retries may recover broken, blank, unreadable, or missing output. They are not aesthetic
  revision and do not authorize subjective regeneration.
- Jewelry delivery writes only the active task's two artifact roots. Repository code, Skills,
  scripts, tests, and documentation do not change during a design task.
- Reference-library files needed by a provider are copied into the active task's `references/`
  directory. Another task's workspace is never used as input.

## End Of Turn

Before ending a working turn, make the four documents agree with the filesystem:

- `proposal.md` reflects the current request and direction;
- `progress.md` states what happened, what is blocked, and the next executable action;
- `result.md` links only real outputs and names the actual delivered and missing counts;
- `handoff.md` gives the minimal paths and context needed to continue.

This document is the only task-structure contract. Provider and application documents may explain
their own commands, but may not add task files, lifecycle state, completion gates, or review stages.
