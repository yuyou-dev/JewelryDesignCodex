# Troubleshooting

Start with the observable state, not by editing caches or configuration files:

```text
codex plugin marketplace list --json
codex plugin list --available --json
codex mcp get svt_jewelry_ui --json
node <marketplace-root>/scripts/jdc.mjs doctor --json
```

Obtain `<marketplace-root>` from the `root` field for `jewelry-design-codex` in the marketplace-list JSON.

## `codex plugin` is unavailable

The PATH command may be older than the Codex Desktop-bundled CLI. Follow [INSTALL.md](../INSTALL.md#2-resolve-the-codex-cli) to resolve the bundled executable and rerun its `--version` and `plugin marketplace --help` commands. Update Codex Desktop when the bundled executable also lacks plugin support.

## Marketplace add fails

- Confirm Git 2.30+ and HTTPS access to GitHub.
- Confirm the source is exactly `yuyou-dev/JewelryDesignCodex` and the selected release ref exists.
- Inspect proxy and certificate errors without changing proxy settings automatically.
- If `jewelry-design-codex` exists with a different source, stop. Remove it only with user approval after showing the conflicting source.

Rerun marketplace-list JSON after recovery. Command exit status alone is not sufficient verification.

## Plugin is listed but not enabled

Verify the exact ID `svt-jewelry-design@jewelry-design-codex`. A similarly named plugin from another marketplace is not equivalent. Install through `codex plugin add`; do not copy plugin folders into the cache.

After a correct install, fully quit and reopen Codex Desktop. Use a new task because the installing task may retain its old tool inventory.

## MCP is missing

Run `codex mcp get svt_jewelry_ui --json`. Then check doctor for:

- unresolved Node.js runtime;
- missing plugin files;
- a launcher path outside the plugin root;
- invalid MCP configuration; or
- a restart requirement.

Use the packaged launcher and `.mcp.json`. Do not register a second hand-written MCP entry with the same name.

## Apps UI stays on loading

1. Confirm the tool call completed and returned a UI resource rather than only prose.
2. Expand the tool result and look for an explicit error or missing media path.
3. Confirm the current task was created after the latest plugin install/update and Codex restart.
4. Replay a form that needs no media. If forms load but a Gallery does not, inspect doctor/media-budget diagnostics rather than reinstalling the whole plugin.
5. Capture sanitized console/tool output and report it with the UI resource name and plugin version.

A valid UI ends in loaded, empty, or explicit error state. Repeated tool calls that remain on loading are not a workaround.

## Form is clipped or has no submit button

- Use a current Codex Desktop build and the latest tagged plugin.
- Check operating-system display scaling and repeat at the default app zoom.
- Record the UI resource URI, window size, scale factor, light/dark mode, and whether the host frame itself scrolls.
- Do not add a nested vertical scroll container as a local patch. The conversation owns vertical scrolling; the Apps UI must resize within its host frame.

## Image generation fails after UI succeeds

UI readiness and provider readiness are separate. Check the user's Codex login and gpt-image-2 access through Codex's supported status/doctor path. Do not inspect or copy authentication files. Keep the actual provider error and successful prepared jobs in the task workspace; do not claim a text plan is completed image delivery.

## Paths fail on Windows

- Use native Windows, not an unverified compatibility layer.
- Confirm Node 20+ and Python 3.10+ are visible to the Codex Desktop process, not only to another shell profile.
- Keep paths quoted and pass them as argument vectors. Do not convert UTF-8 or space-containing paths into short names.
- Report the sanitized path shape and failing command component without including the Windows account name.

## Update did not change the version

`codex plugin marketplace upgrade jewelry-design-codex --json` refreshes the configured Git ref. A marketplace pinned to `v0.1.0` stays on that release. Moving to a newer tag requires an intentional source-ref change through Codex marketplace commands, followed by doctor, full restart, and a new task.

## Clean uninstall

Follow [INSTALL.md](../INSTALL.md#uninstall). Plugin and marketplace removal must leave user design workspaces and generated media intact. If Codex still shows old tools after removal, fully restart the app; do not delete broad cache directories.

For a reproducible unresolved problem, use [Support](SUPPORT.md). Send suspected vulnerabilities through [Security](../SECURITY.md), not a public issue.
