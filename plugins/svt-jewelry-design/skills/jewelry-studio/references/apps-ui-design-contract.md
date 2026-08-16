# Apps UI Design Contract

Use this contract for every project-owned inline MCP App in Codex or another chat host. It governs
form, comparison, gallery, and media interaction design. Workflow semantics remain in
`references/conversation-ui-contract.md`; MCP protocol fields remain in the server implementation.

## Host-aware composition

1. Design the component as content inside the host's existing frame. Do not draw a second outer
   card, shadow, decorative shell, or oversized header. Set `prefersBorder: false` when the host
   frame is sufficient.
2. Start in inline mode and use the smallest presentation that supports the task. Fullscreen is for
   detailed inspection or editing, not a default escape from layout pressure.
3. Use system typography, host color tokens where available, compact spacing, light/dark support,
   and one clear visual hierarchy. Do not add decorative scores, rankings, badges, or recommendations
   that the workflow did not produce.
4. Keep metadata concise: title, at most three lines of summary, optional use case, and at most one
   primary CTA for the active item.
5. Keep ordinary body and metadata text at a readable 12–13px baseline, supporting text no smaller
   than 11px, and compact headings around 17–19px. Respect host text resizing and preserve WCAG AA
   contrast; compact must not mean illegible.

## Brand identity

1. The product brand is `苏哇科技`. Let the host-owned tool header carry the persistent app name
   and icon. Do not repeat a persistent logo, oversized wordmark, or branded header inside the
   component body.
2. In the distributable plugin, keep the canonical files under `assets/brand/`: `logo-static.png`
   for the plugin/composer identity, `logo-header.webp` for compact transitional states, and
   `logo-loading.webp` for media-loading states. UI resources embed these local files at serve time;
   they must not depend on the original source folder or an undeclared remote asset domain.
3. Animated identity is functional feedback, not decoration. Show it only while real content is
   loading, replace it with content or a concise error state, and provide a static fallback under
   `prefers-reduced-motion: reduce`.
4. Treat standard `isError` results, Codex single-text JSON wrappers, incomplete structured results,
   and empty preview collections as terminal error states. Hide loading immediately and show a
   concise, model-consistent error; never wait forever for media that the tool did not return.
5. Use system colors for text, dividers, and surfaces. Primary submit/continue actions and selected
   form choices use a restrained black background with white text in both light and dark modes. The
   Suwa gold may accent a focus ring or small status detail; it must not recolor the whole canvas or
   reduce WCAG AA contrast. Do not ship unrelated brand banners in inline Apps.

## Height and scrolling

1. No nested vertical scrolling is allowed in an inline App. The host conversation owns vertical
   navigation. Set document-level vertical overflow to hidden and prevent overscroll chaining.
2. Observe the rendered `main` element and report its actual bounding-box height through
   `ui/notifications/size-changed`. Do not use document scroll height as the requested iframe size.
3. Use a bounded responsive media stage with explicit minimum and maximum heights. Gallery and
   comparison stages should normally occupy about 400–560px on desktop and 440–500px on narrow
   layouts. Do not let an unconstrained aspect ratio turn container width into excessive card
   height, and never trade the host's scroll ownership for a taller inner document.
4. Preserve host scrolling over interactive media: use `touch-action: pan-y` for horizontal
   before/after gestures. Never cover the principal surface with `touch-action: none`.

## Forms

1. Render only unresolved decisions. Use one compact, self-contained page and no more than four
   ordinary clarification fields; a dedicated workflow intake may group more fields when each is necessary.
2. Make ordinary forms density-adaptive instead of shrinking text or clipping content. One or two
   light fields may use choice cards. Three or four non-visual fields use compact selects or
   horizontally scrolling multi-choice pills, while keeping one visible primary submit action in
   the same page. Do not turn an inline form into tabs, a wizard, or another deep navigation flow.
3. Group related controls side by side on desktop. Ordinary forms reflow to one column at 360px and
   below instead of hiding overflow or clipping controls. A dedicated intake with many
   already-defaulted choices may retain compact split groups and use a one-open-at-a-time accordion
   at 360px and below so every field remains reachable without nested scrolling; keep selected
   values in form state while a section is collapsed. Textareas do not resize inside the iframe.
4. A generic form may contain at most one visual-choice field. Present its two to eight image choices
   in one bounded horizontal image rail with square, undistorted thumbnails, readable alt text, and
   no vertical expansion by item count. Keep preview bytes in UI-only `_meta.formMedia` under one
   shared budget; model-visible structured content retains only stable field and option ids.
5. Use stable field ids, localized labels, a visible Other path when needed, and a readable summary
   plus stable JSON in `ui/message`. File upload belongs to the host attachment flow, not the form.

## Comparisons and galleries

1. A comparison always uses real source and result media. The slider state is ephemeral and does
   not approve, rank, regenerate, or mutate an image.
2. For multiple retouch pairs, use a vertical pair rail. For similar candidates or ordinary design
   outputs, use a vertical candidate rail beside the active media. Rail thumbnails are fixed squares
   with `object-fit: cover`; use one 68px column for up to five items and a 58px two-column rail for
   six to twelve so every item stays visible without an inner scrollbar. At narrow widths, use 60px
   and 52px respectively. Poster output may keep its real portrait ratio in the principal stage,
   but its navigation thumbnail remains a compact square.
   Do not place a horizontal thumbnail strip below the media and grow the card vertically.
3. Keep every touch target at least 44px high or wide. Support pointer, touch, and keyboard use;
   every hidden input, thumbnail, slider, and CTA must have a visible `:focus-visible` state.
4. On narrow screens, compact metadata may overlay the media, but it must not cover candidate
   navigation, the comparison handle, labels, or the primary action.
5. Selection records one neutral `jewelryAssetSelection` context containing the stable `assetId`,
   its `sourceWorkflow`, and an optional factual role such as retouch `after`. Prefer
   `ui/update-model-context` so the next user-authored message decides the new workflow; use
   `ui/message` only as a compatibility fallback. Never preset retouch, remix, poster, catalog,
   display, video, or any other next action, and never include absolute paths in the selection.
6. Before/after comparisons preserve reading order: source or pre-retouch media is on the left and
   result or post-retouch media is on the right. Labels, clipping direction, and accessible text
   must agree with the pixels shown.

## Visual editing workbenches

1. Use the shared canvas-first shell selected for this project: a compact square asset rail on the
   left, the principal canvas in the center, a floating bottom tool dock, and a contextual settings
   drawer on the right. Keep chrome monochrome; reserve Suwa gold for focus, anchors, and small
   status accents. Primary commit actions remain black with white text.
2. Inline mode is a preview-capable editor and must preserve host vertical scrolling with
   `touch-action: pan-y`. Request fullscreen for detailed drawing or placement; only the fullscreen
   canvas may use `touch-action: none`. Never create a nested vertical scrollbar in either mode.
3. The local redraw workbench supports three explicit intents: marked local change, put-it-here
   placement, and sketch-to-jewelry. Drawing, anchors, overlays, and rough cutout edges encode
   spatial intent only. They are not literal jewelry material, line width, finish, or final shadow.
   Sketch-to-jewelry may open a clean white canvas with no source attachment. In that state, keep
   drawing and save enabled, omit the source asset tile/path, and use the saved composite as the
   complete geometry reference. Marked local change and put-it-here still require a real source.
4. The try-on workbench uses one model base plus one locally prepared jewelry overlay. Let users
   drag, scale, and rotate it, and optionally pair earrings. The saved composite is an approximate
   placement constraint; the original jewelry and model images remain the identity sources.
5. Basic cutout stays browser-local and self-contained: estimate a simple background, then allow
   keep/remove brush corrections. Remove only background regions connected to an image boundary;
   show the real transparent and white-background previews. A gemstone-assisted sketch must confirm
   the cutout before placement or drawing. Do not claim production-grade alpha, upload the source
   to an extra provider, or add a heavy canvas framework for this v1.
6. In marked-edit and put-it-here modes, every completed anchor or painted region creates one stable
   annotation and immediately focuses its own instruction field. Canvas marker, instruction editor,
   delete action, and saved annotation id stay synchronized. Sketch strokes are geometry and never
   open per-stroke instruction fields.
7. A commit saves one stable task-local draft under `artifacts/runs/<task-id>/visual-workbench/` and
   sends only its stable id/workspace-relative path back to the conversation. Never include an
   absolute path in the follow-up message. The App does not generate, approve, rank, or pick a next workflow.
8. Persist paths and state in model-readable structured data, but keep preview bytes in `_meta`.
   Bound composite/cutout payloads, show terminal errors instead of infinite loading, and keep the
   resource URI versioned when the bridge or draft schema changes.

## Media and fallback

1. Keep paths and model-readable metadata in `structuredContent`. Put compact preview bytes only in
   UI-only `_meta`; do not duplicate Base64 in model-visible content or repeat a shared source per
   candidate.
2. A successful specialized App is the final visual presentation, so do not repeat the same media
   inline afterward. When the tool is unavailable, returns `isError`, or lacks a required output,
   show every real successful asset inline and report missing items.
3. Treat each `ui://` resource as a cache key. Any breaking layout, bridge, payload, or behavior
   change requires a versioned URI and a plugin cachebuster update.

## Acceptance gate

Before release, verify all applicable surfaces with real media and both direct tool results and the
host's wrapped-result shape:

- 4-way, 8-way, and 10–12-way galleries at a 1280×720 desktop viewport;
- single and 1–8 pair retouch comparisons plus poster/catalog/display/grid/grid-redraw/reference-sheet galleries;
- local redraw for blank canvas, pure sketch, gemstone-plus-sketch, put-it-here, and marked-edit modes;
- try-on placement for ring, bracelet, necklace, pendant, earrings, and brooch;
- the narrowest supported 320×700 viewport;
- no vertical or horizontal document overflow;
- host vertical touch scrolling plus horizontal comparison dragging;
- keyboard focus, candidate switching, slider use, CTA submission, loading, and fallback;
- light/dark compatibility and readable alt text/labels;
- automated MCP/resource/contract tests followed by manual host acceptance in a fresh task after
  plugin installation or restart.

Screenshots are evidence, not the acceptance gate by themselves. Record measured dimensions and
overflow state, and do not declare a UI release complete before manual host acceptance.
