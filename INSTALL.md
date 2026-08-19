# JewelryDesignCodex Installation Runbook

This runbook is written for Codex. Follow it for a first installation, verification, or removal. An existing installation must use [UPDATE.md](UPDATE.md).

The desired end state is observable: the `svt-jewelry-design@jewelry-design-codex` plugin is installed and enabled, the `svt_jewelry_ui` MCP is registered, the repository doctor reports a non-blocked state, and the user knows that a full Codex restart plus a new task is required.

## Guardrails

- Work only in a local Codex Desktop environment. If the host is ChatGPT on the web, Codex Cloud, a remote task, or another environment that cannot modify the user's local Codex configuration, stop and explain that local installation must be initiated from Codex Desktop.
- Use the Codex Desktop-bundled CLI where available. A PATH-resolved `codex` is acceptable only when it supports the required `plugin` commands and identifies as the same/current desktop generation.
- Run read-only discovery before each mutation. Treat an already-correct installation as success.
- Ask for approval before installing or upgrading system software, changing a proxy, opening a browser for authentication, or using administrator privileges. Never bypass host approval controls.
- Execute explicit commands. Do not pipe downloaded content into a shell and do not request, print, copy, or inspect credentials.
- Do not edit `config.toml`, installed plugin cache files, or marketplace state by hand. Use Codex CLI lifecycle commands.
- Preserve user projects and generated jewelry assets during update and uninstall.

## 1. Confirm the host

Confirm all of the following:

1. The user is interacting with the local Codex Desktop app.
2. Local command execution and the user's Codex configuration are available.
3. The operating system is macOS or native Windows.

If any condition fails, stop. Link the user to [platform support](docs/SUPPORT.md) and do not attempt a partial install.

## 2. Resolve the Codex CLI

First run `codex --version` and `codex plugin --help` without changing state.

Use the PATH command when both commands succeed and `plugin marketplace` plus `plugin add` appear in help. Otherwise resolve the executable bundled with the running Codex Desktop installation:

- On macOS, check the running app bundle's `Contents/Resources/codex` executable. Check the system Applications folder and the user's Applications folder only; do not scan unrelated directories.
- On Windows, obtain the running Codex Desktop executable path and look for `codex.exe` inside that installation package's resources. Do not perform a drive-wide search.

Store the resolved executable as an argument vector for subsequent commands. Quote it as one path; paths may contain spaces or non-ASCII characters. Do not replace or relink the user's global `codex` command.

When the selected executable is not the PATH-resolved `codex`, set `JDC_CODEX_BIN` to that absolute executable path only for lifecycle-script child processes. Likewise, if prerequisite discovery selects a Python executable outside PATH, pass its absolute path as `JDC_PYTHON_BIN`. Do not persist either override in unrelated shell or user configuration.

Completion criterion: the chosen executable successfully runs both `--version` and `plugin marketplace --help`.

If no compatible executable exists, ask the user to update or reinstall Codex Desktop, then stop with a blocked result.

## 3. Check prerequisites

Run read-only checks for:

- Git 2.30 or newer.
- Node.js 20 or newer.
- Python 3.10 or newer.
- An active Codex login, using the CLI's own status/doctor output; do not inspect login files.
- HTTPS access to GitHub.

The core plugin uses Node and Python standard-library tooling and does not require `npm install`, `pip install`, ImageMagick, or a separately configured API key.

If Git, Node, or Python is missing or too old, report the exact failed check and the platform-standard installation option. Ask for approval before installing it. After any approved installation, rerun all checks from a fresh shell. A system dependency is complete only when its version command succeeds.

Use these deterministic platform branches; do not improvise another package source:

### macOS dependency branch

1. Check `brew --version`.
2. If Homebrew is already installed, show the exact changes and ask for approval, then install only the missing packages:

   ```text
   brew install git node@20 python@3.12
   ```

   Do not reinstall packages whose version checks already pass. When Homebrew keeps `node@20`
   keg-only, use `<brew-prefix>/opt/node@20/bin/node` for this installation run rather than editing
   the user's shell profile.
3. If Homebrew is absent, do not install it with a downloaded shell script. Stop and ask the user
   to install the missing signed packages from their official sources: Apple Command Line Tools for
   Git, the Node.js 20 LTS macOS installer from `nodejs.org`, and the Python 3.12 universal installer
   from `python.org`. Resume only after the user confirms those installers completed.
4. Open a fresh shell and verify `git --version`, `node --version`, and `python3 --version` again.

### native Windows dependency branch

1. Check `winget --version` in PowerShell.
2. If `winget` is available, show the exact changes and ask for approval, then install only missing
   dependencies with the official package IDs:

   ```text
   winget install --exact --id Git.Git
   winget install --exact --id OpenJS.NodeJS.LTS
   winget install --exact --id Python.Python.3.12
   ```

   Never add unattended acceptance or administrator flags unless the host approval UI presents and
   the user approves them.
3. If `winget` is absent, stop and ask the user to install the signed Git for Windows, Node.js 20
   LTS, and Python 3.12 installers from `git-scm.com`, `nodejs.org`, and `python.org`. Do not download
   an executable from an unofficial mirror.
4. Open a new PowerShell session and verify `git --version`, `node --version`, and `py -3.12
   --version` (or the selected `python.exe --version`) before continuing.

If any installer requests elevation, leave that decision to the user. A refusal leaves the run in
`blocked`; it is not permission to use another installation mechanism.

## 4. Inspect existing state

Run these through the resolved Codex CLI:

```text
codex plugin marketplace list --json
codex plugin list --available --json
```

Interpret the JSON rather than matching human-formatted output.

- If marketplace `jewelry-design-codex` already points to the official `yuyou-dev/JewelryDesignCodex` Git source, keep it.
- If that name exists with another source, stop and show the conflicting source. Do not remove or overwrite it without explicit user approval.
- If the plugin is already installed and enabled from the correct marketplace, continue to doctor instead of reinstalling.
- If the plugin ID exists from a different marketplace, do not silently replace it. Report the conflict and ask whether the user wants the old source removed.

## 5. Add the marketplace

When the official marketplace is absent, run:

```text
codex plugin marketplace add yuyou-dev/JewelryDesignCodex --ref v0.2.0 --json
```

Then rerun `codex plugin marketplace list --json`. Continue only when one entry has:

- name: `jewelry-design-codex`
- source type: Git
- source repository: `yuyou-dev/JewelryDesignCodex` or its canonical GitHub URL

Do not continue merely because the add command exited successfully.

## 6. Bootstrap and install

Read the `root` for marketplace `jewelry-design-codex` from the marketplace-list JSON. Resolve the lifecycle script as `<root>/scripts/jdc.mjs`; ensure the resolved path remains inside that marketplace root.

Run:

```text
node <marketplace-root>/scripts/jdc.mjs bootstrap --json
```

Bootstrap is idempotent. It checks local prerequisites and packaged files; it must not print secrets or generate an image. If it reports a required system change, obtain approval, make only that change through the platform-standard package channel, and rerun bootstrap.

When bootstrap is non-blocked and the core plugin is not already installed, run:

```text
codex plugin add svt-jewelry-design@jewelry-design-codex --json
```

Rerun `codex plugin list --available --json`. Continue only when the exact plugin ID is installed and enabled.

## 7. Verify with doctor

Run:

```text
node <marketplace-root>/scripts/jdc.mjs doctor --json
codex mcp get svt_jewelry_ui --json
```

Doctor returns one of these top-level states:

- `ready`: installation and the running host are ready.
- `restart_required`: files and configuration are correct, but the current Codex process has not loaded them.
- `blocked`: one or more required checks failed.

Treat `ready` and `restart_required` as a successful installation only when the plugin-list check and MCP check also succeed. For `blocked`, present each failed check and follow its recovery instruction; do not claim success.

Do not run a real image generation as part of doctor. Provider readiness is confirmed later in a user-owned design task.

## 8. Restart and hand off

Tell the user that plugins and MCP tools do not hot-load reliably into the task that installed them. Ask the user to fully quit and reopen Codex Desktop.

After restart, create or guide the user to create a **new task** with this starter prompt:

```text
我想设计一款蓝宝石戒指，请先用可视化表单帮我补全设计方向。
```

In the new task, verify that the jewelry follow-up form renders and reaches a submitted or explicit error state. A permanent loading screen is not a pass. Real gpt-image-2 generation remains subject to the user's Codex account and provider access.

## Optional extensions

The core installation is complete without video or Feishu.

Only install an optional extension when the user asks for that capability. Inspect `codex plugin list --available --json`, then install the selected extension:

```text
# Optional video planning and Dreamina/Seedance submission
codex plugin add svt-jewelry-video@jewelry-design-codex --json

# Optional Feishu delivery
codex plugin add svt-jewelry-feishu@jewelry-design-codex --json
```

Follow the installed extension's own authentication instructions and report its readiness separately. The video plugin does not bundle the Dreamina CLI, account, or credits. The Feishu plugin does not bundle `lark-cli`, an app, or account credentials. Never downgrade core readiness because an unrequested optional provider is absent.

## Maintenance

### Update

Do not maintain a second update procedure here. Read the permanent [UPDATE.md](UPDATE.md) Runbook,
which clones the exact target release, preserves enabled optional plugins, performs the fixed-ref
migration, verifies rollback on failure, and requires a full Codex restart plus a new task.

### Uninstall

Show the target before removal. With user approval, run:

```text
node <marketplace-root>/scripts/jdc.mjs uninstall --json
```

The lifecycle uninstall removes the core plugin idempotently. Verify plugin-list JSON afterward; if the core remains installed, report the failed lifecycle action rather than issuing an unexamined duplicate removal. Remove optional JewelryDesignCodex plugins the user explicitly selects. Remove marketplace `jewelry-design-codex` only when no installed plugin still uses it and the user requests source removal:

```text
codex plugin marketplace remove jewelry-design-codex --json
```

Do not delete design-task workspaces, generated media, user prompts, or unrelated Codex configuration.

### Recovery

Use [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for a failed branch. Recovery is complete only after marketplace source, plugin state, doctor, MCP registration, restart, and new-task UI have all been rechecked.
