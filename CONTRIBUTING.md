# Contributing

Thanks for helping make professional jewelry design more accessible in Codex.

## Before starting

Open an issue for a behavior change, new external provider, breaking schema change, or new Apps UI surface. Small documentation, test, portability, and accessibility fixes can go directly to a pull request.

Keep the core install self-contained:

- macOS and native Windows are the required platforms;
- core runtime code must not require `npm install`, `pip install`, ImageMagick, a hosted MCP, or a project-owned credential;
- video and Feishu remain optional integrations;
- user assets, generated media, credentials, task logs, and absolute local paths never belong in the repository; and
- a modified branded distribution follows [TRADEMARKS.md](TRADEMARKS.md).

## Development setup

Requirements: Git 2.30+, Node.js 20+, Python 3.10+, and a current Codex CLI with plugin marketplace support.

1. Fork and clone the repository.
2. Work on a focused branch.
3. Run the repository doctor from the repository root:

   ```text
   node scripts/jdc.mjs doctor --offline --json
   ```

4. Run the core plugin tests:

   ```text
   npm --prefix plugins/svt-jewelry-design test
   ```

5. Run the repository's full check command when present in the root package manifest.

Use a temporary Codex home or a disposable local marketplace for installation tests. Do not overwrite a contributor's existing `personal` marketplace or edit Codex cache state by hand.

## Change rules

- Preserve stable tool, resource, option, and result IDs unless the change intentionally introduces a versioned contract.
- A new UI resource or breaking payload change receives a new versioned `ui://` URI.
- Every tool must retain a useful text fallback when Apps UI is unavailable.
- Keep Apps UI compact, keyboard-accessible, touch-usable, readable in light and dark themes, and free of nested vertical scrolling.
- Use neutral asset-selection results so a chosen image can continue into any later jewelry workflow.
- Image generation and optional provider operations must use the user's own authorization and explicitly selected task files.
- Add focused tests for the behavior changed. Avoid committing generated screenshots except sanitized, intentional documentation assets.

## Pull requests

A pull request should state:

- the user-visible problem and chosen behavior;
- affected platforms and compatibility impact;
- tests run and their results;
- screenshots for Apps UI changes at normal and narrow widths; and
- any license, privacy, credential, or provider implication.

By submitting a contribution, you agree that it is licensed under Apache License 2.0 and that you have the right to submit it. Keep third-party notices accurate when adding or changing vendored material.
