# Security Policy

## Supported versions

Security fixes are provided for the latest tagged release. During the `0.x` series, users should update to the newest `0.x` release before reporting a problem already fixed there.

| Version | Supported |
| --- | :---: |
| Latest tagged release | Yes |
| Older releases and source snapshots | No |

## Report a vulnerability

Use GitHub's private [Report a vulnerability](https://github.com/yuyou-dev/JewelryDesignCodex/security/advisories/new) form. Include:

- affected release and operating system;
- whether the issue is in the installer, Skill, local MCP, Apps UI, or provider runner;
- minimal reproduction steps and impact;
- logs with tokens, account identifiers, local user names, design assets, and private paths removed; and
- any proposed mitigation.

Do not open a public issue for an unpatched vulnerability. Do not include Codex authentication files, API keys, Feishu credentials, provider tokens, or private jewelry designs in a report.

Maintainers will acknowledge reports when project availability permits, validate the affected surface, and coordinate a disclosure after a fix is available. This community project does not promise a fixed response-time SLA.

## Security boundaries

- The core plugin runs locally and invokes the user's Codex installation. It does not provide a hosted account service.
- Real image generation sends only task-selected prompt and reference material through the user's configured Codex/OpenAI route.
- Optional video and Feishu integrations have separate authentication and provider policies. They are not prerequisites for the core plugin.
- `doctor` reports health without reading or printing secrets and does not submit a generation request.
- Installation and maintenance use Codex plugin commands. The project does not ask users to pipe remote scripts into a shell.

See [Architecture](docs/ARCHITECTURE.md) for the data flow and [Support](docs/SUPPORT.md) for non-security reports.
