import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdir, mkdtemp, readFile, realpath, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import readline from "node:readline";
import test from "node:test";
import { runInNewContext } from "node:vm";
import { deflateSync } from "node:zlib";

const serverPath = fileURLToPath(new URL("../mcp/server.mjs", import.meta.url));
const pluginRoot = dirname(dirname(serverPath));

function extractedFunction(html, name) {
  const start = html.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `missing function ${name}`);
  const brace = html.indexOf("{", start);
  let depth = 0;
  for (let index = brace; index < html.length; index += 1) {
    if (html[index] === "{") depth += 1;
    if (html[index] === "}") depth -= 1;
    if (depth === 0) return runInNewContext(`(${html.slice(start, index + 1)})`);
  }
  throw new Error(`unterminated function ${name}`);
}

test("ships the routed Apps UI design contract", async () => {
  const referenceRoot = join(pluginRoot, "skills", "jewelry-studio", "references");
  const conversation = await readFile(join(referenceRoot, "conversation-ui-contract.md"), "utf8");
  const design = await readFile(join(referenceRoot, "apps-ui-design-contract.md"), "utf8");
  const grill = await readFile(join(pluginRoot, "skills", "jewelry-grill-me", "SKILL.md"), "utf8");
  assert.match(conversation, /references\/apps-ui-design-contract\.md/);
  assert.match(conversation, /Apps UI capability resolution/);
  assert.match(conversation, /initial\s+visible tool list/);
  assert.match(conversation, /all intake, editor, comparison, and Gallery surfaces/);
  assert.match(grill, /Every Grill Me question round/);
  assert.match(grill, /discover `ask_jewelry_followup_questions`/);
  assert.match(grill, /before any prose fallback/);
  assert.match(design, /No nested vertical scrolling/);
  assert.match(design, /touch-action: pan-y/);
  assert.match(design, /vertical\s+candidate rail/);
  assert.match(design, /manual host acceptance/);
  assert.match(design, /苏哇科技/);
  assert.match(design, /assets\/brand\//);
  assert.match(design, /prefers-reduced-motion/);
});

test("ships portable local-edit commands and exact current-round manifests", async () => {
  const skill = await readFile(join(pluginRoot, "skills", "jewelry-local-edit", "SKILL.md"), "utf8");
  assert.match(skill, /node "<plugin-root>\/scripts\/jdc\.mjs" visual-workbench/);
  assert.match(skill, /node "<plugin-root>\/scripts\/jdc\.mjs" image2/);
  assert.match(skill, /--job-manifest visual-workbench\/<draft-id>\/jobs\.json/);
});

test("ships maintainable Suwa Technology brand assets and plugin identity", async () => {
  const manifest = JSON.parse(await readFile(join(pluginRoot, ".codex-plugin", "plugin.json"), "utf8"));
  assert.equal(manifest.author.name, "苏哇科技");
  assert.equal(manifest.interface.developerName, "苏哇科技");
  assert.match(manifest.interface.displayName, /苏哇科技/);
  assert.equal(manifest.interface.composerIcon, "./assets/brand/logo-static.png");
  for (const asset of ["logo-static.png", "logo-header.webp", "logo-loading.webp", "README.md"]) {
    await readFile(join(pluginRoot, "assets", "brand", asset));
  }
});

function startServer(environment = {}) {
  const child = spawn(process.execPath, [serverPath, "--stdio"], {
    env: { ...process.env, ...environment },
    stdio: ["pipe", "pipe", "pipe"],
  });
  const lines = readline.createInterface({ input: child.stdout });
  const responses = [];
  const waiters = [];
  lines.on("line", (line) => {
    const message = JSON.parse(line);
    const waiter = waiters.shift();
    if (waiter) waiter(message);
    else responses.push(message);
  });
  return {
    child,
    async send(message) {
      child.stdin.write(`${JSON.stringify(message)}\n`);
      if (responses.length) return responses.shift();
      return new Promise((resolve) => waiters.push(resolve));
    },
    async close() {
      child.stdin.end();
      if (child.exitCode === null) await once(child, "exit");
    },
  };
}

const request = (id, method, params = {}) => ({ jsonrpc: "2.0", id, method, params });

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function pngChunk(type, data) {
  const typeBytes = Buffer.from(type, "ascii");
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(Buffer.concat([typeBytes, data])));
  return Buffer.concat([length, typeBytes, data, checksum]);
}

async function writeNoisyPng(directory) {
  const width = 900;
  const height = 900;
  const pngPath = join(directory, "noise.png");
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 6;
  const rows = randomBytes((width * 4 + 1) * height);
  for (let row = 0; row < height; row += 1) rows[row * (width * 4 + 1)] = 0;
  await writeFile(pngPath, Buffer.concat([
    Buffer.from("89504e470d0a1a0a", "hex"),
    pngChunk("IHDR", header),
    pngChunk("IDAT", deflateSync(rows, { level: 1 })),
    pngChunk("IEND", Buffer.alloc(0)),
  ]));
  return pngPath;
}

test("advertises clarification, remix, retouch, creation, and design tools linked to MCP Apps UI resources", async () => {
  const server = startServer();
  try {
    const initialized = await server.send(request(1, "initialize", { protocolVersion: "2025-11-25" }));
    assert.equal(initialized.result.protocolVersion, "2025-11-25");
    assert.equal(initialized.result.serverInfo.name, "svt_jewelry_ui");
    assert.deepEqual(initialized.result.capabilities, { tools: {}, resources: {} });

    const listed = await server.send(request(2, "tools/list"));
    assert.equal(listed.result.tools.length, 10);
    const tool = listed.result.tools.find(({ name }) => name === "ask_jewelry_followup_questions");
    assert.equal(tool.name, "ask_jewelry_followup_questions");
    assert.equal(tool._meta.ui.resourceUri, "ui://svt-jewelry/followup-questions/v4.html");
    assert.equal(tool._meta["openai/outputTemplate"], tool._meta.ui.resourceUri);
    assert.equal(tool.inputSchema.properties.fields.maxItems, 4);
    assert.equal(tool.inputSchema.properties.fields.items.properties.options.maxItems, 8);
    assert.equal(tool.inputSchema.properties.fields.items.properties.options.items.properties.previewPath.type, "string");
    assert.match(tool.description, /jewelry-grill-me exception/);
    assert.match(tool.description, /at most four unresolved questions per round/);
    const comparison = listed.result.tools.find(({ name }) => name === "show_jewelry_retouch_comparison");
    assert.equal(comparison._meta.ui.resourceUri, "ui://svt-jewelry/retouch-comparison/v10.html");
    assert.equal(comparison.inputSchema.properties.pairs.maxItems, 8);
    const remixBrief = listed.result.tools.find(({ name }) => name === "ask_jewelry_remix_brief");
    assert.equal(remixBrief._meta.ui.resourceUri, "ui://svt-jewelry/remix-brief/v7.html");
    const remixGallery = listed.result.tools.find(({ name }) => name === "show_jewelry_remix_gallery");
    assert.equal(remixGallery._meta.ui.resourceUri, "ui://svt-jewelry/remix-gallery/v7.html");
    assert.deepEqual(remixGallery.inputSchema.required, ["sourcePath", "candidates"]);
    assert.deepEqual(
      remixGallery.inputSchema.properties.candidates.oneOf.map(({ minItems, maxItems }) => [minItems, maxItems]),
      [[4, 4], [8, 8]],
    );
    const creationBrief = listed.result.tools.find(({ name }) => name === "ask_jewelry_creation_brief");
    assert.equal(creationBrief._meta.ui.resourceUri, "ui://svt-jewelry/creation-brief/v4.html");
    assert.deepEqual(creationBrief.inputSchema.properties.workflow.enum, ["poster", "catalog", "display"]);
    assert.equal(creationBrief.inputSchema.properties.unresolvedFields.maxItems, 4);
    const creationGallery = listed.result.tools.find(({ name }) => name === "show_jewelry_creation_gallery");
    assert.equal(creationGallery._meta.ui.resourceUri, "ui://svt-jewelry/creation-gallery/v6.html");
    assert.deepEqual(creationGallery.inputSchema.properties.workflow.enum, ["poster", "catalog", "display", "grid", "grid_redraw", "reference_sheet", "tryon"]);
    assert.equal(creationGallery.inputSchema.properties.items.maxItems, 12);
    assert.equal(creationGallery.inputSchema.properties.sourcePath, undefined);
    const designGallery = listed.result.tools.find(({ name }) => name === "show_jewelry_design_gallery");
    assert.equal(designGallery._meta.ui.resourceUri, "ui://svt-jewelry/design-gallery/v2.html");
    assert.equal(designGallery.inputSchema.properties.items.minItems, 1);
    assert.equal(designGallery.inputSchema.properties.items.maxItems, 12);
    assert.equal(designGallery.inputSchema.properties.items.items.properties.id.pattern, "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$");
  } finally {
    await server.close();
  }
});

test("serves the ordinary design Gallery and preserves ten real runner ids", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-design-gallery-"));
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const ids = [
    "01-single-bloom", "02-twin-shoulders", "03-asymmetric-cluster", "04-half-wreath", "05-vine-wrap",
    "06-dew-flower", "07-petal-halo", "08-open-branch", "09-three-bloom-orbit", "10-seal-flower",
  ];
  const items = [];
  for (const [index, id] of ids.entries()) {
    const path = join(directory, `${id}.png`);
    await writeFile(path, pixel);
    items.push({
      id,
      title: `勿忘我戒指 ${index + 1}`,
      path,
      pieceType: "戒指",
      summary: "小轻金系列延展",
      materials: "18K 金",
      gemstones: "钻石",
      craft: "微镶工艺",
      useCase: "日常佩戴",
    });
  }
  const server = startServer();
  try {
    const resource = await server.send(request(1, "resources/read", { uri: "ui://svt-jewelry/design-gallery/v2.html" }));
    assert.equal(resource.result.contents[0]._meta.ui.prefersBorder, false);
    assert.match(resource.result.contents[0].text, /选定此图继续/);
    assert.match(resource.result.contents[0].text, /designMedia/);
    assert.match(resource.result.contents[0].text, /touch-action:\s*pan-y/);
    assert.match(resource.result.contents[0].text, /grid-template-columns:repeat\(2,58px\)/);
    assert.match(resource.result.contents[0].text, /ui\/update-model-context/);
    assert.match(resource.result.contents[0].text, /jewelryAssetSelection/);
    assert.match(resource.result.contents[0].text, /等待设计成品超时/);
    assert.match(resource.result.contents[0].text, /addEventListener\("error"/);
    assert.match(resource.result.contents[0].text, /closest\?\.\("\.design-rail,\.stage"\)/);
    assert.match(resource.result.contents[0].text, /nextButton\.focus\(\)/);
    assert.match(resource.result.contents[0].text, /等待用户下一条任务指令/);
    assert.match(resource.result.contents[0].text, /@media \(max-width:620px\)[\s\S]*?\.gallery-grid\{grid-template-columns:62px/);
    assert.match(resource.result.contents[0].text, /@media \(max-width:620px\)[\s\S]*?\.design-button\{width:60px;height:60px\}/);
    assert.doesNotMatch(resource.result.contents[0].text, /overflow-y:\s*auto/);

    const called = await server.send(request(2, "tools/call", {
      name: "show_jewelry_design_gallery",
      arguments: { title: "10 款小轻金勿忘我戒指", initialDesignId: ids[8], items },
    }));
    assert.equal(called.result.isError, undefined);
    assert.deepEqual(called.result.structuredContent.designGallery.items.map(({ id }) => id), ids);
    assert.equal(called.result.structuredContent.designGallery.initialDesignId, ids[8]);
    assert.equal(JSON.stringify(called.result.structuredContent).includes("base64"), false);
    assert.deepEqual(Object.keys(called.result._meta.designMedia.items), ids);
    assert.ok(JSON.stringify(called.result._meta.designMedia).length <= 720 * 1024);
    assert.equal(called.result._meta.ui.resourceUri, "ui://svt-jewelry/design-gallery/v2.html");
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("accepts one to twelve ordinary designs and rejects unstable or incomplete design galleries", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-design-gallery-validation-"));
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const path = join(directory, "design.png");
  await writeFile(path, pixel);
  const makeItems = (count) => Array.from({ length: count }, (_, index) => ({
    id: `${String(index + 1).padStart(2, "0")}-design`, title: `设计 ${index + 1}`, path,
  }));
  const server = startServer();
  try {
    for (const count of [1, 4, 8, 12]) {
      const called = await server.send(request(count, "tools/call", {
        name: "show_jewelry_design_gallery", arguments: { items: makeItems(count) },
      }));
      assert.equal(called.result.isError, undefined);
      assert.equal(called.result.structuredContent.designGallery.items.length, count);
    }
    for (const [id, items, pattern] of [
      [20, [], /1 to 12/],
      [21, makeItems(13), /1 to 12/],
      [22, [{ id: "../escape", title: "bad", path }], /stable/],
      [23, [{ id: `A${"x".repeat(64)}`, title: "long", path }], /64/],
      [24, [{ id: "01-design", title: "one", path }, { id: "01-design", title: "two", path }], /unique/],
      [25, [{ id: "01-design", title: "missing", path: join(directory, "missing.png") }], /ENOENT|no such file/],
    ]) {
      const called = await server.send(request(id, "tools/call", {
        name: "show_jewelry_design_gallery", arguments: { items },
      }));
      assert.equal(called.result.isError, true);
      assert.match(called.result.content[0].text, pattern);
    }
    const malformedInitial = await server.send(request(26, "tools/call", {
      name: "show_jewelry_design_gallery", arguments: { initialDesignId: "../escape", items: makeItems(1) },
    }));
    assert.equal(malformedInitial.result.isError, true);
    assert.match(malformedInitial.result.content[0].text, /initialDesignId/);
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("returns a normalized remix brief with stable defaults and text fallback", async () => {
  const server = startServer();
  try {
    const called = await server.send(request(1, "tools/call", {
      name: "ask_jewelry_remix_brief",
      arguments: {
        title: "确认爆款二创方向",
        hasReferenceImages: true,
        defaults: {
          count: 8,
          designSystem: "gold",
          structureFidelity: "high",
          themes: ["oriental-totem"],
        },
      },
    }));
    const brief = called.result.structuredContent.remixBrief;
    assert.equal(brief.count, 8);
    assert.equal(brief.schemaVersion, 2);
    assert.equal(brief.designSystem, "gold");
    assert.equal(brief.structureFidelity, "high");
    assert.equal(brief.intensity, "balanced");
    assert.equal(brief.hasReferenceImages, true);
    assert.deepEqual(brief.themes, ["oriental-totem"]);
    assert.match(called.result.content[0].text, /4 或 8/);
    assert.equal(called.result._meta.ui.resourceUri, "ui://svt-jewelry/remix-brief/v7.html");
  } finally {
    await server.close();
  }
});

test("returns normalized structured form data and a model-readable fallback", async () => {
  const server = startServer();
  try {
    const called = await server.send(request(1, "tools/call", {
      name: "ask_jewelry_followup_questions",
      arguments: {
        title: "确认戒指方向",
        prompt: "只确认会改变产品身份的选择。",
        fields: [
          {
            id: "jewelry_type",
            label: "首饰类型",
            type: "single",
            required: true,
            options: [
              { id: "ring", label: "戒指" },
              { id: "necklace", label: "项链" },
            ],
          },
          { id: "hero_material", label: "主石", type: "text", placeholder: "例如皇家蓝蓝宝石" },
        ],
      },
    }));
    assert.equal(called.result.isError, undefined);
    assert.equal(called.result.structuredContent.form.title, "确认戒指方向");
    assert.match(called.result.structuredContent.form.formId, /^[0-9a-f-]{36}$/);
    assert.match(called.result.content[0].text, /首饰类型（必填）：戒指 \/ 项链/);
    assert.equal(called.result._meta.ui.resourceUri, "ui://svt-jewelry/followup-questions/v4.html");
  } finally {
    await server.close();
  }
});

test("serves a compact adaptive MCP Apps form with standard and compatibility bridges", async () => {
  const server = startServer();
  try {
    const read = await server.send(request(1, "resources/read", {
      uri: "ui://svt-jewelry/followup-questions/v4.html",
    }));
    const resource = read.result.contents[0];
    assert.equal(resource.mimeType, "text/html;profile=mcp-app");
    assert.match(resource.text, /ui\/initialize/);
    assert.match(resource.text, /ui\/notifications\/tool-input/);
    assert.match(resource.text, /ui\/notifications\/tool-result/);
    assert.match(resource.text, /ui\/message/);
    assert.match(resource.text, /sendFollowUpMessage/);
    assert.match(resource.text, /overflow:\s*hidden/);
    assert.match(resource.text, /compact-select/);
    assert.match(resource.text, /visual-options/);
    assert.match(resource.text, /overflow-x:\s*auto/);
    assert.match(resource.text, /image\.alt\s*=\s*option\.label/);
    assert.match(resource.text, /form\.fields\.length\s*>=\s*3/);
    assert.match(resource.text, /extractEnvelope/);
    assert.match(resource.text, /main\.getBoundingClientRect\(\)\.height/);
    assert.doesNotMatch(resource.text, /overflow-y:\s*auto/);
    assert.doesNotMatch(resource.text, /\.shell\s*\{[^}]*border:/s);
    assert.doesNotMatch(resource.text, /Design Intake/);
    assert.match(resource.text, /option input:checked[^}]*background:\s*#171717[^}]*color:\s*#fff/s);
    assert.match(resource.text, /\.submit[^}]*background:\s*#171717/s);
    assert.equal(resource._meta.ui.prefersBorder, false);
  } finally {
    await server.close();
  }
});

test("bounds generic clarification to four fields and eight options", async () => {
  const server = startServer();
  try {
    const makeField = (index, optionCount = 2) => ({
      id: `field_${index}`,
      label: `字段 ${index}`,
      type: "single",
      options: Array.from({ length: optionCount }, (_, optionIndex) => ({
        id: `option_${optionIndex}`,
        label: `选项 ${optionIndex}`,
      })),
    });
    const tooManyFields = await server.send(request(1, "tools/call", {
      name: "ask_jewelry_followup_questions",
      arguments: { title: "过多字段", fields: Array.from({ length: 5 }, (_, index) => makeField(index)) },
    }));
    assert.equal(tooManyFields.result.isError, true);
    assert.match(tooManyFields.result.content[0].text, /1 to 4/);

    const tooManyOptions = await server.send(request(2, "tools/call", {
      name: "ask_jewelry_followup_questions",
      arguments: { title: "过多选项", fields: [makeField(1, 9)] },
    }));
    assert.equal(tooManyOptions.result.isError, true);
    assert.match(tooManyOptions.result.content[0].text, /2 to 8/);
  } finally {
    await server.close();
  }
});

test("keeps multi-image choice previews UI-only under one shared form budget", async () => {
  const server = startServer();
  try {
    const preview = "data:image/png;base64,iVBORw0KGgo=";
    const called = await server.send(request(1, "tools/call", {
      name: "ask_jewelry_followup_questions",
      arguments: {
        title: "选择视觉方向",
        fields: [{
          id: "visual_direction",
          label: "视觉方向",
          type: "single",
          required: true,
          options: Array.from({ length: 4 }, (_, index) => ({
            id: `visual_${index + 1}`,
            label: `方向 ${index + 1}`,
            preview,
          })),
        }],
      },
    }));
    assert.equal(called.result.isError, undefined);
    assert.equal(JSON.stringify(called.result.structuredContent).includes("base64"), false);
    assert.equal(Object.keys(called.result._meta.formMedia.visual_direction).length, 4);
    assert.ok(JSON.stringify(called.result._meta.formMedia).length <= 720 * 1024);
  } finally {
    await server.close();
  }
});

test("prepares real local visual-choice images as bounded UI-only previews", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-followup-visual-"));
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const paths = [];
  for (let index = 0; index < 4; index += 1) {
    const path = join(directory, `visual-${index + 1}.png`);
    await writeFile(path, pixel);
    paths.push(path);
  }
  const server = startServer();
  try {
    const called = await server.send(request(1, "tools/call", {
      name: "ask_jewelry_followup_questions",
      arguments: {
        title: "选择真实珠宝方向",
        fields: [{
          id: "visual_direction",
          label: "视觉方向",
          type: "single",
          required: true,
          options: paths.map((previewPath, index) => ({
            id: `visual_${index + 1}`,
            label: `方向 ${index + 1}`,
            previewPath,
          })),
        }],
      },
    }));
    assert.equal(called.result.isError, undefined);
    assert.equal(JSON.stringify(called.result.structuredContent).includes(directory), false);
    const previews = Object.values(called.result._meta.formMedia.visual_direction);
    assert.equal(previews.length, 4);
    assert.ok(previews.every((preview) => preview.startsWith("data:image/png;base64,")));
    assert.ok(JSON.stringify(called.result._meta.formMedia).length <= 720 * 1024);
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("returns compact UI-only preview media with model-readable fallback paths", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-retouch-compare-"));
  const beforePath = join(directory, "before.png");
  const afterPath = join(directory, "after.png");
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  await writeFile(beforePath, pixel);
  await writeFile(afterPath, pixel);
  const server = startServer();
  try {
    const called = await server.send(request(1, "tools/call", {
      name: "show_jewelry_retouch_comparison",
      arguments: {
        beforePath,
        afterPath,
        title: "蓝宝石戒指精修对比",
        initialPosition: 42,
      },
    }));
    assert.equal(called.result.structuredContent.comparison.title, "蓝宝石戒指精修对比");
    assert.equal(called.result.structuredContent.comparison.initialPosition, 42);
    assert.equal(called.result.structuredContent.comparison.before.path, beforePath);
    assert.equal(called.result.structuredContent.comparison.after.path, afterPath);
    assert.equal(JSON.stringify(called.result.structuredContent).includes("base64"), false);
    assert.equal(called.result.content.length, 1);
    assert.match(called.result._meta.comparisonMedia.before, /^data:image\/png;base64,/);
    assert.match(called.result._meta.comparisonMedia.after, /^data:image\/png;base64,/);
    assert.match(called.result.content[0].text, new RegExp(beforePath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    assert.equal(called.result._meta.ui.resourceUri, "ui://svt-jewelry/retouch-comparison/v10.html");
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("serves the draggable retouch comparison UI and rejects missing image paths", async () => {
  const server = startServer();
  try {
    const read = await server.send(request(1, "resources/read", {
      uri: "ui://svt-jewelry/retouch-comparison/v10.html",
    }));
    const resource = read.result.contents[0];
    assert.equal(resource.mimeType, "text/html;profile=mcp-app");
    assert.match(resource.text, /type="range"/);
    assert.match(resource.text, /ui\/initialize/);
    assert.match(resource.text, /ui\/notifications\/tool-result/);
    assert.match(resource.text, /comparisonMedia/);
    assert.match(resource.text, /comparisonMedia/);
    assert.match(resource.text, /JSON\.parse/);
    assert.match(resource.text, /clip-path/);
    assert.match(resource.text, /overflow-y:\s*hidden/);
    assert.match(resource.text, /height:\s*clamp\(400px,\s*50vw,\s*560px\)/);
    assert.match(resource.text, /querySelector\("main"\)\.getBoundingClientRect\(\)\.height/);
    assert.match(resource.text, /苏哇科技/);
    assert.match(resource.text, /RETOUCH-/);
    assert.match(resource.text, /class="pair-rail"/);
    assert.match(resource.text, /comparison-grid\.single/);
    assert.match(resource.text, /grid-auto-rows:\s*68px/);
    assert.match(resource.text, /pair-rail\.dense[^}]*grid-template-columns:repeat\(2,58px\)[^}]*grid-auto-rows:58px/s);
    assert.match(resource.text, /选定精修图继续/);
    assert.match(resource.text, /ui\/update-model-context/);
    assert.match(resource.text, /dense=active\.pairs\.length>5/);
    assert.match(resource.text, /clip-path:\s*inset\(0 0 0 var\(--position\)\)/);
    assert.match(resource.text, /value\.isError/);
    assert.match(resource.text, /function showError/);
    assert.match(resource.text, /等待精修对比超时/);
    assert.match(resource.text, /pairs\.length===rawPairs\.length/);
    assert.match(resource.text, /prefers-reduced-motion/);
    assert.equal(resource._meta.ui.prefersBorder, false);

    const missing = await server.send(request(2, "tools/call", {
      name: "show_jewelry_retouch_comparison",
      arguments: { beforePath: "/missing/before.png", afterPath: "/missing/after.png" },
    }));
    assert.equal(missing.result.isError, true);
    assert.match(missing.result.content[0].text, /Unable to render jewelry UI/);
  } finally {
    await server.close();
  }
});

test("serves compact remix UIs without nested host-style borders", async () => {
  const server = startServer();
  try {
    const briefRead = await server.send(request(1, "resources/read", {
      uri: "ui://svt-jewelry/remix-brief/v7.html",
    }));
    const briefResource = briefRead.result.contents[0];
    assert.match(briefResource.text, /变化控制/);
    assert.match(briefResource.text, /设计语言/);
    assert.match(briefResource.text, /ui\/message/);
    assert.match(briefResource.text, /Current jewelry remix brief \(JSON\)/);
    assert.match(briefResource.text, /const form = event\.currentTarget/);
    assert.doesNotMatch(briefResource.text, /event\.currentTarget\.querySelectorAll/);
    assert.match(briefResource.text, /产品体系/);
    assert.match(briefResource.text, /designSystems/);
    assert.match(briefResource.text, /点缀珐琅/);
    assert.doesNotMatch(briefResource.text, /REMIX_TAXONOMY_JSON/);
    assert.doesNotMatch(briefResource.text, /点缀珐瑯/);
    assert.match(briefResource.text, /customThemes/);
    assert.match(briefResource.text, /overflow-y:\s*hidden/);
    assert.match(briefResource.text, /resize:\s*none/);
    assert.match(briefResource.text, /max-width:\s*360px/);
    assert.match(briefResource.text, /input:focus-visible\s*\+\s*span/);
    assert.match(briefResource.text, /苏哇科技/);
    assert.match(briefResource.text, /button[^}]*background:\s*#171717[^}]*color:\s*#fff/s);
    assert.equal(briefResource._meta.ui.prefersBorder, false);

    const galleryRead = await server.send(request(2, "resources/read", {
      uri: "ui://svt-jewelry/remix-gallery/v7.html",
    }));
    const galleryResource = galleryRead.result.contents[0];
    assert.match(galleryResource.text, /type="range"/);
    assert.match(galleryResource.text, /galleryMedia/);
    assert.match(galleryResource.text, /JSON\.parse/);
    assert.match(galleryResource.text, /选定此图继续/);
    assert.match(galleryResource.text, /ui\/message/);
    assert.match(galleryResource.text, /const context = \{ assetId: item\.id, sourceWorkflow: "remix" \}/);
    assert.match(galleryResource.text, /ui\/update-model-context/);
    assert.match(galleryResource.text, /event\.target === document\.querySelector\("#slider"\)/);
    assert.match(galleryResource.text, /class="gallery-grid"/);
    assert.match(galleryResource.text, /grid-template-columns:\s*70px\s+minmax\(0,\s*650px\)\s+minmax\(180px,\s*200px\)/);
    assert.match(galleryResource.text, /grid-auto-rows:\s*68px/);
    assert.match(galleryResource.text, /thumbs\.dense[^}]*grid-template-columns:\s*repeat\(2,\s*58px\)[^}]*grid-auto-rows:\s*58px/s);
    assert.match(galleryResource.text, /dense = gallery\.candidates\.length > 5/);
    assert.match(galleryResource.text, /\.select[^}]*background:\s*#171717[^}]*color:\s*#fff/s);
    assert.match(galleryResource.text, /overflow-y:\s*hidden/);
    assert.doesNotMatch(galleryResource.text, /overflow-y:\s*auto/);
    assert.match(galleryResource.text, /touch-action:\s*pan-y/);
    assert.doesNotMatch(galleryResource.text, /touch-action:\s*none/);
    assert.match(galleryResource.text, /height:\s*clamp\(400px,\s*50vw,\s*560px\)/);
    assert.match(galleryResource.text, /range.*:focus-visible/);
    assert.match(galleryResource.text, /value\.isError/);
    assert.match(galleryResource.text, /function showError/);
    assert.match(galleryResource.text, /等待二创 Gallery 超时/);
    assert.match(galleryResource.text, /every\(item\s*=>\s*media\.candidates\[item\.id\]\)/);
    assert.match(galleryResource.text, /document\.querySelector\("main"\)\.getBoundingClientRect\(\)\.height/);
    assert.match(galleryResource.text, /苏哇科技/);
    assert.equal(galleryResource._meta.ui.prefersBorder, false);
  } finally {
    await server.close();
  }
});

test("returns an eight-candidate remix gallery with one shared source preview", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-remix-gallery-eight-"));
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const sourcePath = join(directory, "source.png");
  await writeFile(sourcePath, pixel);
  const candidates = [];
  for (const letter of "ABCDEFGH") {
    const path = join(directory, `REMIX-${letter}.png`);
    await writeFile(path, pixel);
    candidates.push({ id: `REMIX-${letter}`, title: `方案 ${letter}`, path, summary: `方向 ${letter}`, useCase: "系列延展" });
  }
  const server = startServer();
  try {
    const called = await server.send(request(1, "tools/call", {
      name: "show_jewelry_remix_gallery",
      arguments: { sourcePath, candidates },
    }));
    assert.equal(called.result.structuredContent.gallery.candidates.length, 8);
    assert.equal(Object.keys(called.result._meta.galleryMedia).filter((key) => key === "source").length, 1);
    assert.deepEqual(Object.keys(called.result._meta.galleryMedia.candidates), [..."ABCDEFGH"].map((letter) => `REMIX-${letter}`));
    assert.ok(JSON.stringify(called.result._meta.galleryMedia).length <= 720 * 1024);
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("compresses oversized gallery previews and rejects payloads that still exceed the budget", {
  skip: process.platform !== "darwin",
}, async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-remix-gallery-budget-"));
  const imagePath = await writeNoisyPng(directory);
  const candidates = [..."ABCD"].map((letter) => ({
    id: `REMIX-${letter}`,
    title: `方案 ${letter}`,
    path: imagePath,
  }));
  const server = startServer();
  try {
    const called = await server.send(request(1, "tools/call", {
      name: "show_jewelry_remix_gallery",
      arguments: { sourcePath: imagePath, candidates },
    }));
    assert.equal(called.result.isError, undefined);
    const previews = [
      called.result._meta.galleryMedia.source,
      ...Object.values(called.result._meta.galleryMedia.candidates),
    ];
    assert.ok(previews.every((preview) => preview.startsWith("data:image/jpeg;base64,")));
    assert.ok(previews.reduce((total, preview) => total + preview.length, 0) <= 720 * 1024);
  } finally {
    await server.close();
  }

  const constrained = startServer({ SVT_JEWELRY_UI_PREVIEW_BUDGET_CHARS: "1000" });
  try {
    const rejected = await constrained.send(request(2, "tools/call", {
      name: "show_jewelry_remix_gallery",
      arguments: { sourcePath: imagePath, candidates },
    }));
    assert.equal(rejected.result.isError, true);
    assert.match(rejected.result.content[0].text, /payload limit/);
  } finally {
    await constrained.close();
    await rm(directory, { recursive: true });
  }
});

test("returns a four-candidate remix gallery with UI-only media", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-remix-gallery-"));
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const sourcePath = join(directory, "source.png");
  await writeFile(sourcePath, pixel);
  const candidates = [];
  for (const letter of "ABCD") {
    const path = join(directory, `REMIX-${letter}.png`);
    await writeFile(path, pixel);
    candidates.push({
      id: `REMIX-${letter}`,
      title: `方案 ${letter}`,
      path,
      summary: `差异化方向 ${letter}`,
      useCase: "系列延展",
    });
  }

  const server = startServer();
  try {
    const called = await server.send(request(1, "tools/call", {
      name: "show_jewelry_remix_gallery",
      arguments: { sourcePath, candidates },
    }));
    const gallery = called.result.structuredContent.gallery;
    assert.equal(gallery.candidates.length, 4);
    assert.equal(gallery.source.path, sourcePath);
    assert.equal(JSON.stringify(called.result.structuredContent).includes("base64"), false);
    assert.match(called.result._meta.galleryMedia.source, /^data:image\/png;base64,/);
    assert.deepEqual(Object.keys(called.result._meta.galleryMedia.candidates), ["REMIX-A", "REMIX-B", "REMIX-C", "REMIX-D"]);
    assert.ok(JSON.stringify(called.result._meta.galleryMedia).length <= 720 * 1024);
    assert.equal(called.result._meta.ui.resourceUri, "ui://svt-jewelry/remix-gallery/v7.html");
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("returns stable multi-image retouch pairs under one preview budget", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-retouch-multi-"));
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const pairs = [];
  for (const letter of "ABC") {
    const beforePath = join(directory, `before-${letter}.png`);
    const afterPath = join(directory, `after-${letter}.png`);
    await writeFile(beforePath, pixel);
    await writeFile(afterPath, pixel);
    pairs.push({ id: `RETOUCH-${letter}`, title: `精修 ${letter}`, beforePath, afterPath });
  }
  const server = startServer();
  try {
    const called = await server.send(request(1, "tools/call", {
      name: "show_jewelry_retouch_comparison",
      arguments: { pairs, initialPairId: "RETOUCH-B" },
    }));
    assert.equal(called.result.structuredContent.comparison.pairs.length, 3);
    assert.equal(called.result.structuredContent.comparison.initialPairId, "RETOUCH-B");
    assert.deepEqual(Object.keys(called.result._meta.comparisonMedia.pairs), ["RETOUCH-A", "RETOUCH-B", "RETOUCH-C"]);
    assert.equal(JSON.stringify(called.result.structuredContent).includes("base64"), false);
    assert.ok(JSON.stringify(called.result._meta.comparisonMedia).length <= 720 * 1024);
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("normalizes tailored poster, catalog, and display creation briefs", async () => {
  const server = startServer();
  try {
    const workflows = [
      ["poster", "editorial_board", "composition"],
      ["catalog", "core_five", "channel"],
      ["display", "editorial_still_life", "sceneIntensity"],
    ];
    for (let index = 0; index < workflows.length; index += 1) {
      const [workflow, mode, unresolvedField] = workflows[index];
      const called = await server.send(request(index + 1, "tools/call", {
        name: "ask_jewelry_creation_brief",
        arguments: { workflow, hasSourceImages: true, unresolvedFields: [unresolvedField], defaults: { mode, aspectRatio: "3:4" } },
      }));
      assert.equal(called.result.structuredContent.creationBrief.workflow, workflow);
      assert.equal(called.result.structuredContent.creationBrief.mode, mode);
      assert.equal(called.result.structuredContent.creationBrief.aspectRatio, "3:4");
      assert.deepEqual(called.result.structuredContent.creationBrief.unresolvedFields, [unresolvedField]);
      assert.match(called.result.content[0].text, new RegExp(workflow));
    }
  } finally {
    await server.close();
  }
});

test("serves branded creation brief and gallery UIs and returns UI-only gallery media", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-creation-gallery-"));
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const items = [];
  for (let index = 1; index <= 3; index += 1) {
    const path = join(directory, `poster-${index}.png`);
    await writeFile(path, pixel);
    items.push({ id: `POSTER-${String(index).padStart(2, "0")}`, title: `海报 ${index}`, path, summary: "编辑式版面", useCase: "品牌传播" });
  }
  const server = startServer();
  try {
    const brief = await server.send(request(1, "resources/read", { uri: "ui://svt-jewelry/creation-brief/v4.html" }));
    assert.match(brief.result.contents[0].text, /海报/);
    assert.match(brief.result.contents[0].text, /画册/);
    assert.match(brief.result.contents[0].text, /展示/);
    assert.match(brief.result.contents[0].text, /Current jewelry creation brief \(JSON\)/);
    assert.match(brief.result.contents[0].text, /visibleFields/);
    assert.match(brief.result.contents[0].text, /苏哇科技/);
    assert.match(brief.result.contents[0].text, /button[^}]*background:#171717[^}]*color:#fff/s);
    assert.match(brief.result.contents[0].text, /value\.isError/);
    assert.match(brief.result.contents[0].text, /function showError/);
    assert.match(brief.result.contents[0].text, /等待创作表单超时/);
    assert.equal(brief.result.contents[0]._meta.ui.prefersBorder, false);

    const galleryResource = await server.send(request(2, "resources/read", { uri: "ui://svt-jewelry/creation-gallery/v6.html" }));
    assert.match(galleryResource.result.contents[0].text, /class="asset-rail"/);
    assert.match(galleryResource.result.contents[0].text, /选定此图继续/);
    assert.match(galleryResource.result.contents[0].text, /touch-action:\s*pan-y/);
    assert.match(galleryResource.result.contents[0].text, /gallery-grid\.single/);
    assert.match(galleryResource.result.contents[0].text, /grid-auto-rows:68px/);
    assert.match(galleryResource.result.contents[0].text, /asset-rail\.dense[^}]*grid-template-columns:repeat\(2,58px\)[^}]*grid-auto-rows:58px/s);
    assert.match(galleryResource.result.contents[0].text, /ui\/update-model-context/);
    assert.match(galleryResource.result.contents[0].text, /jewelryAssetSelection/);
    assert.match(galleryResource.result.contents[0].text, /dense=active\.items\.length>5/);
    assert.match(galleryResource.result.contents[0].text, /value\.isError/);
    assert.match(galleryResource.result.contents[0].text, /function showError/);
    assert.match(galleryResource.result.contents[0].text, /等待视觉成品超时/);
    assert.match(galleryResource.result.contents[0].text, /items\.length!==gallery\.items\.length/);
    assert.match(galleryResource.result.contents[0].text, /gallery\.items\.length===0/);
    assert.match(galleryResource.result.contents[0].text, /\.select[^}]*background:#171717; color:#fff/s);
    assert.doesNotMatch(galleryResource.result.contents[0].text, /overflow-y:\s*auto/);

    const called = await server.send(request(3, "tools/call", {
      name: "show_jewelry_creation_gallery",
      arguments: { workflow: "poster", items },
    }));
    assert.equal(called.result.structuredContent.creationGallery.items.length, 3);
    assert.deepEqual(Object.keys(called.result._meta.creationMedia.items), items.map(({ id }) => id));
    assert.equal(called.result._meta.creationMedia.source, undefined);
    assert.equal(JSON.stringify(called.result.structuredContent).includes("base64"), false);
    assert.ok(JSON.stringify(called.result._meta.creationMedia).length <= 720 * 1024);

    const single = await server.send(request(4, "tools/call", {
      name: "show_jewelry_creation_gallery",
      arguments: { workflow: "poster", items: [items[0]] },
    }));
    assert.equal(single.result.structuredContent.creationGallery.items.length, 1);
    assert.deepEqual(Object.keys(single.result._meta.creationMedia.items), ["POSTER-01"]);
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("preserves workflow-prefixed creation asset ids across split galleries", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-creation-stable-ids-"));
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const ids = ["POSTER-P01-A", "POSTER-P01-B", "POSTER-P02-A"];
  const items = [];
  for (const id of ids) {
    const path = join(directory, `${id}.png`);
    await writeFile(path, pixel);
    items.push({ id, title: id, path });
  }
  const server = startServer();
  try {
    const called = await server.send(request(1, "tools/call", {
      name: "show_jewelry_creation_gallery",
      arguments: { workflow: "poster", initialAssetId: "POSTER-P02-A", items },
    }));
    assert.equal(called.result.isError, undefined);
    assert.deepEqual(called.result.structuredContent.creationGallery.items.map(({ id }) => id), ids);
    assert.equal(called.result.structuredContent.creationGallery.initialAssetId, "POSTER-P02-A");

    const duplicate = await server.send(request(2, "tools/call", {
      name: "show_jewelry_creation_gallery",
      arguments: { workflow: "poster", items: [items[0], items[0]] },
    }));
    assert.equal(duplicate.result.isError, true);
    assert.match(duplicate.result.content[0].text, /unique/);

    const wrongPrefix = await server.send(request(3, "tools/call", {
      name: "show_jewelry_creation_gallery",
      arguments: { workflow: "catalog", items: [items[0]] },
    }));
    assert.equal(wrongPrefix.result.isError, true);
    assert.match(wrongPrefix.result.content[0].text, /CATALOG/);

    const wrongInitialPrefix = await server.send(request(4, "tools/call", {
      name: "show_jewelry_creation_gallery",
      arguments: { workflow: "poster", initialAssetId: "CATALOG-SKU-01", items },
    }));
    assert.equal(wrongInitialPrefix.result.isError, true);
    assert.match(wrongInitialPrefix.result.content[0].text, /initialAssetId/);

    const overlongId = `POSTER-${"A".repeat(58)}`;
    const overlong = await server.send(request(5, "tools/call", {
      name: "show_jewelry_creation_gallery",
      arguments: { workflow: "poster", items: [{ ...items[0], id: overlongId }] },
    }));
    assert.equal(overlong.result.isError, true);
    assert.match(overlong.result.content[0].text, /64/);
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("uses the shared creation Gallery for grid, redraw, and reference-sheet outputs", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-creation-coverage-"));
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const server = startServer();
  try {
    const workflows = [
      ["grid", "GRID", 1],
      ["grid_redraw", "REDRAW", 9],
      ["reference_sheet", "SHEET", 12],
      ["tryon", "TRYON", 2],
    ];
    for (const [index, [workflow, prefix, count]] of workflows.entries()) {
      const items = [];
      for (let itemIndex = 1; itemIndex <= count; itemIndex += 1) {
        const id = `${prefix}-${String(itemIndex).padStart(2, "0")}`;
        const path = join(directory, `${id}.png`);
        await writeFile(path, pixel);
        items.push({ id, title: id, path });
      }
      const called = await server.send(request(index + 1, "tools/call", {
        name: "show_jewelry_creation_gallery",
        arguments: { workflow, items },
      }));
      assert.equal(called.result.isError, undefined);
      assert.equal(called.result.structuredContent.creationGallery.workflow, workflow);
      assert.equal(called.result.structuredContent.creationGallery.items.length, count);
      assert.deepEqual(Object.keys(called.result._meta.creationMedia.items), items.map(({ id }) => id));
    }
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("rejects incomplete or unstable remix galleries", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-remix-invalid-"));
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const sourcePath = join(directory, "source.png");
  await writeFile(sourcePath, pixel);
  const server = startServer();
  try {
    const partial = await server.send(request(1, "tools/call", {
      name: "show_jewelry_remix_gallery",
      arguments: { sourcePath, candidates: [] },
    }));
    assert.equal(partial.result.isError, true);
    assert.match(partial.result.content[0].text, /4 or 8/);
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("rejects ambiguous field ids and malformed choice fields", async () => {
  const server = startServer();
  try {
    const duplicate = await server.send(request(1, "tools/call", {
      name: "ask_jewelry_followup_questions",
      arguments: {
        title: "重复字段",
        fields: [
          { id: "style", label: "风格一", type: "text" },
          { id: "style", label: "风格二", type: "text" },
        ],
      },
    }));
    assert.equal(duplicate.result.isError, true);
    assert.match(duplicate.result.content[0].text, /duplicate field id/);

    const missingOptions = await server.send(request(2, "tools/call", {
      name: "ask_jewelry_followup_questions",
      arguments: { title: "缺少选项", fields: [{ id: "style", label: "风格", type: "single" }] },
    }));
    assert.equal(missingOptions.result.isError, true);
    assert.match(missingOptions.result.content[0].text, /at least two options/);
  } finally {
    await server.close();
  }
});

test("advertises the shared visual workbench for local editing and model try-on", async () => {
  const server = startServer();
  try {
    const listed = await server.send(request(1, "tools/list"));
    assert.equal(listed.result.tools.length, 10);
    const local = listed.result.tools.find(({ name }) => name === "open_jewelry_local_editor");
    const tryon = listed.result.tools.find(({ name }) => name === "open_jewelry_tryon_editor");
    const save = listed.result.tools.find(({ name }) => name === "save_jewelry_visual_draft");
    assert.equal(local._meta.ui.resourceUri, "ui://svt-jewelry/visual-workbench/v6.html");
    assert.equal(tryon._meta.ui.resourceUri, local._meta.ui.resourceUri);
    assert.equal(save._meta, undefined);
    assert.deepEqual(local.inputSchema.properties.mode.enum, ["local_edit", "put_here", "sketch_design"]);
    assert.deepEqual(local.inputSchema.required, ["workspacePath", "mode", "category"]);
    assert.deepEqual(local.inputSchema.properties.category.enum, ["ring", "bracelet", "necklace", "pendant", "earrings", "brooch", "other"]);
    assert.deepEqual(tryon.inputSchema.properties.category.enum, ["ring", "bracelet", "necklace", "pendant", "earrings", "brooch"]);

    const resource = await server.send(request(2, "resources/read", { uri: local._meta.ui.resourceUri }));
    const html = resource.result.contents[0].text;
    assert.equal(resource.result.contents[0]._meta.ui.prefersBorder, false);
    assert.match(html, /requestDisplayMode/);
    assert.match(html, /save_jewelry_visual_draft/);
    assert.match(html, /ui\/notifications\/tool-result/);
    assert.match(html, /window\.openai/);
    assert.match(html, /function nestedMedia/);
    assert.match(html, /function toolError/);
    assert.match(html, /function missingVisualMedia/);
    assert.match(html, /视觉素材数据不完整/);
    assert.match(html, /wrappedError/);
    assert.match(html, /touch-action:pan-y/);
    assert.match(html, /\.fullscreen[\s\S]*touch-action:none/);
    assert.match(html, /getImageData/);
    assert.match(html, /putImageData/);
    assert.match(html, /自动抠图/);
    assert.match(html, /边界连通抠图/);
    assert.match(html, /annotationInstruction/);
    assert.match(html, /el\.onpointerdown=event=>event\.stopPropagation/);
    assert.match(html, /el\.onclick=event=>\{event\.stopPropagation\(\);selectAnnotation/);
    assert.match(html, /el\.onkeydown=/);
    assert.match(html, /customCategory/);
    assert.match(html, /cutoutPreviewDataUrl/);
    assert.match(html, /画笔/);
    assert.match(html, /锚点/);
    assert.match(html, /空白画板已就绪/);
    assert.match(html, /terminalLoading/);
    assert.match(html, /素材载入失败/);
    assert.match(html, /等待视觉工作台数据超时/);
    assert.match(html, /cutoutLocked/);
    assert.match(html, /minimumCluster/);
    assert.doesNotMatch(html, /trimSeed/);
    assert.doesNotMatch(html, /const visited=/);
    assert.match(html, /annotationTool&&annotations\.length>=8/);
    assert.match(html, /\.drawer \.group\{padding-bottom:5px\}/);
    assert.match(html, /\.drawer\.annotation-mode \.transform-group\{display:none\}/);
    assert.match(html, /active\.source\?\{sourcePath/);
    assert.match(html, /transform/);
    assert.match(html, /苏哇科技/);
    assert.doesNotMatch(html, /overflow-y:\s*auto/);
  } finally {
    await server.close();
  }
});

test("visual workbench terminates direct and wrapped errors and rejects incomplete media", async () => {
  const html = await readFile(join(pluginRoot, "mcp", "jewelry-visual-workbench.html"), "utf8");
  const toolError = extractedFunction(html, "toolError");
  const missingVisualMedia = extractedFunction(html, "missingVisualMedia");
  const normalizedWorkbench = extractedFunction(html, "normalizedWorkbench");
  assert.equal(toolError({ isError: true, content: [{ type: "text", text: "直接失败" }] }), "直接失败");
  assert.equal(toolError({ content: [{ type: "text", text: JSON.stringify({ isError: true, content: [{ type: "text", text: "包装失败" }] }) }] }), "包装失败");
  assert.equal(missingVisualMedia({ workflow: "local_edit", source: { path: "source.png" } }, {}), true);
  assert.equal(missingVisualMedia({ workflow: "local_edit", stone: { path: "stone.png" } }, { stone: "data:image/png;base64,x" }), false);
  assert.equal(missingVisualMedia({ workflow: "tryon" }, { model: "data:image/png;base64,x" }), true);
  assert.equal(missingVisualMedia({ workflow: "tryon" }, { model: "x", jewelry: "y" }), false);
  assert.equal(missingVisualMedia({ workflow: "local_edit", referenceImages: [{ path: "ref.png" }] }, {}), true);
  assert.equal(missingVisualMedia({ workflow: "local_edit", referenceImages: [{ path: "ref.png" }] }, { references: { "REF-1": "x" } }), false);
  assert.equal(normalizedWorkbench({ mode: "local_edit", category: "ring" }), false);
  assert.equal(normalizedWorkbench({ mode: "sketch_design", category: "ring" }), false);
  assert.equal(normalizedWorkbench({ category: "earrings", modelPath: "model.png" }), false);
  assert.equal(normalizedWorkbench({ sessionId: "LOCAL-1234", workflow: "local_edit" }), true);
  assert.equal(normalizedWorkbench({ sessionId: "TRYON-1234", workflow: "tryon" }), true);
});

test("renders both visual workflows and saves only workspace-local draft assets", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-visual-workbench-"));
  const workspace = join(directory, "artifacts", "runs", "visual-test");
  const references = join(workspace, "references");
  await mkdir(references, { recursive: true });
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const sourcePath = join(references, "source.png");
  const stonePath = join(references, "stone.png");
  const modelPath = join(references, "model.png");
  await writeFile(sourcePath, pixel);
  await writeFile(stonePath, pixel);
  await writeFile(modelPath, pixel);
  const server = startServer();
  try {
    const local = await server.send(request(1, "tools/call", {
      name: "open_jewelry_local_editor",
      arguments: {
        workspacePath: workspace,
        sourcePath,
        stonePath,
        mode: "sketch_design",
        category: "ring",
        defaults: { instruction: "围绕主石绘制戒肩", preserve: "主石身份", ratio: "1:1" },
      },
    }));
    assert.equal(local.result.isError, undefined);
    assert.equal(local.result.structuredContent.visualWorkbench.workflow, "local_edit");
    assert.equal(local.result.structuredContent.visualWorkbench.source.path, await realpath(sourcePath));
    assert.equal(JSON.stringify(local.result.structuredContent).includes("base64"), false);
    assert.match(local.result._meta.visualWorkbenchMedia.source, /^data:image\/png;base64,/);
    assert.match(local.result._meta.visualWorkbenchMedia.stone, /^data:image\/png;base64,/);

    const tryon = await server.send(request(2, "tools/call", {
      name: "open_jewelry_tryon_editor",
      arguments: { workspacePath: workspace, jewelryPath: sourcePath, modelPath, category: "bracelet" },
    }));
    assert.equal(tryon.result.structuredContent.visualWorkbench.workflow, "tryon");
    assert.equal(tryon.result.structuredContent.visualWorkbench.category, "bracelet");
    assert.match(tryon.result._meta.visualWorkbenchMedia.jewelry, /^data:image\/png;base64,/);
    assert.match(tryon.result._meta.visualWorkbenchMedia.model, /^data:image\/png;base64,/);

    const dataUrl = `data:image/png;base64,${pixel.toString("base64")}`;
    const saved = await server.send(request(3, "tools/call", {
      name: "save_jewelry_visual_draft",
      arguments: {
        workspacePath: workspace,
        workflow: "tryon",
        state: {
          category: "bracelet",
          jewelryPath: sourcePath,
          modelPath,
          transform: { x: 0.5, y: 0.6, scale: 0.2, rotation: 4 },
        },
        compositeDataUrl: dataUrl,
        cutoutDataUrl: dataUrl,
        cutoutPreviewDataUrl: dataUrl,
      },
    }));
    assert.equal(saved.result.isError, undefined);
    const draft = saved.result.structuredContent.visualDraft;
    assert.match(draft.id, /^TRYON-[A-F0-9]{8}$/);
    assert.equal(draft.workflow, "tryon");
    assert.match(draft.draftPath, /^visual-workbench\/TRYON-[A-F0-9]{8}\/draft\.json$/);
    assert.equal(draft.draftPath.includes(workspace), false);
    const stored = JSON.parse(await readFile(join(workspace, draft.draftPath), "utf8"));
    assert.equal(stored.state.category, "bracelet");
    assert.equal(stored.assets.composite, draft.compositePath);
    assert.equal(stored.assets.cutout, draft.cutoutPath);
    assert.equal(stored.assets.cutoutPreview, draft.cutoutPreviewPath);
    assert.equal(stored.schema_version, 2);

    const escaped = await server.send(request(4, "tools/call", {
      name: "save_jewelry_visual_draft",
      arguments: {
        workspacePath: directory,
        workflow: "tryon",
        state: {},
        compositeDataUrl: dataUrl,
      },
    }));
    assert.equal(escaped.result.isError, true);
    assert.match(escaped.result.content[0].text, /artifacts\/runs/);
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("opens and saves a source-free blank canvas only for sketch design", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-visual-blank-"));
  const workspace = join(directory, "artifacts", "runs", "blank-sketch");
  await mkdir(workspace, { recursive: true });
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const dataUrl = `data:image/png;base64,${pixel.toString("base64")}`;
  const server = startServer();
  try {
    const opened = await server.send(request(1, "tools/call", {
      name: "open_jewelry_local_editor",
      arguments: { workspacePath: workspace, mode: "sketch_design", category: "ring" },
    }));
    assert.equal(opened.result.isError, undefined);
    assert.equal(opened.result.structuredContent.visualWorkbench.source, undefined);
    assert.equal(opened.result._meta.visualWorkbenchMedia.source, undefined);
    assert.match(opened.result.content[0].text, /空白画板/);

    const saved = await server.send(request(2, "tools/call", {
      name: "save_jewelry_visual_draft",
      arguments: {
        workspacePath: workspace,
        workflow: "local_edit",
        state: { schemaVersion: 2, mode: "sketch_design", category: "ring", instruction: "从空白画板设计戒指", annotations: [], cutoutConfirmed: true },
        compositeDataUrl: dataUrl,
      },
    }));
    assert.equal(saved.result.isError, undefined);
    const stored = JSON.parse(await readFile(join(workspace, saved.result.structuredContent.visualDraft.draftPath), "utf8"));
    assert.equal(stored.state.sourcePath, undefined);

    for (const [id, mode] of [[3, "local_edit"], [4, "put_here"]]) {
      const rejected = await server.send(request(id, "tools/call", {
        name: "open_jewelry_local_editor",
        arguments: { workspacePath: workspace, mode, category: "ring" },
      }));
      assert.equal(rejected.result.isError, true);
      assert.match(rejected.result.content[0].text, /sourcePath/);
    }
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("enforces visual draft v2 category, annotations, and confirmed stone cutout", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-visual-v2-"));
  const workspace = join(directory, "artifacts", "runs", "visual-v2");
  const references = join(workspace, "references");
  await mkdir(references, { recursive: true });
  const pixel = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  const sourcePath = join(references, "source.png");
  const stonePath = join(references, "stone.png");
  await writeFile(sourcePath, pixel);
  await writeFile(stonePath, pixel);
  const dataUrl = `data:image/png;base64,${pixel.toString("base64")}`;
  const server = startServer();
  try {
    const missingMode = await server.send(request(1, "tools/call", {
      name: "open_jewelry_local_editor", arguments: { workspacePath: workspace, category: "ring" },
    }));
    assert.equal(missingMode.result.isError, true);
    assert.match(missingMode.result.content[0].text, /mode is required/);

    const custom = await server.send(request(2, "tools/call", {
      name: "open_jewelry_local_editor",
      arguments: { workspacePath: workspace, sourcePath, mode: "put_here", category: "other", customCategory: "领带夹" },
    }));
    assert.equal(custom.result.isError, undefined);
    assert.equal(custom.result.structuredContent.visualWorkbench.customCategory, "领带夹");

    const state = {
      schemaVersion: 2,
      mode: "sketch_design",
      category: "ring",
      stonePath,
      instruction: "围绕主石绘制戒指",
      annotations: [],
      cutoutConfirmed: true,
    };
    const missingPreview = await server.send(request(3, "tools/call", {
      name: "save_jewelry_visual_draft",
      arguments: { workspacePath: workspace, workflow: "local_edit", state, compositeDataUrl: dataUrl, cutoutDataUrl: dataUrl },
    }));
    assert.equal(missingPreview.result.isError, true);
    assert.match(missingPreview.result.content[0].text, /cutoutPreviewDataUrl/);

    const saved = await server.send(request(4, "tools/call", {
      name: "save_jewelry_visual_draft",
      arguments: { workspacePath: workspace, workflow: "local_edit", state, compositeDataUrl: dataUrl, cutoutDataUrl: dataUrl, cutoutPreviewDataUrl: dataUrl },
    }));
    assert.equal(saved.result.isError, undefined);
    const draft = saved.result.structuredContent.visualDraft;
    const stored = JSON.parse(await readFile(join(workspace, draft.draftPath), "utf8"));
    assert.equal(stored.schema_version, 2);
    assert.equal(stored.assets.cutoutPreview, draft.cutoutPreviewPath);

    const missingAnnotation = await server.send(request(5, "tools/call", {
      name: "save_jewelry_visual_draft",
      arguments: {
        workspacePath: workspace,
        workflow: "local_edit",
        state: { schemaVersion: 2, mode: "local_edit", category: "ring", sourcePath, annotations: [] },
        compositeDataUrl: dataUrl,
      },
    }));
    assert.equal(missingAnnotation.result.isError, true);
    assert.match(missingAnnotation.result.content[0].text, /at least one annotation/);

    const oversizedCategory = await server.send(request(6, "tools/call", {
      name: "open_jewelry_local_editor",
      arguments: { workspacePath: workspace, sourcePath, mode: "put_here", category: "other", customCategory: "x".repeat(41) },
    }));
    assert.equal(oversizedCategory.result.isError, true);
    assert.match(oversizedCategory.result.content[0].text, /at most 40 characters/);

    const escapedBounds = await server.send(request(7, "tools/call", {
      name: "save_jewelry_visual_draft",
      arguments: {
        workspacePath: workspace,
        workflow: "local_edit",
        state: {
          schemaVersion: 2, mode: "local_edit", category: "ring", sourcePath,
          annotations: [{ id: "REGION-01", kind: "region", bounds: { x: 0.9, y: 0.2, width: 0.2, height: 0.2 }, instruction: "改成钻石" }],
        },
        compositeDataUrl: dataUrl,
      },
    }));
    assert.equal(escapedBounds.result.isError, true);
    assert.match(escapedBounds.result.content[0].text, /stay inside the canvas/);
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("rejects workspace and input symlink escapes before reading or writing", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-visual-symlink-"));
  const runs = join(directory, "artifacts", "runs");
  const workspace = join(runs, "safe-task");
  const outside = join(directory, "outside");
  await mkdir(join(workspace, "references"), { recursive: true });
  await mkdir(outside, { recursive: true });
  const pixel = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64");
  const outsideImage = join(outside, "outside.png");
  await writeFile(outsideImage, pixel);
  const escapedImage = join(workspace, "references", "escaped.png");
  await symlink(outsideImage, escapedImage);
  const linkedWorkspace = join(runs, "linked-task");
  await symlink(workspace, linkedWorkspace);
  const writeWorkspace = join(runs, "write-task");
  await mkdir(writeWorkspace, { recursive: true });
  await symlink(outside, join(writeWorkspace, "visual-workbench"));
  const dataUrl = `data:image/png;base64,${pixel.toString("base64")}`;
  const server = startServer();
  try {
    const inputEscape = await server.send(request(1, "tools/call", {
      name: "open_jewelry_local_editor",
      arguments: { workspacePath: workspace, sourcePath: escapedImage, mode: "local_edit", category: "ring" },
    }));
    assert.equal(inputEscape.result.isError, true);
    assert.match(inputEscape.result.content[0].text, /symbolic link/);

    const workspaceEscape = await server.send(request(2, "tools/call", {
      name: "open_jewelry_local_editor",
      arguments: { workspacePath: linkedWorkspace, mode: "sketch_design", category: "ring" },
    }));
    assert.equal(workspaceEscape.result.isError, true);
    assert.match(workspaceEscape.result.content[0].text, /symbolic link/);

    const writeEscape = await server.send(request(3, "tools/call", {
      name: "save_jewelry_visual_draft",
      arguments: {
        workspacePath: writeWorkspace, workflow: "local_edit",
        state: { schemaVersion: 2, mode: "sketch_design", category: "ring", annotations: [], cutoutConfirmed: true },
        compositeDataUrl: dataUrl,
      },
    }));
    assert.equal(writeEscape.result.isError, true);
    assert.match(writeEscape.result.content[0].text, /symbolic links/);
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});

test("preserves sketch design workflow in neutral Gallery selection context", async () => {
  const directory = await mkdtemp(join(tmpdir(), "svt-sketch-gallery-"));
  const pixelPath = join(directory, "sketch.png");
  await writeFile(pixelPath, Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  ));
  const server = startServer();
  try {
    const called = await server.send(request(1, "tools/call", {
      name: "show_jewelry_design_gallery",
      arguments: {
        sourceWorkflow: "sketch_design",
        items: ["A", "B", "C", "D"].map((letter) => ({ id: `SKETCH-${letter}`, title: `草图方案 ${letter}`, path: pixelPath })),
      },
    }));
    assert.equal(called.result.isError, undefined);
    assert.equal(called.result.structuredContent.designGallery.sourceWorkflow, "sketch_design");
    const invalid = await server.send(request(3, "tools/call", {
      name: "show_jewelry_design_gallery",
      arguments: {
        sourceWorkflow: "sketch_design",
        items: [{ id: "SKETCH-A-LOCAL", title: "错误编号", path: pixelPath }],
      },
    }));
    assert.equal(invalid.result.isError, true);
    assert.match(invalid.result.content[0].text, /SKETCH-A through SKETCH-D/);
    const resource = await server.send(request(2, "resources/read", { uri: "ui://svt-jewelry/design-gallery/v2.html" }));
    assert.match(resource.result.contents[0].text, /active\?\.sourceWorkflow\|\|"design"/);
  } finally {
    await server.close();
    await rm(directory, { recursive: true });
  }
});
