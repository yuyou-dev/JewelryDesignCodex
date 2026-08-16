# Suwa Technology brand assets

Canonical plugin identity for `苏哇科技`:

- `logo-static.png`: persistent plugin/composer icon.
- `logo-header.webp`: compact animated transition mark.
- `logo-loading.webp`: animated media-loading mark.

The MCP server embeds animated files into versioned, self-contained UI resources at serve time.
Components hide them after real content resolves and fall back to `logo-static.png` when the user
prefers reduced motion. Do not load these files from their original design-source directory or a
remote CDN.

`toy-banner.jpg` from the source brand folder is intentionally not shipped. It is decorative banner
art rather than inline App identity and would conflict with the host's minimal, content-first frame.
