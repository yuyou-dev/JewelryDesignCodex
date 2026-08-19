import assert from "node:assert/strict";
import { realpathSync } from "node:fs";
import { mkdtemp, mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  handle,
  RESOURCE_MIME_TYPE,
  RESOURCE_REGISTRY,
  SERVER_VERSION,
  TOOL_REGISTRY,
} from "../mcp/server.mjs";

const EXPECTED_TOOL_NAMES = [
  "ask_jewelry_followup_questions",
  "show_jewelry_retouch_comparison",
  "ask_jewelry_remix_brief",
  "show_jewelry_remix_gallery",
  "ask_jewelry_creation_brief",
  "show_jewelry_creation_gallery",
  "show_jewelry_design_gallery",
  "open_jewelry_local_editor",
  "open_jewelry_tryon_editor",
  "save_jewelry_visual_draft",
];

const EXPECTED_RESOURCE_URIS = [
  "ui://svt-jewelry/followup-questions/v4.html",
  "ui://svt-jewelry/retouch-comparison/v10.html",
  "ui://svt-jewelry/remix-brief/v7.html",
  "ui://svt-jewelry/remix-gallery/v7.html",
  "ui://svt-jewelry/creation-brief/v4.html",
  "ui://svt-jewelry/creation-gallery/v6.html",
  "ui://svt-jewelry/design-gallery/v2.html",
  "ui://svt-jewelry/visual-workbench/v6.html",
];

const RESOURCE_URIS = new Set(RESOURCE_REGISTRY.map(({ uri }) => uri));
const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);
const COMPOSITE_DATA_URL = `data:image/png;base64,${PNG_BYTES.toString("base64")}`;

function toolEntry(name) {
  const entry = TOOL_REGISTRY.find(({ descriptor }) => descriptor.name === name);
  assert.ok(entry, `tool ${name} is not registered`);
  return entry;
}

function runTool(name, args) {
  return toolEntry(name).run(args);
}

function assertMcpSuccess(result) {
  assert.ok(result && typeof result === "object" && !Array.isArray(result));
  assert.equal(result.isError, undefined);
  assert.ok(Array.isArray(result.content), "content must be an array");
  assert.ok(result.content.length >= 1, "content must not be empty");
  for (const item of result.content) {
    assert.equal(item.type, "text");
    assert.equal(typeof item.text, "string");
    assert.ok(item.text.length > 0, "text content must not be empty");
  }
  assert.ok(
    result.structuredContent && typeof result.structuredContent === "object" && !Array.isArray(result.structuredContent),
    "structuredContent must be an object",
  );
  const template = result._meta?.["openai/outputTemplate"];
  if (template) assert.ok(RESOURCE_URIS.has(template), `outputTemplate ${template} must be a registered resource`);
  return result;
}

async function dispatch(message) {
  const writes = [];
  const original = process.stdout.write;
  process.stdout.write = (chunk) => {
    writes.push(String(chunk));
    return true;
  };
  try {
    await handle(message);
  } finally {
    process.stdout.write = original;
  }
  return writes.map((chunk) => JSON.parse(chunk));
}

async function dispatchOne(message) {
  const responses = await dispatch(message);
  assert.equal(responses.length, 1, "expected exactly one response");
  return responses[0];
}

const request = (id, method, params = {}) => ({ jsonrpc: "2.0", id, method, params });

async function makeTempRoot(t) {
  const root = await mkdtemp(join(tmpdir(), "svt-mcp-server-test-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  return root;
}

async function makeWorkspace(t) {
  const root = await makeTempRoot(t);
  const workspace = join(root, "artifacts", "runs", "test-task");
  await mkdir(workspace, { recursive: true });
  return { root, workspace };
}

async function writePng(directory, name) {
  const path = join(directory, name);
  await writeFile(path, PNG_BYTES);
  return path;
}

test("registers exactly ten jewelry tools with complete descriptors", () => {
  assert.equal(TOOL_REGISTRY.length, 10);
  assert.deepEqual(TOOL_REGISTRY.map(({ descriptor }) => descriptor.name), EXPECTED_TOOL_NAMES);
  for (const { descriptor, run } of TOOL_REGISTRY) {
    assert.equal(typeof run, "function", `${descriptor.name} must have a run handler`);
    assert.equal(typeof descriptor.title, "string");
    assert.ok(descriptor.title.length > 0, `${descriptor.name} must have a title`);
    assert.equal(typeof descriptor.description, "string");
    assert.ok(descriptor.description.length > 40, `${descriptor.name} must have a meaningful description`);
    assert.equal(typeof descriptor.annotations, "object", `${descriptor.name} must carry annotations`);
    assert.equal(descriptor.annotations.openWorldHint, false, `${descriptor.name} must stay closed-world`);
  }
});

test("gives every tool a legal object input schema", () => {
  for (const { descriptor } of TOOL_REGISTRY) {
    const schema = descriptor.inputSchema;
    assert.ok(schema && typeof schema === "object", `${descriptor.name} must define inputSchema`);
    assert.equal(schema.type, "object", `${descriptor.name} inputSchema.type must be object`);
    assert.ok(schema.properties && typeof schema.properties === "object", `${descriptor.name} must define properties`);
    for (const [key, value] of Object.entries(schema.properties)) {
      assert.ok(value && typeof value === "object", `${descriptor.name}.${key} must be a schema object`);
      assert.ok(
        value.type || value.oneOf || value.anyOf,
        `${descriptor.name}.${key} must declare a type or composition`,
      );
    }
    if (schema.required !== undefined) {
      assert.ok(Array.isArray(schema.required), `${descriptor.name} required must be an array`);
      for (const key of schema.required) {
        assert.ok(key in schema.properties, `${descriptor.name} required key ${key} must exist in properties`);
      }
    }
  }
  assert.deepEqual(toolEntry("save_jewelry_visual_draft").descriptor.inputSchema.required, [
    "workspacePath",
    "workflow",
    "state",
    "compositeDataUrl",
  ]);
});

test("registers eight ui resources with assembled branded HTML", () => {
  assert.equal(RESOURCE_REGISTRY.length, 8);
  assert.deepEqual(RESOURCE_REGISTRY.map(({ uri }) => uri), EXPECTED_RESOURCE_URIS);
  for (const resource of RESOURCE_REGISTRY) {
    assert.ok(resource.uri.startsWith("ui://svt-jewelry/"), `${resource.uri} must stay under ui://svt-jewelry/`);
    assert.equal(typeof resource.name, "string");
    assert.ok(resource.name.length > 0, `${resource.uri} must have a name`);
    assert.equal(typeof resource.description, "string");
    assert.ok(resource.description.length > 0, `${resource.uri} must have a description`);
    assert.equal(typeof resource.html, "string");
    assert.ok(resource.html.length > 1000, `${resource.uri} must resolve to non-trivial HTML`);
    assert.ok(resource.html.includes("<"), `${resource.uri} must resolve to HTML markup`);
    assert.doesNotMatch(
      resource.html,
      /\{\{(?:BRAND_NAME|BRAND_STATIC_DATA_URI|BRAND_HEADER_DATA_URI|BRAND_LOADING_DATA_URI|REMIX_TAXONOMY_JSON)\}\}/,
      `${resource.uri} must not keep unexpanded brand or taxonomy placeholders`,
    );
  }
});

test("links every UI tool to a registered resource and keeps the draft tool headless", () => {
  for (const { descriptor } of TOOL_REGISTRY) {
    if (descriptor.name === "save_jewelry_visual_draft") {
      assert.equal(descriptor._meta, undefined, "save_jewelry_visual_draft must not render a UI");
      continue;
    }
    const resourceUri = descriptor._meta?.ui?.resourceUri;
    assert.ok(resourceUri, `${descriptor.name} must declare _meta.ui.resourceUri`);
    assert.ok(RESOURCE_URIS.has(resourceUri), `${descriptor.name} resourceUri must be registered`);
    assert.equal(descriptor._meta["openai/outputTemplate"], resourceUri);
    assert.equal(typeof descriptor._meta["openai/toolInvocation/invoking"], "string");
    assert.equal(typeof descriptor._meta["openai/toolInvocation/invoked"], "string");
  }
  assert.equal(
    new Set(TOOL_REGISTRY.filter(({ descriptor }) => descriptor._meta).map(({ descriptor }) => descriptor._meta.ui.resourceUri)).size,
    8,
    "the nine UI tools must share exactly the eight registered resources",
  );
});

test("answers initialize with the svt_jewelry_ui identity and capabilities", async () => {
  const response = await dispatchOne(request(1, "initialize"));
  assert.equal(response.jsonrpc, "2.0");
  assert.equal(response.id, 1);
  assert.deepEqual(response.result.serverInfo, { name: "svt_jewelry_ui", version: SERVER_VERSION });
  assert.equal(SERVER_VERSION, "0.2.0");
  assert.deepEqual(response.result.capabilities, { tools: {}, resources: {} });
  assert.equal(response.result.protocolVersion, "2025-06-18");
  assert.match(response.result.instructions, /ask_jewelry_followup_questions/);

  const negotiated = await dispatchOne(request(2, "initialize", { protocolVersion: "2024-11-05" }));
  assert.equal(negotiated.result.protocolVersion, "2024-11-05");
});

test("lists tools and resources over JSON-RPC", async () => {
  const tools = await dispatchOne(request(3, "tools/list"));
  assert.deepEqual(tools.result.tools.map(({ name }) => name), EXPECTED_TOOL_NAMES);

  const resources = await dispatchOne(request(4, "resources/list"));
  assert.equal(resources.result.resources.length, 8);
  for (const resource of resources.result.resources) {
    assert.ok(RESOURCE_URIS.has(resource.uri));
    assert.equal(resource.mimeType, RESOURCE_MIME_TYPE);
    assert.equal(resource.mimeType, "text/html;profile=mcp-app");
    assert.equal(typeof resource.name, "string");
    assert.equal(typeof resource.description, "string");
    assert.equal(resource.html, undefined, "resources/list must not inline HTML");
  }
});

test("reads every ui resource over JSON-RPC and rejects unknown URIs", async () => {
  for (const [index, resource] of RESOURCE_REGISTRY.entries()) {
    const response = await dispatchOne(request(100 + index, "resources/read", { uri: resource.uri }));
    assert.equal(response.id, 100 + index);
    assert.equal(response.result.contents.length, 1);
    const [content] = response.result.contents;
    assert.equal(content.uri, resource.uri);
    assert.equal(content.mimeType, RESOURCE_MIME_TYPE);
    assert.equal(content.text, resource.html);
    assert.ok(content.text.length > 0);
    assert.equal(content._meta.ui.prefersBorder, false);
    assert.deepEqual(content._meta.ui.csp, { connectDomains: [], resourceDomains: [] });
    assert.equal(content._meta["openai/widgetPrefersBorder"], false);
  }
  const missing = await dispatchOne(request(200, "resources/read", { uri: "ui://svt-jewelry/missing/v1.html" }));
  assert.deepEqual(missing.error, { code: -32002, message: "resource not found" });
});

test("ignores notifications and malformed envelopes and rejects unknown methods", async () => {
  assert.deepEqual(await dispatch(request(1, "notifications/initialized")), []);
  assert.deepEqual(await dispatch({ id: 2, method: "tools/list", params: {} }), []);
  assert.deepEqual(await dispatch(null), []);
  const unknown = await dispatchOne(request(3, "jewelry/bogus"));
  assert.equal(unknown.error.code, -32601);
  assert.match(unknown.error.message, /method not found: jewelry\/bogus/);
});

test("wraps unknown tools and handler failures as MCP error results", async () => {
  const unknown = await dispatchOne(request(1, "tools/call", { name: "no_such_tool", arguments: {} }));
  assert.equal(unknown.result.isError, true);
  assert.match(unknown.result.content[0].text, /unknown tool/);

  const invalid = await dispatchOne(request(2, "tools/call", {
    name: "ask_jewelry_followup_questions",
    arguments: { fields: [] },
  }));
  assert.equal(invalid.result.isError, true);
  assert.equal(invalid.result.content.length, 1);
  assert.equal(invalid.result.content[0].type, "text");
  assert.match(invalid.result.content[0].text, /^Unable to render jewelry UI: title is required$/);

  const valid = await dispatchOne(request(3, "tools/call", {
    name: "ask_jewelry_creation_brief",
    arguments: { workflow: "poster" },
  }));
  assertMcpSuccess(valid.result);
});

test("validates follow-up form arguments and rejects malformed fields", () => {
  const run = (args) => runTool("ask_jewelry_followup_questions", args);
  assert.throws(() => run(null), /tool arguments must be an object/);
  assert.throws(() => run([]), /tool arguments must be an object/);
  assert.throws(() => run({ fields: [{ id: "a", label: "A", type: "text" }] }), /title is required/);
  assert.throws(() => run({ title: "T", fields: [] }), /fields must contain 1 to 4 items/);
  assert.throws(
    () => run({ title: "T", fields: [1, 2, 3, 4, 5].map((index) => ({ id: `f${index}`, label: "L", type: "text" })) }),
    /fields must contain 1 to 4 items/,
  );
  assert.throws(() => run({ title: "T", fields: ["nope"] }), /field 1 must be an object/);
  assert.throws(() => run({ title: "T", fields: [{ id: "1bad", label: "L", type: "text" }] }), /field 1 has an invalid id/);
  assert.throws(
    () => run({ title: "T", fields: [{ id: "a", label: "A", type: "text" }, { id: "a", label: "B", type: "text" }] }),
    /duplicate field id: a/,
  );
  assert.throws(() => run({ title: "T", fields: [{ id: "a", label: " ", type: "text" }] }), /field a requires a label/);
  assert.throws(() => run({ title: "T", fields: [{ id: "a", label: "A", type: "rank" }] }), /field a has an unsupported type/);
  assert.throws(
    () => run({ title: "T", fields: [{ id: "a", label: "A", type: "single", options: [{ id: "o1", label: "One" }] }] }),
    /field a requires at least two options/,
  );
  assert.throws(
    () => run({
      title: "T",
      fields: [{
        id: "a",
        label: "A",
        type: "multi",
        options: Array.from({ length: 9 }, (_, index) => ({ id: `o${index}`, label: `L${index}` })),
      }],
    }),
    /field a options must contain 2 to 8 items/,
  );
  assert.throws(
    () => run({
      title: "T",
      fields: [{ id: "a", label: "A", type: "single", options: [{ id: "o", label: "1" }, { id: "o", label: "2" }] }],
    }),
    /field a has duplicate option id: o/,
  );
  assert.throws(
    () => run({
      title: "T",
      fields: [{ id: "a", label: "A", type: "single", options: [{ id: "o1", label: " " }, { id: "o2", label: "2" }] }],
    }),
    /field a option 1 requires id and label/,
  );
  assert.throws(
    () => run({
      title: "T",
      fields: [{
        id: "a",
        label: "A",
        type: "single",
        options: [
          { id: "o1", label: "1", preview: "https://example.com/x.png" },
          { id: "o2", label: "2" },
        ],
      }],
    }),
    /preview must be a data:image URL/,
  );
  assert.throws(
    () => run({
      title: "T",
      fields: [{
        id: "a",
        label: "A",
        type: "single",
        options: [
          { id: "o1", label: "1", preview: "data:image/png;base64,AA==", previewPath: "/tmp/x.png" },
          { id: "o2", label: "2" },
        ],
      }],
    }),
    /must use preview or previewPath, not both/,
  );
  assert.throws(
    () => run({
      title: "T",
      fields: [
        { id: "a", label: "A", type: "single", options: [{ id: "o1", label: "1", preview: "data:image/png;base64,AA==" }, { id: "o2", label: "2" }] },
        { id: "b", label: "B", type: "single", options: [{ id: "p1", label: "1", preview: "data:image/png;base64,AA==" }, { id: "p2", label: "2" }] },
      ],
    }),
    /visual previews must be grouped into one choice field per form/,
  );
});

test("normalizes a valid follow-up form into MCP content and structured data", () => {
  const result = assertMcpSuccess(runTool("ask_jewelry_followup_questions", {
    title: " 确认方向 ",
    prompt: "两个快速问题",
    formId: "form-fixed-1",
    fields: [
      { id: "piece", label: "品类", type: "single", required: true, options: [{ id: "ring", label: "戒指" }, { id: "necklace", label: "项链" }] },
      { id: "notes", label: "补充", type: "text", placeholder: "可选" },
    ],
  }));
  const { form } = result.structuredContent;
  assert.equal(form.formId, "form-fixed-1");
  assert.equal(form.title, "确认方向");
  assert.equal(form.submitLabel, "提交设计方向");
  assert.equal(form.messagePrefix, "已提交珠宝设计方向");
  assert.equal(form.fields.length, 2);
  assert.equal(form.fields[0].required, true);
  assert.equal(form.fields[1].required, false);
  assert.equal(form.fields[1].options, undefined);
  assert.match(result.content[0].text, /确认方向/);
  assert.match(result.content[0].text, /- 品类（必填）：戒指 \/ 项链/);
  assert.match(result.content[0].text, /If an interactive card is unavailable/);
  assert.equal(result._meta.formId, "form-fixed-1");
  assert.equal(result._meta.ui.resourceUri, "ui://svt-jewelry/followup-questions/v4.html");
  assert.equal(result._meta.formMedia, undefined, "no previews means no formMedia");

  const generated = runTool("ask_jewelry_followup_questions", {
    title: "T",
    fields: [{ id: "a", label: "A", type: "text" }],
  });
  assert.match(generated.structuredContent.form.formId, /^[0-9a-f-]{36}$/);
});

test("rejects malformed retouch comparisons before reading images", async (t) => {
  const root = await makeTempRoot(t);
  const png = await writePng(root, "a.png");
  const txt = join(root, "note.txt");
  await writeFile(txt, "not an image");
  const run = (args) => runTool("show_jewelry_retouch_comparison", args);

  assert.throws(() => run(undefined), /tool arguments must be an object/);
  assert.throws(() => run("pairs"), /tool arguments must be an object/);
  assert.throws(() => run({}), /RETOUCH-A\.beforePath is required/);
  assert.throws(
    () => run({ pairs: Array.from({ length: 9 }, () => ({ beforePath: png, afterPath: png })) }),
    /pairs must contain 1 to 8 completed items/,
  );
  assert.throws(() => run({ pairs: ["nope"] }), /pair 1 must be an object/);
  assert.throws(
    () => run({ pairs: [{ id: "RETOUCH-B", beforePath: png, afterPath: png }] }),
    /pair 1 id must be RETOUCH-A/,
  );
  assert.throws(() => run({ beforePath: "relative/a.png", afterPath: png }), /must be an absolute local path/);
  assert.throws(() => run({ beforePath: txt, afterPath: png }), /must be a PNG or JPEG image/);
  assert.throws(() => run({ beforePath: join(root, "missing.png"), afterPath: png }), /ENOENT|no such file/);
  const directory = join(root, "directory.png");
  await mkdir(directory);
  assert.throws(() => run({ beforePath: directory, afterPath: png }), /must point to a file/);
});

test("builds retouch comparison results for legacy and multi-pair inputs", async (t) => {
  const root = await makeTempRoot(t);
  const before = await writePng(root, "before.png");
  const after = await writePng(root, "after.png");

  const single = assertMcpSuccess(runTool("show_jewelry_retouch_comparison", {
    beforePath: before,
    afterPath: after,
    initialPosition: 150,
  }));
  const { comparison } = single.structuredContent;
  assert.equal(comparison.title, "珠宝精修前后对比");
  assert.equal(comparison.pairs.length, 1);
  assert.equal(comparison.pairs[0].id, "RETOUCH-A");
  assert.equal(comparison.pairs[0].before.path, before);
  assert.equal(comparison.pairs[0].after.label, "精修后");
  assert.equal(comparison.initialPosition, 100, "initialPosition must clamp to 100");
  assert.deepEqual(comparison.before, comparison.pairs[0].before, "single pairs must expose top-level before/after");
  assert.match(single.content[0].text, /RETOUCH-A 精修前: /);
  assert.ok(single._meta.comparisonMedia.pairs["RETOUCH-A"].before.startsWith("data:image/png;base64,"));
  assert.equal(single._meta.comparisonMedia.before, single._meta.comparisonMedia.pairs["RETOUCH-A"].before);

  const multi = assertMcpSuccess(runTool("show_jewelry_retouch_comparison", {
    title: "两组对比",
    initialPairId: "RETOUCH-Z",
    pairs: [
      { beforePath: before, afterPath: after },
      { id: "RETOUCH-B", beforePath: after, afterPath: before, title: "第二组" },
    ],
  }));
  const multiComparison = multi.structuredContent.comparison;
  assert.equal(multiComparison.pairs.length, 2);
  assert.equal(multiComparison.pairs[1].id, "RETOUCH-B");
  assert.equal(multiComparison.pairs[1].title, "第二组");
  assert.equal(multiComparison.pairs[0].title, "精修对比 1");
  assert.equal(multiComparison.initialPairId, "RETOUCH-A", "unknown initialPairId must fall back to the first pair");
  assert.equal(multiComparison.initialPosition, 50);
  assert.equal(multiComparison.before, undefined, "multi-pair results must not duplicate top-level images");
  assert.deepEqual(Object.keys(multi._meta.comparisonMedia.pairs), ["RETOUCH-A", "RETOUCH-B"]);
});

test("normalizes remix briefs with safe defaults and taxonomy filtering", () => {
  const run = (args) => runTool("ask_jewelry_remix_brief", args);
  assert.throws(() => run([1]), /tool arguments must be an object/);
  assert.equal(run(null).structuredContent.remixBrief.count, 4, "nullish arguments fall back to defaults");

  const empty = assertMcpSuccess(run(undefined));
  const brief = empty.structuredContent.remixBrief;
  assert.equal(brief.schemaVersion, 2);
  assert.equal(brief.count, 4);
  assert.equal(brief.designSystem, "");
  assert.equal(brief.structureFidelity, "medium");
  assert.equal(brief.intensity, "balanced");
  assert.equal(brief.fusionStrategy, "pattern_translation");
  assert.equal(brief.referenceRole, "style");
  assert.equal(brief.title, "确认爆款二创方向");
  assert.equal(brief.hasReferenceImages, false);
  assert.deepEqual(brief.themes, []);
  assert.match(empty.content[0].text, /4 或 8 个独立方向/);
  assert.equal(empty._meta.formId, brief.formId);

  const tailored = run({
    title: "定制",
    hasReferenceImages: true,
    defaults: {
      count: 8,
      designSystem: "gold",
      structureFidelity: "high",
      intensity: "bogus",
      themes: ["other", "not-a-real-theme"],
      customStyles: " 珐琅 ",
      referenceRole: "material",
    },
  }).structuredContent.remixBrief;
  assert.equal(tailored.count, 8);
  assert.equal(tailored.designSystem, "gold");
  assert.equal(tailored.structureFidelity, "high");
  assert.equal(tailored.intensity, "balanced", "unknown enum values must fall back");
  assert.deepEqual(tailored.themes, ["other"], "themes must be filtered to the taxonomy plus other");
  assert.equal(tailored.customStyles, "珐琅");
  assert.equal(tailored.referenceRole, "material");

  const invalidSystem = run({ defaults: { designSystem: "platinum", themes: ["other"] } }).structuredContent.remixBrief;
  assert.equal(invalidSystem.designSystem, "");
  assert.deepEqual(invalidSystem.themes, [], "selections must empty out without a valid design system");
});

test("rejects incomplete remix galleries and wrong candidate ids", async (t) => {
  const root = await makeTempRoot(t);
  const png = await writePng(root, "c.png");
  const candidate = (id) => ({ id, path: png, title: id, summary: "s", useCase: "u" });
  const run = (args) => runTool("show_jewelry_remix_gallery", args);

  assert.throws(() => run({}), /tool arguments must be an object|exactly 4 or 8/);
  assert.throws(() => run({ sourcePath: png, candidates: [] }), /candidates must contain exactly 4 or 8 completed items/);
  assert.throws(
    () => run({ sourcePath: png, candidates: ["A", "B", "C"].map(candidate) }),
    /candidates must contain exactly 4 or 8 completed items/,
  );
  assert.throws(
    () => run({ sourcePath: png, candidates: ["A", "B", "C", "D", "E"].map((id) => candidate(`REMIX-${id}`)) }),
    /candidates must contain exactly 4 or 8 completed items/,
  );
  assert.throws(
    () => run({ sourcePath: png, candidates: [candidate("REMIX-B"), candidate("REMIX-B"), candidate("REMIX-C"), candidate("REMIX-D")] }),
    /candidate 1 id must be REMIX-A/,
  );
  assert.throws(
    () => run({ sourcePath: png, candidates: ["nope", "nope", "nope", "nope"] }),
    /candidate 1 must be an object/,
  );
  assert.throws(
    () => run({ sourcePath: png, candidates: ["A", "B", "C", "D"].map((id) => ({ id: `REMIX-${id}`, path: join(root, `${id}.png`) })) }),
    /ENOENT|no such file/,
  );
});

test("builds four and eight candidate remix galleries with shared source media", async (t) => {
  const root = await makeTempRoot(t);
  const source = await writePng(root, "source.png");
  const candidate = async (id) => ({ id, path: await writePng(root, `${id}.png`), title: `候选 ${id}`, summary: "s", useCase: "u" });

  const four = assertMcpSuccess(runTool("show_jewelry_remix_gallery", {
    sourcePath: source,
    initialCandidateId: "REMIX-C",
    candidates: await Promise.all(["A", "B", "C", "D"].map((letter) => candidate(`REMIX-${letter}`))),
  }));
  const gallery = four.structuredContent.gallery;
  assert.equal(gallery.title, "珠宝爆款二创");
  assert.equal(gallery.initialCandidateId, "REMIX-C");
  assert.equal(gallery.initialPosition, 50);
  assert.equal(gallery.source.path, source);
  assert.equal(gallery.source.label, "原款");
  assert.equal(gallery.candidates.length, 4);
  assert.deepEqual(gallery.candidates.map(({ id }) => id), ["REMIX-A", "REMIX-B", "REMIX-C", "REMIX-D"]);
  assert.match(four.content[0].text, /- 原款: /);
  assert.match(four.content[0].text, /- REMIX-D 候选 REMIX-D: /);
  assert.ok(four._meta.galleryMedia.source.startsWith("data:image/png;base64,"));
  assert.deepEqual(Object.keys(four._meta.galleryMedia.candidates), ["REMIX-A", "REMIX-B", "REMIX-C", "REMIX-D"]);

  const eight = runTool("show_jewelry_remix_gallery", {
    sourcePath: source,
    candidates: await Promise.all("ABCDEFGH".split("").map((letter) => candidate(`REMIX-${letter}`))),
  });
  assert.equal(eight.structuredContent.gallery.candidates.length, 8);
  assert.equal(eight.structuredContent.gallery.initialCandidateId, "REMIX-A");
});

test("validates creation brief workflows and unresolved fields", () => {
  const run = (args) => runTool("ask_jewelry_creation_brief", args);
  assert.throws(() => run([]), /tool arguments must be an object/);
  assert.throws(() => run({}), /workflow must be poster, catalog, or display/);
  assert.throws(() => run({ workflow: "grid" }), /workflow must be poster, catalog, or display/);
  assert.throws(
    () => run({ workflow: "poster", unresolvedFields: ["mode", "channel"] }),
    /unresolvedFields must contain only unresolved poster fields/,
  );
  assert.throws(
    () => run({ workflow: "poster", unresolvedFields: ["mode", "mode"] }),
    /unresolvedFields must contain only unresolved poster fields/,
  );
  assert.throws(
    () => run({ workflow: "catalog", unresolvedFields: [] }),
    /unresolvedFields must contain only unresolved catalog fields/,
  );
});

test("normalizes poster, catalog, and display creation briefs", () => {
  const poster = assertMcpSuccess(runTool("ask_jewelry_creation_brief", { workflow: "poster" }));
  const posterBrief = poster.structuredContent.creationBrief;
  assert.equal(posterBrief.workflow, "poster");
  assert.deepEqual(posterBrief.unresolvedFields, ["mode", "aspectRatio", "composition", "typography"]);
  assert.equal(posterBrief.title, "确认珠宝海报方向");
  assert.equal(posterBrief.mode, "editorial_board");
  assert.equal(posterBrief.aspectRatio, "3:4");
  assert.equal(posterBrief.channel, "", "fields outside the workflow must stay empty");
  assert.match(poster.content[0].text, /workflow: poster/);
  assert.equal(poster._meta.formId, posterBrief.formId);

  const catalog = runTool("ask_jewelry_creation_brief", {
    workflow: "catalog",
    title: "自定义标题",
    hasSourceImages: true,
    unresolvedFields: ["channel", "background"],
    defaults: { channel: "live", style: "custom_style" },
  }).structuredContent.creationBrief;
  assert.equal(catalog.title, "自定义标题");
  assert.equal(catalog.hasSourceImages, true);
  assert.deepEqual(catalog.unresolvedFields, ["channel", "background"]);
  assert.equal(catalog.channel, "live");
  assert.equal(catalog.style, "custom_style");
  assert.equal(catalog.mode, "core_five", "unspecified defaults must keep the workflow fallback");

  const display = runTool("ask_jewelry_creation_brief", { workflow: "display" }).structuredContent.creationBrief;
  assert.deepEqual(display.unresolvedFields, ["mode", "aspectRatio", "sceneIntensity", "background"]);
  assert.equal(display.sceneIntensity, "balanced");
  assert.equal(display.background, "quiet_neutral");
});

test("rejects malformed creation galleries and unstable asset ids", async (t) => {
  const root = await makeTempRoot(t);
  const png = await writePng(root, "item.png");
  const run = (args) => runTool("show_jewelry_creation_gallery", args);

  assert.throws(() => run(null), /tool arguments must be an object/);
  assert.throws(() => run({ workflow: "design", items: [{ id: "POSTER-1", path: png }] }), /workflow must be poster, catalog, display, grid, grid_redraw, reference_sheet, or tryon/);
  assert.throws(() => run({ workflow: "poster", items: [] }), /items must contain 1 to 12 completed assets/);
  assert.throws(
    () => run({ workflow: "poster", items: Array.from({ length: 13 }, (_, index) => ({ id: `POSTER-${index}`, path: png })) }),
    /items must contain 1 to 12 completed assets/,
  );
  assert.throws(() => run({ workflow: "poster", items: ["nope"] }), /item 1 must be an object/);
  assert.throws(
    () => run({ workflow: "poster", items: [{ id: "CATALOG-1", path: png }] }),
    /item 1 id must start with POSTER-/,
  );
  assert.throws(
    () => run({ workflow: "poster", items: [{ id: `POSTER-${"A".repeat(64)}`, path: png }] }),
    /item 1 id must be at most 64 characters/,
  );
  assert.throws(
    () => run({ workflow: "poster", items: [{ id: "POSTER-1", path: png }, { id: "POSTER-1", path: png }] }),
    /creation item ids must be unique/,
  );
  assert.throws(
    () => run({ workflow: "grid", items: [{ id: "GRID-1", path: png }], initialAssetId: "POSTER-1" }),
    /initialAssetId must start with GRID-/,
  );
  assert.throws(
    () => run({ workflow: "poster", items: [{ id: "POSTER-1", path: png }], initialAssetId: `POSTER-${"A".repeat(64)}` }),
    /initialAssetId must be at most 64 characters|initialAssetId must start with/,
  );
});

test("builds creation galleries with workflow-prefixed ids and UI-only media", async (t) => {
  const root = await makeTempRoot(t);
  const first = await writePng(root, "first.png");
  const second = await writePng(root, "second.png");

  const result = assertMcpSuccess(runTool("show_jewelry_creation_gallery", {
    workflow: "grid_redraw",
    items: [
      { id: "REDRAW-1", path: first, summary: "s", slot: "CELL-1" },
      { id: "REDRAW-2", path: second, title: "重绘 2" },
    ],
    initialAssetId: "REDRAW-2",
  }));
  const gallery = result.structuredContent.creationGallery;
  assert.equal(gallery.workflow, "grid_redraw");
  assert.equal(gallery.title, "九宫格拆分重绘");
  assert.equal(gallery.initialAssetId, "REDRAW-2");
  assert.equal(gallery.items.length, 2);
  assert.equal(gallery.items[0].title, "九宫格拆分重绘 1", "missing titles must use the workflow fallback");
  assert.equal(gallery.items[1].title, "重绘 2");
  assert.equal(gallery.items[0].slot, "CELL-1");
  assert.deepEqual(Object.keys(result._meta.creationMedia.items), ["REDRAW-1", "REDRAW-2"]);
  assert.match(result.content[0].text, /- REDRAW-2 重绘 2: /);

  const fallback = runTool("show_jewelry_creation_gallery", {
    workflow: "tryon",
    items: [{ id: "TRYON-1", path: first }],
    initialAssetId: "TRYON-9",
  });
  assert.equal(fallback.structuredContent.creationGallery.initialAssetId, "TRYON-1", "unknown initialAssetId must fall back to the first item");
});

test("rejects malformed design galleries and enforces sketch ids", async (t) => {
  const root = await makeTempRoot(t);
  const png = await writePng(root, "design.png");
  const run = (args) => runTool("show_jewelry_design_gallery", args);

  assert.throws(() => run("items"), /tool arguments must be an object/);
  assert.throws(() => run({ items: [] }), /items must contain 1 to 12 completed designs/);
  assert.throws(
    () => run({ items: Array.from({ length: 13 }, (_, index) => ({ id: `JOB-${index}`, path: png })) }),
    /items must contain 1 to 12 completed designs/,
  );
  assert.throws(() => run({ items: [42] }), /item 1 must be an object/);
  assert.throws(() => run({ items: [{ id: "bad id!", path: png }] }), /item 1 id must use the stable runner-id format/);
  assert.throws(() => run({ items: [{ id: "-leading-hyphen", path: png }] }), /item 1 id must use the stable runner-id format/);
  assert.throws(
    () => run({ items: [{ id: `J${"a".repeat(64)}`, path: png }] }),
    /item 1 id must be at most 64 characters/,
  );
  assert.throws(
    () => run({ items: [{ id: "JOB-1", path: png }, { id: "JOB-1", path: png }] }),
    /design item ids must be unique/,
  );
  assert.throws(
    () => run({ items: [{ id: "JOB-1", path: png }], initialDesignId: "bad id!" }),
    /initialDesignId must use the stable runner-id format/,
  );
  assert.throws(
    () => run({ items: [{ id: "JOB-1", path: png }], initialDesignId: `J${"a".repeat(64)}` }),
    /initialDesignId must be at most 64 characters/,
  );
  assert.throws(
    () => run({ sourceWorkflow: "sketch_design", items: ["A", "B", "C"].map((id) => ({ id: `SKETCH-${id}`, path: png })) }),
    /sketch_design items must use SKETCH-A through SKETCH-D in order/,
  );
  assert.throws(
    () => run({
      sourceWorkflow: "sketch_design",
      items: ["B", "A", "C", "D"].map((id) => ({ id: `SKETCH-${id}`, path: png })),
    }),
    /sketch_design items must use SKETCH-A through SKETCH-D in order/,
  );
});

test("builds design galleries and preserves runner and sketch ids", async (t) => {
  const root = await makeTempRoot(t);
  const png = await writePng(root, "design.png");

  const design = assertMcpSuccess(runTool("show_jewelry_design_gallery", {
    items: [
      { id: "run_01", path: png, pieceType: "戒指" },
      { id: "run_02", path: png, title: "定制标题", materials: "18K 金" },
    ],
    initialDesignId: "run_02",
  }));
  const gallery = design.structuredContent.designGallery;
  assert.equal(gallery.sourceWorkflow, "design");
  assert.equal(gallery.title, "珠宝设计成品");
  assert.equal(gallery.initialDesignId, "run_02");
  assert.equal(gallery.items[0].title, "珠宝设计 1");
  assert.equal(gallery.items[1].title, "定制标题");
  assert.equal(gallery.items[0].pieceType, "戒指");
  assert.deepEqual(Object.keys(design._meta.designMedia.items), ["run_01", "run_02"]);
  assert.match(design.content[0].text, /- run_02 定制标题: /);

  const sketch = runTool("show_jewelry_design_gallery", {
    sourceWorkflow: "sketch_design",
    items: ["A", "B", "C", "D"].map((id) => ({ id: `SKETCH-${id}`, path: png })),
  });
  assert.equal(sketch.structuredContent.designGallery.sourceWorkflow, "sketch_design");
  assert.deepEqual(
    sketch.structuredContent.designGallery.items.map(({ id }) => id),
    ["SKETCH-A", "SKETCH-B", "SKETCH-C", "SKETCH-D"],
  );
});

test("rejects invalid local-editor workspaces, modes, and categories", async (t) => {
  const { root, workspace } = await makeWorkspace(t);
  const source = await writePng(workspace, "source.png");
  const run = (args) => runTool("open_jewelry_local_editor", args);

  assert.throws(() => run(undefined), /tool arguments must be an object/);
  assert.throws(() => run({ workspacePath: "artifacts/runs/x", mode: "local_edit", category: "ring" }), /workspacePath must be an absolute/);
  assert.throws(() => run({ workspacePath: root, mode: "local_edit", category: "ring" }), /must be the exact active artifacts\/runs\/<task-id> directory/);
  assert.throws(() => run({ workspacePath: join(root, "artifacts", "runs", "missing-task"), mode: "local_edit", category: "ring" }), /ENOENT|no such file/);

  const linkRoot = await makeTempRoot(t);
  const realWorkspace = join(linkRoot, "artifacts", "runs", "real-task");
  await mkdir(realWorkspace, { recursive: true });
  const linkWorkspace = join(linkRoot, "artifacts", "runs", "link-task");
  await symlink(realWorkspace, linkWorkspace);
  assert.throws(
    () => run({ workspacePath: linkWorkspace, mode: "local_edit", category: "ring" }),
    /workspacePath must not be a symbolic link/,
  );

  assert.throws(() => run({ workspacePath: workspace, mode: "generate", category: "ring" }), /mode is required and must be local_edit, put_here, or sketch_design/);
  assert.throws(() => run({ workspacePath: workspace, mode: "local_edit", category: "tiara" }), /category is required and unsupported/);
  assert.throws(() => run({ workspacePath: workspace, mode: "local_edit", category: "other" }), /customCategory is required/);
  assert.throws(
    () => run({ workspacePath: workspace, mode: "local_edit", category: "other", customCategory: "x".repeat(41) }),
    /customCategory is required and must be at most 40 characters/,
  );
  assert.throws(() => run({ workspacePath: workspace, mode: "local_edit", category: "ring" }), /sourcePath is required for local_edit and put_here/);
  assert.throws(() => run({ workspacePath: workspace, mode: "put_here", category: "ring" }), /sourcePath is required for local_edit and put_here/);
  assert.throws(
    () => run({ workspacePath: workspace, mode: "sketch_design", category: "ring", referenceImages: [1, 2, 3, 4, 5].map(() => ({})) }),
    /referenceImages must contain at most 4 items/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, mode: "sketch_design", category: "ring", referenceImages: [{ path: source, role: "vibe" }] }),
    /referenceImages\[0\]\.role is unsupported/,
  );
  const outside = await writePng(root, "outside.png");
  assert.throws(
    () => run({ workspacePath: workspace, mode: "sketch_design", category: "ring", referenceImages: [{ path: outside, role: "style" }] }),
    /must not escape the active workspace/,
  );
});

test("opens the local editor for sketch and source-driven modes", async (t) => {
  const { workspace } = await makeWorkspace(t);
  const source = await writePng(workspace, "source.png");
  const reference = await writePng(workspace, "reference.png");

  const blank = assertMcpSuccess(runTool("open_jewelry_local_editor", {
    workspacePath: workspace,
    mode: "sketch_design",
    category: "other",
    customCategory: "发簪",
  }));
  const blankBench = blank.structuredContent.visualWorkbench;
  assert.equal(blankBench.workflow, "local_edit");
  assert.equal(blankBench.mode, "sketch_design");
  assert.equal(blankBench.title, "随手画转珠宝");
  assert.equal(blankBench.customCategory, "发簪");
  assert.equal(blankBench.source, undefined);
  assert.equal(blankBench.workspacePath, realpathSync(workspace), "workspacePath must be canonicalized");
  assert.deepEqual(blankBench.referenceImages, []);
  assert.equal(blankBench.defaults.ratio, "1:1");
  assert.match(blank.content[0].text, /空白画板：未提供源图/);
  assert.equal(blank._meta.visualWorkbenchMedia.source, undefined);

  const edit = assertMcpSuccess(runTool("open_jewelry_local_editor", {
    workspacePath: workspace,
    mode: "local_edit",
    category: "ring",
    sourcePath: source,
    referenceImages: [{ path: reference, role: "material" }],
    defaults: { instruction: "换主石" },
  }));
  const bench = edit.structuredContent.visualWorkbench;
  assert.equal(bench.mode, "local_edit");
  assert.equal(bench.title, "珠宝局部重绘");
  assert.equal(bench.source.path, realpathSync(source), "workspace images must be canonicalized");
  assert.equal(bench.source.mimeType, "image/png");
  assert.equal(bench.referenceImages.length, 1);
  assert.equal(bench.referenceImages[0].role, "material");
  assert.equal(bench.referenceImages[0].data, undefined, "structured content must stay path-only");
  assert.equal(bench.defaults.instruction, "换主石");
  assert.match(edit.content[0].text, /源图: /);
  assert.ok(edit._meta.visualWorkbenchMedia.source.startsWith("data:image/png;base64,"));
  assert.ok(edit._meta.visualWorkbenchMedia.references["REF-1"].startsWith("data:image/png;base64,"));
  assert.match(bench.sessionId, /^[0-9a-f-]{36}$/);
});

test("rejects invalid tryon editor inputs", async (t) => {
  const { workspace } = await makeWorkspace(t);
  const jewelry = await writePng(workspace, "jewelry.png");
  const run = (args) => runTool("open_jewelry_tryon_editor", args);

  assert.throws(() => run(null), /tool arguments must be an object/);
  assert.throws(
    () => run({ workspacePath: workspace, jewelryPath: jewelry, modelPath: jewelry, category: "other" }),
    /category is unsupported/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, category: "ring" }),
    /jewelryPath is required/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, jewelryPath: jewelry, category: "ring" }),
    /modelPath is required/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, jewelryPath: jewelry, modelPath: join(workspace, "missing.png"), category: "ring" }),
    /ENOENT|no such file/,
  );
});

test("opens the tryon editor with clamped placement defaults", async (t) => {
  const { workspace } = await makeWorkspace(t);
  const jewelry = await writePng(workspace, "jewelry.png");
  const model = await writePng(workspace, "model.png");

  const result = assertMcpSuccess(runTool("open_jewelry_tryon_editor", {
    workspacePath: workspace,
    jewelryPath: jewelry,
    modelPath: model,
    category: "necklace",
    defaults: { x: 5, y: -1, scale: 0.001, rotation: 999, pair: true, instruction: "戴在锁骨" },
  }));
  const bench = result.structuredContent.visualWorkbench;
  assert.equal(bench.workflow, "tryon");
  assert.equal(bench.title, "珠宝模特佩戴");
  assert.equal(bench.category, "necklace");
  assert.equal(bench.jewelry.path, realpathSync(jewelry));
  assert.equal(bench.model.path, realpathSync(model));
  assert.deepEqual(bench.defaults, { instruction: "戴在锁骨", pair: true, ratio: "3:4", x: 1, y: 0, scale: 0.02, rotation: 180 });
  assert.match(result.content[0].text, /珠宝: /);
  assert.match(result.content[0].text, /模特: /);
  assert.ok(result._meta.visualWorkbenchMedia.jewelry.startsWith("data:image/png;base64,"));
  assert.ok(result._meta.visualWorkbenchMedia.model.startsWith("data:image/png;base64,"));

  const plain = runTool("open_jewelry_tryon_editor", {
    workspacePath: workspace,
    jewelryPath: jewelry,
    modelPath: model,
    category: "ring",
  }).structuredContent.visualWorkbench;
  assert.deepEqual(plain.defaults, { instruction: "", pair: false, ratio: "3:4", x: 0.5, y: 0.55, scale: 0.24, rotation: 0 });
});

test("rejects malformed visual drafts before writing files", async (t) => {
  const { workspace } = await makeWorkspace(t);
  const source = await writePng(workspace, "source.png");
  const run = (args) => runTool("save_jewelry_visual_draft", args);
  const sketchState = { schemaVersion: 2, mode: "sketch_design", category: "ring" };

  assert.throws(() => run([]), /tool arguments must be an object/);
  assert.throws(
    () => run({ workspacePath: workspace, workflow: "poster", state: sketchState, compositeDataUrl: COMPOSITE_DATA_URL }),
    /workflow must be local_edit or tryon/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, workflow: "local_edit", state: "state", compositeDataUrl: COMPOSITE_DATA_URL }),
    /state must be an object/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, workflow: "local_edit", state: { ...sketchState, notes: "x".repeat(64 * 1024) }, compositeDataUrl: COMPOSITE_DATA_URL }),
    /state exceeds the 64 KiB draft limit/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, workflow: "local_edit", state: { schemaVersion: 2, mode: "polish", category: "ring", sourcePath: source }, compositeDataUrl: COMPOSITE_DATA_URL }),
    /state\.mode is unsupported/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, workflow: "local_edit", state: { mode: "sketch_design", category: "ring" }, compositeDataUrl: COMPOSITE_DATA_URL }),
    /state\.schemaVersion must be 2/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, workflow: "local_edit", state: { ...sketchState, category: "tiara" }, compositeDataUrl: COMPOSITE_DATA_URL }),
    /state\.category is unsupported/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, workflow: "local_edit", state: sketchState, compositeDataUrl: "https://example.com/x.png" }),
    /compositeDataUrl must be a PNG or JPEG data URL/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, workflow: "local_edit", state: { ...sketchState, mode: "local_edit", sourcePath: "missing.png" }, compositeDataUrl: COMPOSITE_DATA_URL }),
    /ENOENT|no such file/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, workflow: "local_edit", state: { ...sketchState, mode: "local_edit" }, compositeDataUrl: COMPOSITE_DATA_URL }),
    /state\.sourcePath is required for local_edit and put_here/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, workflow: "tryon", state: { jewelryPath: "missing.png", modelPath: "missing.png", category: "ring", transform: {} }, compositeDataUrl: COMPOSITE_DATA_URL }),
    /ENOENT|no such file/,
  );
  assert.throws(
    () => run({ workspacePath: workspace, workflow: "tryon", state: { category: "ring" }, compositeDataUrl: COMPOSITE_DATA_URL }),
    /state\.jewelryPath|ENOENT/,
  );
});

test("saves local-edit drafts inside the workspace with stable ids", async (t) => {
  const { workspace } = await makeWorkspace(t);
  const source = await writePng(workspace, "source.png");

  const sketch = assertMcpSuccess(runTool("save_jewelry_visual_draft", {
    workspacePath: workspace,
    workflow: "local_edit",
    state: { schemaVersion: 2, mode: "sketch_design", category: "pendant", annotations: [] },
    compositeDataUrl: COMPOSITE_DATA_URL,
  }));
  const draft = sketch.structuredContent.visualDraft;
  assert.match(draft.id, /^LOCAL-[0-9A-F]{8}$/);
  assert.equal(draft.workflow, "local_edit");
  assert.equal(draft.draftPath, `visual-workbench/${draft.id}/draft.json`);
  assert.equal(draft.compositePath, `visual-workbench/${draft.id}/composite.png`);
  assert.equal(draft.cutoutPath, undefined);
  assert.match(sketch.content[0].text, /已保存画布草稿 LOCAL-/);
  assert.match(sketch.content[0].text, /Current visual draft \(JSON\): /);
  assert.equal(sketch._meta, undefined, "draft saves must not render a UI");

  const persisted = JSON.parse(await readFile(join(workspace, draft.draftPath), "utf8"));
  assert.equal(persisted.schema_version, 2);
  assert.equal(persisted.id, draft.id);
  assert.equal(persisted.workflow, "local_edit");
  assert.equal(persisted.state.mode, "sketch_design");
  assert.equal(persisted.assets.composite, draft.compositePath);
  const compositeBytes = await readFile(join(workspace, draft.compositePath));
  assert.ok(compositeBytes.equals(PNG_BYTES));

  const edited = runTool("save_jewelry_visual_draft", {
    workspacePath: workspace,
    workflow: "local_edit",
    state: {
      schemaVersion: 2,
      mode: "local_edit",
      category: "ring",
      sourcePath: source,
      annotations: [{ kind: "anchor", id: "ANCHOR-01", instruction: "换主石", position: { x: 0.5, y: 0.4 } }],
    },
    compositeDataUrl: COMPOSITE_DATA_URL,
  });
  assert.match(edited.structuredContent.visualDraft.id, /^LOCAL-[0-9A-F]{8}$/);
});

test("enforces draft annotations, geometry, and confirmed stone cutouts", async (t) => {
  const { workspace } = await makeWorkspace(t);
  const source = await writePng(workspace, "source.png");
  const stone = await writePng(workspace, "stone.png");
  const baseState = { schemaVersion: 2, mode: "local_edit", category: "ring", sourcePath: source };
  const run = (state, extra = {}) => runTool("save_jewelry_visual_draft", {
    workspacePath: workspace,
    workflow: "local_edit",
    state,
    compositeDataUrl: COMPOSITE_DATA_URL,
    ...extra,
  });

  assert.throws(() => run({ ...baseState, annotations: [] }), /local_edit and put_here require at least one annotation/);
  assert.throws(
    () => run({ ...baseState, annotations: Array.from({ length: 9 }, (_, index) => ({ kind: "anchor", id: `ANCHOR-0${index}`, instruction: "i", position: { x: 0, y: 0 } })) }),
    /state\.annotations must contain at most 8 items|invalid id or kind/,
  );
  assert.throws(
    () => run({ ...baseState, annotations: [{ kind: "anchor", id: "ANCHOR-1", instruction: "i", position: { x: 0, y: 0 } }] }),
    /invalid id or kind/,
  );
  assert.throws(
    () => run({ ...baseState, annotations: [{ kind: "region", id: "REGION-01", instruction: "i", bounds: { x: 0.9, y: 0, width: 0.2, height: 0.2 } }] }),
    /bounds must have non-zero size and stay inside the canvas/,
  );
  assert.throws(
    () => run({ ...baseState, annotations: [{ kind: "anchor", id: "ANCHOR-01", instruction: " ", position: { x: 0, y: 0 } }] }),
    /ANCHOR-01\.instruction is required/,
  );
  assert.throws(
    () => run({ ...baseState, annotations: [{ kind: "anchor", id: "ANCHOR-01", instruction: "i", position: { x: 1.5, y: 0 } }] }),
    /must use normalized coordinates/,
  );
  assert.throws(
    () => run({ schemaVersion: 2, mode: "sketch_design", category: "ring", stonePath: stone }),
    /stone-assisted sketch_design requires confirmed cutout/,
  );
  assert.throws(
    () => run({ schemaVersion: 2, mode: "sketch_design", category: "ring", stonePath: stone, cutoutConfirmed: true }),
    /confirmed stone cutout requires cutoutDataUrl and cutoutPreviewDataUrl/,
  );

  const withStone = run(
    { schemaVersion: 2, mode: "sketch_design", category: "ring", stonePath: stone, cutoutConfirmed: true },
    { cutoutDataUrl: COMPOSITE_DATA_URL, cutoutPreviewDataUrl: COMPOSITE_DATA_URL },
  );
  const draft = withStone.structuredContent.visualDraft;
  assert.equal(draft.cutoutPath, `visual-workbench/${draft.id}/cutout.png`);
  assert.equal(draft.cutoutPreviewPath, `visual-workbench/${draft.id}/cutout-preview.png`);
  await readFile(join(workspace, draft.cutoutPath));
  await readFile(join(workspace, draft.cutoutPreviewPath));
});

test("saves tryon drafts with workspace-local jewelry and model paths", async (t) => {
  const { workspace } = await makeWorkspace(t);
  const jewelry = await writePng(workspace, "jewelry.png");
  const model = await writePng(workspace, "model.png");
  const run = (state) => runTool("save_jewelry_visual_draft", {
    workspacePath: workspace,
    workflow: "tryon",
    state,
    compositeDataUrl: COMPOSITE_DATA_URL,
  });

  assert.throws(
    () => run({ jewelryPath: jewelry, modelPath: model, category: "other", transform: {} }),
    /state\.category is unsupported/,
  );
  assert.throws(
    () => run({ jewelryPath: jewelry, modelPath: model, category: "ring" }),
    /state\.transform is required/,
  );

  const result = assertMcpSuccess(run({
    jewelryPath: jewelry,
    modelPath: model,
    category: "earrings",
    transform: { x: 0.5, y: 0.4, scale: 0.2, rotation: 10 },
  }));
  const draft = result.structuredContent.visualDraft;
  assert.match(draft.id, /^TRYON-[0-9A-F]{8}$/);
  const persisted = JSON.parse(await readFile(join(workspace, draft.draftPath), "utf8"));
  assert.equal(persisted.workflow, "tryon");
  assert.equal(persisted.state.category, "earrings");
  assert.deepEqual(persisted.state.transform, { x: 0.5, y: 0.4, scale: 0.2, rotation: 10 });
});
