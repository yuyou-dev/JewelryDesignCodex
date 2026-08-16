# Support

JewelryDesignCodex is a community open-source project. Support is provided through the [GitHub issue tracker](https://github.com/yuyou-dev/JewelryDesignCodex/issues); response times are not guaranteed.

## Before opening an issue

1. Update to the latest tagged release.
2. Read [Troubleshooting](TROUBLESHOOTING.md).
3. Run `node <marketplace-root>/scripts/jdc.mjs doctor --json`.
4. Reproduce in a new task after a full Codex restart.
5. Remove credentials, private designs, personal names, account identifiers, thread URLs, and absolute personal paths from all evidence.

## Include in a bug report

- JewelryDesignCodex release and plugin version.
- Codex Desktop and Codex CLI versions.
- macOS or Windows version and CPU architecture.
- The workflow and exact expected/observed terminal state.
- Sanitized doctor JSON and the smallest safe reproduction.
- For Apps UI: resource URI, viewport size, display scale, light/dark theme, and a sanitized screenshot.
- For provider failures: the error class and exit status, not auth material.

## Supported questions

- installation, update, uninstall, and marketplace conflicts;
- local MCP and Apps UI rendering;
- core Skills, prompt compilation, and task-scoped Image-2 runner behavior;
- macOS and native Windows portability;
- accessibility, privacy, documentation, and contribution questions.

## Outside core support

- ChatGPT web, Codex Cloud, Linux, WSL, Wine, and unofficial Codex builds;
- account billing, provider quotas, or gpt-image-2 access decisions;
- custom forks or modified branded distributions;
- third-party video or Feishu outages and account authorization;
- recovery of deleted user workspaces or media; and
- professional manufacturing, gemological, legal, or commercial advice.

Optional integrations may accept useful compatibility fixes, but their availability does not determine core plugin readiness.

Use GitHub's private [security advisory form](https://github.com/yuyou-dev/JewelryDesignCodex/security/advisories/new) for vulnerabilities. Do not post unpatched security issues publicly.
