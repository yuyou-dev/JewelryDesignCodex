# Update JewelryDesignCodex

This is the permanent update Runbook for Codex. Read it completely before changing the machine.
It migrates an existing official installation to the fixed release `v0.2.0`; it is not a first-install
guide. If JewelryDesignCodex is not installed, stop and follow [INSTALL.md](INSTALL.md).

## Safety rules

- Continue only in local Codex Desktop on macOS or native Windows.
- Use the Codex Desktop-bundled CLI and inspect JSON state before every mutation.
- Accept only marketplace `jewelry-design-codex` from `yuyou-dev/JewelryDesignCodex`. A same-name
  marketplace from any other source is a conflict: stop without changing it.
- Do not edit Codex configuration or marketplace files by hand. Do not read or copy credentials.
- Preserve conversations, design-task folders, generated images, and enabled optional
  JewelryDesignCodex plugins.
- Never run an updater fetched from `main`. Clone the exact `v0.2.0` tag and run its bundled script.

## 1. Inspect the existing installation

Resolve the bundled Codex CLI as described in [INSTALL.md](INSTALL.md#1-confirm-the-host), then run:

```text
"<CODEX_BIN>" --version
"<CODEX_BIN>" login status
"<CODEX_BIN>" plugin marketplace list --json
"<CODEX_BIN>" plugin list --available --json
```

Confirm the official source, record the installed core version, and record which of these plugin IDs
are installed and enabled:

- `svt-jewelry-design@jewelry-design-codex`
- `svt-jewelry-video@jewelry-design-codex`
- `svt-jewelry-feishu@jewelry-design-codex`

If the core plugin is absent, use the installation Runbook instead. If already at `0.2.0`, still run
the updater: it performs an idempotent verification without replacing the fixed ref.

## 2. Check runtimes

Require Git 2.30+, Node.js 20+, a logged-in Codex CLI, and GitHub network access. If a runtime is
missing, follow the platform-specific, approval-gated installation branch in INSTALL.md. Never
silently install system software or request administrator privileges.

## 3. Clone the exact updater

Create a new temporary directory and clone only the signed release target. Do not reuse a project
folder or an existing checkout.

macOS:

```text
UPDATE_ROOT="$(mktemp -d -t jewelry-design-codex-update)"
git clone --depth 1 --branch v0.2.0 https://github.com/yuyou-dev/JewelryDesignCodex.git "$UPDATE_ROOT"
git -C "$UPDATE_ROOT" describe --tags --exact-match
```

Windows PowerShell:

```text
$UPDATE_ROOT = Join-Path ([System.IO.Path]::GetTempPath()) ("jewelry-design-codex-update-" + [guid]::NewGuid())
git clone --depth 1 --branch v0.2.0 https://github.com/yuyou-dev/JewelryDesignCodex.git $UPDATE_ROOT
git -C $UPDATE_ROOT describe --tags --exact-match
```

Continue only when the exact tag is `v0.2.0` and the checkout's `package.json` version is `0.2.0`.

## 4. Run the transactional update

Pass the resolved bundled CLI to the target-version updater without changing global PATH.

macOS:

```text
JDC_CODEX_BIN="<CODEX_BIN>" node "$UPDATE_ROOT/scripts/jdc.mjs" update --json
```

Windows PowerShell:

```text
$env:JDC_CODEX_BIN = "<CODEX_BIN>"
node "$UPDATE_ROOT\scripts\jdc.mjs" update --json
```

The JSON result must expose `fromVersion`, `toVersion`, `migration`, `restoredPlugins`, and
`rolledBack`. A normal migration removes the old fixed-ref marketplace, adds the official
marketplace at `v0.2.0`, and restores the recorded core and optional plugins. It never deletes user
work. If any replacement step fails, the updater attempts to restore the previous release ref and
plugin set, returns `blocked`, and reports whether rollback was verified.

Do not improvise additional marketplace commands after a `blocked` result. Report its action list,
reason, and rollback state, then use [Troubleshooting](docs/TROUBLESHOOTING.md).

## 5. Verify the new installation

Run the doctor from the same exact checkout and re-read Codex state:

```text
node "<UPDATE_ROOT>/scripts/jdc.mjs" doctor --json
"<CODEX_BIN>" plugin marketplace list --json
"<CODEX_BIN>" plugin list --available --json
"<CODEX_BIN>" mcp get svt_jewelry_ui --json
```

Confirm the core plugin is installed and enabled at `0.2.0`, every previously enabled optional
plugin was restored, and doctor is `ready` or `restart_required`. Optional plugins not previously
enabled must remain disabled.

Delete only the temporary checkout after verification. Never delete user projects, conversations,
briefs, or generated images.

## 6. Restart and hand off

Tell the user to fully quit and reopen Codex Desktop, then start a **new task**. Existing tasks do not
hot-load updated Skills or MCP tools. In the new task, verify a jewelry form opens and reaches a
submitted or explicit error state; a permanent loading view is not success.
