import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const marketplacePath = path.join(root, ".agents", "plugins", "marketplace.json");
const coreRoot = path.join(root, "plugins", "svt-jewelry-design");
const optionalRoots = [
  path.join(root, "plugins", "svt-jewelry-video"),
  path.join(root, "plugins", "svt-jewelry-feishu"),
];

const readJson = (file) => JSON.parse(fs.readFileSync(file, "utf8"));

function walkFiles(directory) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const child = path.join(directory, entry.name);
    return entry.isDirectory() ? walkFiles(child) : [child];
  });
}

test("repository marketplace exposes one default core and two optional integrations", () => {
  const marketplace = readJson(marketplacePath);
  assert.equal(marketplace.name, "jewelry-design-codex");
  assert.equal(marketplace.interface.displayName, "JewelryDesignCodex");

  const entries = Object.fromEntries(marketplace.plugins.map((plugin) => [plugin.name, plugin]));
  assert.deepEqual(Object.keys(entries).sort(), [
    "svt-jewelry-design",
    "svt-jewelry-feishu",
    "svt-jewelry-video",
  ]);
  assert.equal(entries["svt-jewelry-design"].policy.installation, "AVAILABLE");
  assert.equal(entries["svt-jewelry-video"].policy.installation, "AVAILABLE");
  assert.equal(entries["svt-jewelry-feishu"].policy.installation, "AVAILABLE");

  for (const plugin of marketplace.plugins) {
    assert.equal(plugin.source.source, "local");
    assert.equal(plugin.source.path, `./plugins/${plugin.name}`);
    assert.ok(["ON_INSTALL", "ON_USE"].includes(plugin.policy.authentication));
    assert.equal(plugin.category, "Productivity");
  }
});

test("public plugin manifests are versioned, licensed, and point at the public repository", () => {
  for (const pluginRoot of [coreRoot, ...optionalRoots]) {
    const manifest = readJson(path.join(pluginRoot, ".codex-plugin", "plugin.json"));
    assert.equal(manifest.name, path.basename(pluginRoot));
    assert.equal(manifest.version, "0.2.0");
    assert.equal(manifest.license, "Apache-2.0");
    assert.equal(manifest.repository, "https://github.com/yuyou-dev/JewelryDesignCodex");
    assert.equal(manifest.homepage, "https://github.com/yuyou-dev/JewelryDesignCodex");
    assert.equal(manifest.author.name, "苏哇科技");
  }
});

test("core package is self-contained and excludes unavailable integrations", () => {
  const skillRoot = path.join(coreRoot, "skills");
  const names = fs.readdirSync(skillRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name);
  assert.ok(!names.includes("jewelry-search"));
  assert.ok(!names.includes("jewelry-dreamina-video"));
  assert.ok(!names.includes("jewelry-video-prompt"));
  assert.ok(!names.includes("jewelry-feishu-agent"));

  const unavailableReferences = [
    "$jewelry-search",
    "$jewelry-dreamina-video",
    "$jewelry-video-prompt",
    "$jewelry-feishu-agent",
    "run_lark_cli.py",
    "jewelry_seedance_video",
  ];
  const text = walkFiles(skillRoot)
    .filter((file) => /\.(?:md|json|ya?ml|mjs)$/i.test(file))
    .map((file) => fs.readFileSync(file, "utf8"))
    .join("\n");
  for (const value of unavailableReferences) assert.ok(!text.includes(value), value);
});

test("published package contains no private paths, private repo names, or task links", () => {
  const scanRoots = [
    marketplacePath,
    path.join(coreRoot, ".codex-plugin", "plugin.json"),
    path.join(coreRoot, "skills"),
    ...optionalRoots,
    path.join(root, "PROVENANCE.md"),
  ];
  const forbidden = [
    /\/Users\//,
    /[A-Za-z]:\\Users\\/,
    /codex:\/\/threads\//,
    new RegExp("SVT-Jewelry" + "DesignPlugins"),
    new RegExp("SVT-Jewelry" + "-Skills-Image-2"),
    /github\.com\/yuyou-dev\/SVT-/,
    /npm run jewelry:/,
    /npm run feishu:/,
    /npm run seedance:/,
  ];
  for (const scanRoot of scanRoots) {
    const files = fs.statSync(scanRoot).isDirectory() ? walkFiles(scanRoot) : [scanRoot];
    for (const file of files) {
      if (!/\.(?:md|json|ya?ml|mjs|py|html)$/i.test(file)) continue;
      const content = fs.readFileSync(file, "utf8");
      for (const pattern of forbidden) {
        assert.ok(!pattern.test(content), `${path.relative(root, file)} contains ${pattern}`);
      }
    }
  }
});

test("every shipped skill passes the structural quick checks", () => {
  for (const pluginRoot of [coreRoot, ...optionalRoots]) {
    const skillsRoot = path.join(pluginRoot, "skills");
    for (const entry of fs.readdirSync(skillsRoot, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const skillFile = path.join(skillsRoot, entry.name, "SKILL.md");
      assert.ok(fs.existsSync(skillFile), `${entry.name} has SKILL.md`);
      const source = fs.readFileSync(skillFile, "utf8");
      assert.match(source, /^---\nname: [a-z0-9-]+\ndescription: .+\n---\n/);
      assert.ok(source.length < 40_000, `${entry.name} stays concise`);
    }
  }
});
