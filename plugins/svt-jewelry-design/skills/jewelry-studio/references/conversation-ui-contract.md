# Conversation UI Contract

Use this contract when a designer-facing jewelry workflow needs clarification or presents generated
media in Codex or another MCP Apps host.

Before creating or changing a project-owned UI resource, read and follow
`references/apps-ui-design-contract.md`. That design contract is the normative source for host-aware
composition, responsive layout, scrolling, accessibility, media presentation, and UI acceptance.

## Clarification decision

1. Ask only when the missing answer changes the workflow or the identity of the requested product.
   Typical examples are jewelry type, preservation versus redesign, a required source reference, or
   an output family such as still images versus video.
2. Do not ask about choices that can be handled with a tasteful, reversible default. State the
   assumption briefly and continue.
3. Do not turn delivery count, batch size, provider cost, or internal job selection into an ordinary
   clarification form. Counted requests remain committed delivery counts unless the user explicitly
   asks for a shortlist or staged approval.
4. For ordinary partial ambiguity, ask at most one consolidated clarification round before
   execution. A later question is justified only by new evidence, a provider blocker, or an
   irreversible choice that could not have been known earlier.

`$jewelry-grill-me` is the narrow multi-round exception. Enter it only when the user explicitly asks
for Grill Me 珠宝 or a deeper guided interview, or when the request and attachments reveal no
usable workflow, product identity, or output family. Complete four discovery rounds—foundation,
meaning, design language, then variation and delivery—before a separate confirmation round, and ask no more than four unresolved fields per round. Summarize established answers after each submission,
and never ask a resolved field again. A known fact moves that stage to a deeper decision rather than
removing the stage. Grill Me may ask `delivery_count` once when no count is known, using 1, 2, 4, 8,
or a custom value; this narrow exception defines the desired visual exploration and does not permit
provider, cost, concurrency, or internal batch questions. Present one shared brief with locked facts,
flexible axes, and visibly separated candidate branches, then obtain explicit confirmation before
execution. Do not start provider work during Grill Me.

A known workflow with missing fields remains ordinary clarification. For example, “开启随手画”
with no jewelry category gets one dynamic form and must not silently default to a ring, pendant, or
brooch. A clear request such as “设计五款蓝宝石戒指” or “我想设计一款蓝宝石戒指” already
establishes workflow and product identity, so it executes without a mandatory form and labels only
reversible creative assumptions.

The dedicated jewelry-remix intake has one narrow exception: after the user explicitly starts the
“爆款二创” workflow, 4 versus 8 is a product-mode choice. It is not a provider-cost or batch-size
question and does not relax the counted-delivery rule. Do not ask again when the user already chose 4 or 8.

## Apps UI capability resolution

When a workflow requires a structured interaction or a registered visual presentation, resolve the
required Apps UI surface before emitting a prose or inline-media fallback. Absence from the initial
visible tool list does not mean that the surface is unavailable: Codex may defer MCP tools until they
are selected. Use this sequence:

1. If the required tool is already callable, call it.
2. Otherwise, discover the exact registered tool name through the host's tool-search mechanism and
   call the discovered tool.
3. Use the documented fallback only when exact-name discovery confirms that the tool is absent, the
   host has no compatible UI capability, or an actual tool call returns an error.

This rule applies to all intake, editor, comparison, and Gallery surfaces in this contract. Do not
treat a prose answer as an equivalent successful presentation, and do not describe a tool as
unavailable merely because it was not exposed in the first tool catalog.

## Presentation priority

When clarification is necessary, use the richest interaction surface currently available:

1. The workflow's registered plugin MCP form or Apps UI tool, resolved as above.
2. Another real host-provided structured follow-up tool when the registered tool is absent.
3. A concise normal chat question when no structured tool is available.

Do not emit raw HTML, a fake JSON form, or prose that claims to be interactive. Skills can decide
when and what to ask, but a rendered form requires a host capability or an MCP tool with an attached
UI resource.

## Recommended jewelry form

Compose the form dynamically from the unresolved decisions; do not show fields already answered by
the user's words or attachments. Prefer no more than four fields in one card.

| Stable field id | Type | Use when unresolved | Typical options |
| --- | --- | --- | --- |
| `workflow_family` | single | Grill Me cannot infer the intended workflow | new design, remix, sketch, local edit, retouch, try-on, campaign |
| `jewelry_type` | single | Product identity is unknown | ring, necklace, earrings, bracelet, brooch, other |
| `starting_point` | single | Grill Me needs to establish the source of truth | text idea, product image, gemstone, sketch, selected result, model image |
| `delivery_count` | single | Grill Me has no explicit visual count | 1, 2, 4, 8, other custom count |
| `design_mode` | single | An attachment could mean preservation or inspiration | preserve, redesign, inspiration |
| `design_system` | single | Gold versus gem-set changes the design language | gold, gem-set |
| `style_direction` | single | Style changes the whole concept family | minimal, botanical, art_deco, oriental, other |
| `variation_axes` | multi | Grill Me will produce more than one image | silhouette, setting, motif, stone layout, negative space, material craft |
| `hero_material` | text | The focal stone/material is essential and absent | Free text with an example placeholder |
| `deliverables` | multi | The user asks for a campaign but not its output family | product still, model image, poster, video |
| `aspect_ratio` | single | A platform-specific output is required | 1:1, 3:4, 9:16, 16:9 |

Every off-list single or multi choice should offer an explicit localized `other` option when the
host supports it. Labels and submit text must use the user's language.

After submission, restate the selected answers in one short paragraph, record them in the active
task proposal/progress when a design task exists, and continue without asking the user to repeat the
same information. Ordinary clarification continues directly; Grill Me advances only the remaining
decision frontier and ends with explicit confirmation of the shared brief.

## MCP Apps implementation boundary

The `svt-jewelry-design` plugin exposes `ask_jewelry_followup_questions` through its
`svt_jewelry_ui` MCP server. Its tool input carries the title, prompt, submit label, and dynamic
field definitions. The tool accepts one to four unresolved fields and at most one visual-choice
field with two to eight preview options. It attaches `ui://svt-jewelry/followup-questions/v4.html` with
`_meta.ui.resourceUri`, serves `text/html;profile=mcp-app`, receives tool input through the MCP Apps
`ui/*` bridge, and submits a human-readable answer plus stable field ids through `ui/message`.
Three or four non-visual fields render with compact controls; one or two light fields may use choice
cards; visual options use one bounded horizontal rail. Preview bytes stay in `_meta.formMedia` under
one shared budget and never appear in model-visible `structuredContent`.
When the tool or UI host is unavailable, use its model-readable fallback or one concise chat
question instead of claiming that a form rendered.

The UI is a thin interaction layer. Design defaults, routing, task files, provider execution, and
delivery counts remain governed by the jewelry skills and repository contracts.

### Inline layout

No nested vertical scrolling is allowed inside an inline MCP App. Apply the sizing, touch,
accessibility, vertical candidate rail, and narrow-layout rules in
`references/apps-ui-design-contract.md`; do not redefine them per workflow.

### Retouch comparison

The plugin also exposes `show_jewelry_retouch_comparison` as a decoupled render tool linked to
`ui://svt-jewelry/retouch-comparison/v10.html`. Call it only after retouch execution has produced one
or more real local source/output pairs. Each pair uses a stable sequential id such as `RETOUCH-A`.
The server keeps paths plus labels in model-readable `structuredContent` and text fallback, and
supplies size-bounded previews through UI-only `_meta.comparisonMedia` under one shared payload
budget. The component accepts both a direct tool result and Codex's single-text JSON wrapper, uses a
vertical pair rail for multiple images, and must not assume that full-resolution MCP image blocks
survive host transport.

The slider position is ephemeral UI state. A comparison does not mutate either image, count as an
additional deliverable, approve the result, or authorize aesthetic revision. Its continue action
records the post-retouch asset as neutral context for the next user-authored instruction. Treat a non-error
comparison tool result as successful presentation because the server returns an error when it cannot
prepare every preview; do not repeat the compared images inline after success. Only when the tool is
unavailable or returns an error should the normal response show every real source/output pair inline.

### Jewelry remix intake and Gallery

The plugin exposes `ask_jewelry_remix_brief` with
`ui://svt-jewelry/remix-brief/v7.html`. Use it only for the dedicated source-image remix workflow.
It renders one compact, borderless intake and sends a readable answer plus stable JSON through
`ui/message`; it does not upload files or choose provider execution details.

Remix brief completeness is based on explicit user answers or a previously submitted Remix form,
not on preferences inferred from the source image. The required decision groups are 4/8 mode,
design system, the three change controls, and theme, morphology, style, and material/craft direction.
Image analysis may prefill editable choices and establish the source identity lock, but it cannot
turn an unanswered preference into a completed field. When any required group is unresolved, use
the dedicated intake; if its tool is deferred, discover it by exact name before using the concise
chat fallback. A fully explicit brief may skip the form.

After exactly 4 or 8 independent outputs exist, `show_jewelry_remix_gallery` attaches
`ui://svt-jewelry/remix-gallery/v7.html`. Its `structuredContent` contains only source/candidate
paths and metadata. UI-only `_meta.galleryMedia` carries one size-bounded source preview and one
preview per candidate under a shared payload budget. The component accepts both a direct tool result
and Codex's single-text JSON wrapper.

The Gallery navigates stable `REMIX-*` candidates and compares each against the same source with an
ephemeral slider. Choosing a candidate records neutral asset context but does not select or start
another workflow. A successful Gallery tool call is the final visual presentation: do not repeat the source and candidate images inline. If the tool is unavailable, returns an error, or delivery is
incomplete, show every successful real image inline and report the missing count.

### Poster, catalog, and display creation

For a dedicated jewelry poster, catalog, or product-display workflow, use
`ask_jewelry_creation_brief` with `ui://svt-jewelry/creation-brief/v4.html` only when an unresolved
choice changes the creative family. The form switches its compact fields by `poster`, `catalog`, or
`display`; it never uploads files and must not override an explicit delivery count. Catalog's core
five versus expanded seven profile is a workflow preset only when the user did not already specify
the requested slots.

After one to twelve real poster, catalog, display, grid, grid-redraw, reference-sheet, or model-try-on outputs
exist, call `show_jewelry_creation_gallery` with
`ui://svt-jewelry/creation-gallery/v6.html`. Its model-visible payload contains workflow, stable asset
ids, local paths, and concise metadata; preserve each caller-provided, workflow-prefixed id rather
than renumbering it by Gallery position. UI-only media carries bounded previews. The Gallery uses a
vertical asset rail and records the stable asset id plus source workflow as neutral context when the
designer chooses an output. It does not rank, approve, regenerate, preset a next workflow, or start
a follow-up job. On success, do not repeat the Gallery
images inline; on tool error or missing output, show every real successful image and state the gap.

### Local redraw and model try-on workbench

The plugin exposes `open_jewelry_local_editor` and `open_jewelry_tryon_editor` through one shared,
versioned `ui://svt-jewelry/visual-workbench/v6.html` resource. The first supports marked local
changes, put-it-here placement, and blank-canvas, pure, or gemstone-assisted sketch-to-jewelry.
Only blank-canvas `sketch_design` may omit `sourcePath`; the other two modes require it. The second supports
ring, bracelet, necklace, pendant, earrings, and brooch placement on a supplied model.

Copy every supplied input image into the active run workspace before calling either tool. Structured content
carries task-local paths and defaults; `_meta.visualWorkbenchMedia` carries only bounded previews.
The canvas may do basic browser-local background removal, keep/remove brush correction, drawing,
anchors, drag, scale, rotation, and paired-earring placement. These controls record approximate
spatial intent only; they are not a direct image-generation mask or a finished composite.
Marked-edit and put-it-here drafts use independent `ANCHOR-*` and `REGION-*` instructions. A
gemstone-assisted sketch confirms its cutout before drawing, while a blank or uploaded pure sketch
does not require cutout. Sketch-to-jewelry compiles four `SKETCH-A` through `SKETCH-D` outputs and
uses the ordinary design Gallery with `sourceWorkflow: sketch_design`; the other two modes remain
one-output comparison workflows.

On commit, the UI calls `save_jewelry_visual_draft`. The server writes the flattened composite,
optional cutout, and JSON state only under `artifacts/runs/<task-id>/visual-workbench/<draft-id>/`.
The follow-up message contains the stable draft id and workspace-relative draft path, never an
absolute path. The agent then resolves `<plugin-root>` as the installed plugin directory and compiles
the draft through `node "<plugin-root>/scripts/jdc.mjs" visual-workbench` plus the bundled Image-2
runner. If the UI or save call fails, use a concise textual spatial brief; never
claim a visual draft exists or leave the component in loading state.

### Ordinary jewelry design Gallery

After one to twelve real ordinary jewelry-design outputs exist, call
`show_jewelry_design_gallery` with `ui://svt-jewelry/design-gallery/v2.html`. This presentation is
for ordinary design sets, not retouch, remix, poster, catalog, or display workflows. Ordinary design
sets preserve each real runner job id exactly. Sketch-design sets instead expose the four logical
stable ids `SKETCH-A` through `SKETCH-D` while retaining each scoped runner output path. The model-visible payload
contains paths and concise facts, while UI-only `_meta.designMedia` carries bounded previews under
the shared media budget.

The Gallery uses a square vertical rail, keeps the active design at `object-fit: contain`, and records
the stable design id plus the active `sourceWorkflow` (`design` or `sketch_design`) as neutral context
when the designer chooses a款式.
The next user message is routed normally and may request any supported workflow. Choosing does not approve, rank,
regenerate, reduce a counted delivery, or start another job. A successful call is the final visual
presentation, so do not repeat the same images inline. If the tool is unavailable, returns an
error, lacks any completed item, or the requested set has more than twelve outputs, show every real
successful image inline and state any missing count. Never split or hide a larger counted delivery
merely to fit this v1 Gallery.

Every loading-capable Apps UI must consume both standard results and Codex single-text wrappers.
An explicit `isError`, incomplete result, or empty media set must replace loading with a concise
error state; it must never leave an animated loading identity on screen indefinitely.

Across all selectable result surfaces, use `ui/update-model-context` when the host advertises it.
The canonical structured payload is `jewelryAssetSelection` with `assetId`, `sourceWorkflow`, and an
optional factual `assetRole`; never include an absolute path. Fall back to one `ui/message` only for
hosts without model-context updates. Selection itself never dictates the next workflow.

## Media presentation

1. Show every delivered image inline before path-only metadata unless a successful specialized MCP
   App is the final visual presentation. In Codex desktop, use Markdown image syntax with an absolute
   local path when the runtime did not return a native image attachment.
2. Show every delivered video inline with the host's native video attachment when available. In
   Codex desktop, use the same Markdown media syntax with the absolute `.mp4` or `.mov` path.
3. Use one visible media item per deliverable. Do not hide a counted set behind a single contact
   sheet unless that combined output was requested.
4. For a small visually comparable set, a project-owned MCP App may render an inline carousel. Use
   fullscreen only for detailed inspection or editing and picture-in-picture only for ongoing video
   playback. The host controls the final size of ordinary Markdown media cards.
5. Never embed a path that does not exist or a provider URL that has not been returned.
