import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = new URL("../", import.meta.url);
const rootPath = fileURLToPath(root);
const read = (path) => readFileSync(new URL(path, root), "utf8");

test("repository exposes the documented public marketplace interface", () => {
  const marketplace = JSON.parse(read(".agents/plugins/marketplace.json"));
  assert.equal(marketplace.name, "jewelry-design-codex");
  assert.deepEqual(
    marketplace.plugins.map((plugin) => plugin.name),
    ["svt-jewelry-design", "svt-jewelry-video", "svt-jewelry-feishu"],
  );
  assert.equal(marketplace.plugins[0].policy.installation, "AVAILABLE");
  assert.equal(marketplace.plugins[0].source.path, "./plugins/svt-jewelry-design");
});

test("core plugin has stable public release metadata and a local MCP", () => {
  const manifest = JSON.parse(read("plugins/svt-jewelry-design/.codex-plugin/plugin.json"));
  const mcp = JSON.parse(read("plugins/svt-jewelry-design/.mcp.json"));
  assert.equal(manifest.name, "svt-jewelry-design");
  assert.equal(manifest.version, "0.2.0");
  assert.equal(manifest.license, "Apache-2.0");
  assert.equal(manifest.repository, "https://github.com/yuyou-dev/JewelryDesignCodex");
  assert.ok(mcp.mcpServers.svt_jewelry_ui);
  assert.doesNotMatch(JSON.stringify(mcp), /\/bin\/bash|start-server\.sh/);
});

test("README presents one-command Codex installation near the top", () => {
  const readme = read("README.md");
  const prompt = "/goal Read https://raw.githubusercontent.com/yuyou-dev/JewelryDesignCodex/main/INSTALL.md";
  assert.ok(readme.indexOf(prompt) >= 0 && readme.indexOf(prompt) < 5000);
  assert.match(read("INSTALL.md"), /plugin marketplace add yuyou-dev\/JewelryDesignCodex/);
  assert.match(read("INSTALL.md"), /svt-jewelry-design@jewelry-design-codex/);
});

test("README presents the permanent one-command update flow", () => {
  const readme = read("README.md");
  const prompt = "/goal Read https://raw.githubusercontent.com/yuyou-dev/JewelryDesignCodex/main/UPDATE.md";
  assert.ok(readme.indexOf(prompt) > readme.indexOf("/INSTALL.md"));
  assert.ok(readme.indexOf(prompt) < 7000);
  const update = read("UPDATE.md");
  assert.match(update, /--branch v0\.2\.0/);
  assert.match(update, /rolledBack/);
  assert.match(update, /svt-jewelry-video@jewelry-design-codex/);
});

test("tracked public package contains no private machine or task residue", () => {
  assert.doesNotThrow(() => execFileSync(process.execPath, ["scripts/public-scan.mjs"], {
    cwd: rootPath,
    encoding: "utf8",
    stdio: "pipe",
  }));
});

test("public plugin Skills do not expose unavailable core integrations", () => {
  const skills = readdirSync(join(rootPath, "plugins/svt-jewelry-design/skills"), { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .join("\n");
  assert.doesNotMatch(skills, /jewelry-search|jewelry-dreamina-video|jewelry-feishu-agent/);
});
