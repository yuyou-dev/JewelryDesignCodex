# AGENTS.md

## Repository role

This repository is the public Git marketplace for JewelryDesignCodex. It packages the installable
`svt-jewelry-design` plugin and optional provider integrations. The default plugin must remain usable
from its installed cache without a sibling source repository.

## Working contract

1. Keep the public interfaces small: marketplace installation, `scripts/jdc.mjs`, the plugin manifest,
   stdio MCP, and versioned `ui://` resources.
2. Do not add credentials, generated jewelry, user references, Codex task links, local absolute paths,
   private repository URLs, or copied plugin caches.
3. Core installation must not expose a Skill whose executable dependency is absent. External video
   and Feishu capabilities belong in their optional plugins and must report their own auth state.
4. Preserve macOS and native Windows behavior. Do not add a POSIX-only launcher, `sips`, ImageMagick,
   or an implicit npm/pip install to the core runtime.
5. Breaking MCP Apps UI changes require a new versioned `ui://` resource URI.
6. Keep `v0.2.0` release metadata aligned across the root package, marketplace, and plugin manifests.

## Documentation routing

- Installation behavior: `INSTALL.md`
- Runtime and data flow: `docs/ARCHITECTURE.md`
- Failure recovery: `docs/TROUBLESHOOTING.md`
- Branding rights: `TRADEMARKS.md`
- Security reports: `SECURITY.md`

## Verification

Run `npm test`, then run the Python test suite under `plugins/svt-jewelry-design/tests`. Before a
release, run the doctor from the checked-out repository and install the tagged Git marketplace into a
fresh Codex profile. A stdio test does not replace a new-task Apps UI smoke test.
