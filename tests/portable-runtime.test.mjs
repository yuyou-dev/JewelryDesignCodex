import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { randomFillSync } from "node:crypto";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { createRequire } from "node:module";
import { deflateSync } from "node:zlib";
import { resolveCodex } from "../plugins/svt-jewelry-design/runtime/runtime.mjs";
import { compactImage } from "../plugins/svt-jewelry-design/mcp/portable-image.mjs";

const ROOT = resolve(import.meta.dirname, "..");
const PLUGIN = join(ROOT, "plugins", "svt-jewelry-design");
const JDC = join(ROOT, "scripts", "jdc.mjs");
const PLUGIN_JDC = join(PLUGIN, "scripts", "jdc.mjs");
const MCP_SERVER = join(PLUGIN, "mcp", "server.mjs");
const require = createRequire(import.meta.url);
const jpeg = require("../plugins/svt-jewelry-design/mcp/vendor/jpeg-js/index.js");

function runNode(args, options = {}) {
  return spawnSync(process.execPath, args, {
    cwd: ROOT,
    encoding: "utf8",
    ...options,
  });
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const typeBytes = Buffer.from(type, "ascii");
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(Buffer.concat([typeBytes, data])));
  return Buffer.concat([length, typeBytes, data, checksum]);
}

function noisyPng(width, height) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 6;
  const rows = Buffer.alloc((width * 4 + 1) * height);
  randomFillSync(rows);
  for (let y = 0; y < height; y += 1) {
    const offset = y * (width * 4 + 1);
    rows[offset] = 0;
  }
  return Buffer.concat([
    Buffer.from("89504e470d0a1a0a", "hex"),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(rows, { level: 1 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

function fakeCodex(directory) {
  const implementation = join(directory, "fake-codex.mjs");
  writeFileSync(implementation, `
const args = process.argv.slice(2).join(" ");
const mode = process.env.FAKE_CODEX_MODE || "installed";
if (args.includes("plugin marketplace list")) {
  const source = mode === "conflict" ? "https://example.invalid/not-jdc.git" : "https://github.com/yuyou-dev/JewelryDesignCodex.git";
  process.stdout.write(JSON.stringify({marketplaces:[{name:"jewelry-design-codex",marketplaceSource:{sourceType:"git",source}}]}));
} else if (args.includes("plugin list")) {
  const installed = ["installed", "disabled"].includes(mode)
    ? [{pluginId:"svt-jewelry-design@jewelry-design-codex",name:"svt-jewelry-design",marketplaceName:"jewelry-design-codex",version:"0.1.0",installed:true,enabled:mode !== "disabled"}]
    : [];
  process.stdout.write(JSON.stringify({installed,available:[]}));
} else if (args.includes("mcp get")) {
  process.stdout.write(JSON.stringify({name:"svt_jewelry_ui",enabled:true}));
} else {
  process.stdout.write("{}");
}
`);
  if (process.platform === "win32") {
    const wrapper = join(directory, "fake-codex.cmd");
    writeFileSync(wrapper, `@echo off\r\n"${process.execPath}" "${implementation}" %*\r\n`);
    return wrapper;
  }
  const wrapper = join(directory, "fake-codex");
  writeFileSync(wrapper, `#!/bin/sh\nexec "${process.execPath}" "${implementation}" "$@"\n`);
  chmodSync(wrapper, 0o755);
  return wrapper;
}

function statefulFakeCodex(directory) {
  const implementation = join(directory, "stateful-codex.mjs");
  const statePath = join(directory, "state.json");
  writeFileSync(statePath, JSON.stringify({ marketplace: false, installed: false, version: "0.1.0", available: "0.1.0" }));
  writeFileSync(implementation, `
import { readFileSync, writeFileSync } from "node:fs";
const statePath = ${JSON.stringify(statePath)};
const state = JSON.parse(readFileSync(statePath, "utf8"));
const args = process.argv.slice(2);
const command = args.join(" ");
const save = () => writeFileSync(statePath, JSON.stringify(state));
const marketplace = () => state.marketplace
  ? [{name:"jewelry-design-codex",marketplaceSource:{sourceType:"git",source:"https://github.com/yuyou-dev/JewelryDesignCodex.git"}}]
  : [];
const installed = () => state.installed
  ? [{pluginId:"svt-jewelry-design@jewelry-design-codex",name:"svt-jewelry-design",marketplaceName:"jewelry-design-codex",version:state.version,installed:true,enabled:true}]
  : [];
if (command.startsWith("login status")) {
  process.stdout.write("Logged in");
} else if (command.startsWith("plugin marketplace list")) {
  process.stdout.write(JSON.stringify({marketplaces:marketplace()}));
} else if (command.startsWith("plugin marketplace add")) {
  state.marketplace = true; save(); process.stdout.write("{}");
} else if (command.startsWith("plugin marketplace upgrade")) {
  state.available = "0.2.0"; save(); process.stdout.write("{}");
} else if (command.startsWith("plugin list")) {
  const available = state.marketplace
    ? [{name:"svt-jewelry-design",marketplaceName:"jewelry-design-codex",version:state.available}]
    : [];
  process.stdout.write(JSON.stringify({installed:installed(),available}));
} else if (command.startsWith("plugin add")) {
  state.installed = true; state.version = state.available; save(); process.stdout.write("{}");
} else if (command.startsWith("plugin remove")) {
  state.installed = false; save(); process.stdout.write("{}");
} else if (command.startsWith("mcp get")) {
  if (!state.installed) process.exit(1);
  process.stdout.write(JSON.stringify({name:"svt_jewelry_ui",enabled:true}));
} else {
  process.stdout.write("{}");
}
`);
  if (process.platform === "win32") {
    const wrapper = join(directory, "stateful-codex.cmd");
    writeFileSync(wrapper, `@echo off\r\n"${process.execPath}" "${implementation}" %*\r\n`);
    return wrapper;
  }
  const wrapper = join(directory, "stateful-codex");
  writeFileSync(wrapper, `#!/bin/sh\nexec "${process.execPath}" "${implementation}" "$@"\n`);
  chmodSync(wrapper, 0o755);
  return wrapper;
}

test("MCP manifest launches Node directly without a POSIX shell", () => {
  const config = JSON.parse(readFileSync(join(PLUGIN, ".mcp.json"), "utf8"));
  const server = config.mcpServers.svt_jewelry_ui;
  assert.equal(server.command, "node");
  assert.deepEqual(server.args, ["./mcp/server.mjs", "--stdio"]);
  assert.doesNotMatch(JSON.stringify(server), /(?:\/bin\/bash|\.sh\b|BASH_SOURCE)/);
});

test("MCP stdio server starts from a path with spaces and non-ASCII characters", () => {
  const request = JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} });
  const result = runNode([MCP_SERVER, "--stdio"], { input: `${request}\n` });
  assert.equal(result.status, 0, result.stderr);
  const response = JSON.parse(result.stdout.trim());
  assert.deepEqual(response.result.serverInfo, { name: "svt_jewelry_ui", version: "0.1.0" });
});

test("MCP compacts oversized PNG previews with bundled cross-platform code", () => {
  const directory = mkdtempSync(join(tmpdir(), "jdc-portable-preview-"));
  try {
    const imagePath = join(directory, "珠宝 测试.png");
    writeFileSync(imagePath, noisyPng(640, 640));
    const request = JSON.stringify({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: {
        name: "show_jewelry_design_gallery",
        arguments: { sourceWorkflow: "design", items: [{ id: "DESIGN-A", title: "A", path: imagePath }] },
      },
    });
    const result = runNode([MCP_SERVER, "--stdio"], {
      input: `${request}\n`,
      env: { ...process.env, PATH: "", SVT_JEWELRY_UI_PREVIEW_BUDGET_CHARS: String(180 * 1024) },
    });
    assert.equal(result.status, 0, result.stderr);
    const response = JSON.parse(result.stdout.trim());
    assert.equal(response.result.isError, undefined, response.result.content?.[0]?.text);
    const preview = response.result._meta.designMedia.items["DESIGN-A"];
    assert.match(preview, /^data:image\/jpeg;base64,/);
    assert.ok(preview.length <= 180 * 1024, `preview is ${preview.length} characters`);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("MCP compacts oversized JPEG previews with the vendored codec", () => {
  const directory = mkdtempSync(join(tmpdir(), "jdc-portable-jpeg-"));
  try {
    const pixels = Buffer.alloc(640 * 640 * 4);
    randomFillSync(pixels);
    for (let offset = 3; offset < pixels.length; offset += 4) pixels[offset] = 255;
    const imagePath = join(directory, "jewelry.jpg");
    writeFileSync(imagePath, jpeg.encode({ width: 640, height: 640, data: pixels }, 100).data);
    const request = JSON.stringify({
      jsonrpc: "2.0", id: 3, method: "tools/call",
      params: { name: "show_jewelry_design_gallery", arguments: { items: [{ id: "DESIGN-JPEG", path: imagePath }] } },
    });
    const result = runNode([MCP_SERVER, "--stdio"], {
      input: `${request}\n`,
      env: { ...process.env, PATH: "", SVT_JEWELRY_UI_PREVIEW_BUDGET_CHARS: String(180 * 1024) },
    });
    assert.equal(result.status, 0, result.stderr);
    const response = JSON.parse(result.stdout.trim());
    assert.equal(response.result.isError, undefined, response.result.content?.[0]?.text);
    const preview = response.result._meta.designMedia.items["DESIGN-JPEG"];
    assert.match(preview, /^data:image\/jpeg;base64,/);
    assert.ok(preview.length <= 180 * 1024);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("portable preview rejects oversized PNG dimensions before decompression", () => {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(100_000, 0);
  header.writeUInt32BE(100_000, 4);
  header[8] = 8;
  header[9] = 6;
  const image = Buffer.concat([
    Buffer.from("89504e470d0a1a0a", "hex"),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(Buffer.from([0]))),
    chunk("IEND", Buffer.alloc(0)),
  ]);
  assert.throws(
    () => compactImage({ mimeType: "image/png", data: image }, 640, 72),
    /dimensions exceed the portable preview limit/,
  );
});

test("portable preview rejects oversized JPEG dimensions before codec allocation", () => {
  const frame = Buffer.alloc(17);
  frame.writeUInt16BE(17, 0);
  frame[2] = 8;
  frame.writeUInt16BE(65_535, 3);
  frame.writeUInt16BE(65_535, 5);
  frame[7] = 3;
  const image = Buffer.concat([
    Buffer.from([0xff, 0xd8, 0xff, 0xc0]),
    frame,
    Buffer.from([0xff, 0xd9]),
  ]);
  assert.throws(
    () => compactImage({ mimeType: "image/jpeg", data: image }, 640, 72),
    /dimensions exceed the portable preview limit/,
  );
});

test("lifecycle commands expose deterministic JSON dry-runs", () => {
  for (const command of ["bootstrap", "update", "uninstall"]) {
    const result = runNode([JDC, command, "--dry-run", "--json"]);
    assert.equal(result.status, 0, `${command}: ${result.stderr}`);
    const output = JSON.parse(result.stdout);
    assert.equal(output.command, command);
    assert.equal(output.dryRun, true);
    assert.ok(["ready", "restart_required"].includes(output.status));
    assert.ok(Array.isArray(output.actions));
  }
});

test("offline doctor reports portable runtime checks without reading credentials", () => {
  const result = runNode([JDC, "doctor", "--offline", "--json"]);
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.command, "doctor");
  assert.equal(output.offline, true);
  assert.equal(output.status, "ready");
  assert.equal(output.checks.node.ok, true);
  assert.equal(output.checks.plugin.ok, true);
  assert.equal(JSON.stringify(output).includes("auth.json"), false);
  assert.equal(JSON.stringify(output).toLowerCase().includes("api_key"), false);
});

test("bootstrap is idempotent when the expected plugin is already installed", () => {
  const directory = mkdtempSync(join(tmpdir(), "jdc-fake-codex-"));
  try {
    const result = runNode([JDC, "bootstrap", "--json"], {
      env: { ...process.env, JDC_CODEX_BIN: fakeCodex(directory), FAKE_CODEX_MODE: "installed" },
    });
    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.status, "ready");
    assert.deepEqual(output.actions, []);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("bootstrap stops instead of overwriting a conflicting marketplace", () => {
  const directory = mkdtempSync(join(tmpdir(), "jdc-fake-codex-"));
  try {
    const result = runNode([JDC, "bootstrap", "--json"], {
      env: { ...process.env, JDC_CODEX_BIN: fakeCodex(directory), FAKE_CODEX_MODE: "conflict" },
    });
    assert.equal(result.status, 1);
    const output = JSON.parse(result.stdout);
    assert.equal(output.status, "blocked");
    assert.match(output.reason, /different source/);
    assert.deepEqual(output.actions, []);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("bootstrap restores a disabled core plugin and uninstall still removes it", () => {
  const directory = mkdtempSync(join(tmpdir(), "jdc-disabled-codex-"));
  try {
    const env = { ...process.env, JDC_CODEX_BIN: fakeCodex(directory), FAKE_CODEX_MODE: "disabled" };
    const bootstrapResult = runNode([JDC, "bootstrap", "--json"], { env });
    assert.equal(bootstrapResult.status, 0, bootstrapResult.stderr);
    const bootstrapOutput = JSON.parse(bootstrapResult.stdout);
    assert.equal(bootstrapOutput.status, "restart_required");
    assert.deepEqual(bootstrapOutput.actions.map(({ label }) => label), ["install plugin"]);

    const uninstallResult = runNode([JDC, "uninstall", "--json"], { env });
    assert.equal(uninstallResult.status, 0, uninstallResult.stderr);
    const uninstallOutput = JSON.parse(uninstallResult.stdout);
    assert.equal(uninstallOutput.status, "restart_required");
    assert.deepEqual(uninstallOutput.actions.map(({ label }) => label), ["remove plugin"]);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("lifecycle remains idempotent across install, update, and uninstall", () => {
  const directory = mkdtempSync(join(tmpdir(), "jdc-stateful-codex-"));
  try {
    const codex = statefulFakeCodex(directory);
    const env = { ...process.env, JDC_CODEX_BIN: codex };

    const first = JSON.parse(runNode([JDC, "bootstrap", "--json"], { env }).stdout);
    assert.equal(first.status, "restart_required");
    assert.deepEqual(first.actions.map(({ label }) => label), ["add marketplace", "install plugin"]);

    const repeat = JSON.parse(runNode([JDC, "bootstrap", "--json"], { env }).stdout);
    assert.equal(repeat.status, "ready");
    assert.deepEqual(repeat.actions, []);

    const update = JSON.parse(runNode([JDC, "update", "--json"], { env }).stdout);
    assert.equal(update.status, "restart_required");
    assert.deepEqual(update.actions.map(({ label }) => label), ["upgrade marketplace", "refresh plugin"]);

    const remove = JSON.parse(runNode([JDC, "uninstall", "--json"], { env }).stdout);
    assert.equal(remove.status, "restart_required");
    assert.deepEqual(remove.actions.map(({ label }) => label), ["remove plugin"]);

    const removeAgain = JSON.parse(runNode([JDC, "uninstall", "--json"], { env }).stdout);
    assert.equal(removeAgain.status, "ready");
    assert.deepEqual(removeAgain.actions, []);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("plugin-local command router delegates to bundled Python tools", () => {
  const result = runNode([PLUGIN_JDC, "remix", "--help"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /prepare/);
});

test("Codex runtime resolution prefers an explicit path, then bundled Desktop paths", async () => {
  const directory = mkdtempSync(join(tmpdir(), "jdc-runtime-resolution-"));
  try {
    const explicit = join(directory, process.platform === "win32" ? "explicit.exe" : "explicit");
    writeFileSync(explicit, "runtime");
    chmodSync(explicit, 0o755);
    assert.equal(await resolveCodex({ env: { JDC_CODEX_BIN: explicit, PATH: "" }, platform: process.platform }), realpathSync(explicit));

    const mac = join(directory, "Applications", "Codex.app", "Contents", "Resources", "codex");
    mkdirSync(resolve(mac, ".."), { recursive: true });
    writeFileSync(mac, "runtime");
    chmodSync(mac, 0o755);
    assert.equal(await resolveCodex({ env: { HOME: directory, PATH: "" }, platform: "darwin" }), realpathSync(mac));

    const windows = join(directory, "Programs", "Codex", "resources", "codex.exe");
    mkdirSync(resolve(windows, ".."), { recursive: true });
    writeFileSync(windows, "runtime");
    assert.equal(await resolveCodex({ env: { LOCALAPPDATA: directory, PATH: "" }, platform: "win32" }), realpathSync(windows));
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
