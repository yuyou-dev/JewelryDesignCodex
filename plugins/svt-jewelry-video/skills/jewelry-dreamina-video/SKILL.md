---
name: jewelry-dreamina-video
description: Use to submit or query reference-first Dreamina Seedance jewelry video tasks after a finished local jewelry image exists and the optional Dreamina CLI is separately installed and authorized.
---

# Jewelry Dreamina Video

## External dependency

This optional plugin does not bundle Dreamina, credentials, credits, or a provider account. Before
the first provider operation:

1. Confirm the `dreamina` CLI is installed from its official distribution.
2. Inspect `dreamina --help` and the relevant subcommand help; the installed CLI is the interface
   source of truth.
3. Check authorization without printing tokens. If authorization is missing, pause and let the user
   complete the CLI's own login flow.

Do not copy auth files, API keys, cookies, or account state into the task or plugin.

## Workflow

1. Require at least one readable local jewelry image or video. The reference controls product
   identity; this Skill never invents a product from text alone.
2. Use the prompt prepared by `$jewelry-video-prompt`, or write an equivalent reference-first prompt
   with locked materials, camera motion, lighting, ratio, duration, and negative constraints.
3. Inspect current CLI help, then submit with local reference paths and every required setting
   explicitly. Do not assume provider defaults.
4. Treat the provider JSON as authoritative. Preserve `submit_id`, submit status, failure reason,
   model, duration, ratio, and reference paths in the active task workspace.
5. Query an accepted `submit_id` until it reaches a terminal status. Download only when the user
   needs a local file, and record the returned URL or local path plus media metadata.
6. For multiple videos, prepare all labeled requests first, submit with bounded concurrency, and
   keep a `job id -> submit_id -> status -> result` mapping.

## Boundaries

- Dreamina is optional and video-only here. Use the core JewelryDesignCodex plugin for still images.
- Never submit without a local product reference or fall back to text-only jewelry video.
- Never report a queued, failed, or compliance-blocked submission as complete.
- Provider login, quotas, safety confirmation, and billing remain between the user and Dreamina.

## Verification

- The referenced files exist and the jewelry identity is locked to them.
- The current CLI accepted the selected settings.
- A successful result contains real video media, not only a submit identifier.
- User-facing output contains no credential, token, cookie, or unredacted account identifier.
