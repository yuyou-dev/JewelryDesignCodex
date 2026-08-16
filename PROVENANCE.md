# Source and Asset Provenance

JewelryDesignCodex is published by 苏哇科技 under Apache-2.0, except for the brand treatment
described in `TRADEMARKS.md` and any separately identified third-party component.

## Project code

The core Skills, local MCP Apps UI, Image-2 task runner, remix compiler, visual workbench, and package
tests were developed for this project and exported into this public repository as a clean source
snapshot. Private Git history, credentials, user tasks, generated customer media, caches, absolute
machine paths, and conversation links are not part of the distribution.

## Brand assets

The files under `plugins/svt-jewelry-design/assets/brand/` and the plugin icon are original 苏哇科技
brand assets. They may be redistributed with unmodified official copies of JewelryDesignCodex.
Apache-2.0 does not grant permission to imply endorsement or publish a modified fork as an official
苏哇科技 product; see `TRADEMARKS.md`.

## Runtime dependencies

The core plugin uses Node.js built-in modules and Python's standard library. It does not bundle
Codex credentials, API keys, provider accounts, or customer assets. gpt-image-2 runs through the
user's own Codex installation and authorization.

The optional video and Feishu plugins contain workflow instructions only. Dreamina and `lark-cli`
are separate products, are not bundled, and require their own installation, terms, accounts, and
authorization. Their names identify compatibility and do not imply redistribution or endorsement.

The core MCP vendors `jpeg-js` 0.4.4 for portable PNG/JPEG preview processing. Its upstream identity,
license, and embedded third-party notices are recorded in `NOTICE` and retained with the vendored
source. Any additional vendored library or media-processing binary must receive the same treatment
before publication.
