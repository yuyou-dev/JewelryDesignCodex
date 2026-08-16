#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync, realpathSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { resolveCodex, resolveExecutable, resolvePython } from "../plugins/svt-jewelry-design/runtime/runtime.mjs";

const MARKETPLACE = "jewelry-design-codex";
const MARKETPLACE_SOURCE = "yuyou-dev/JewelryDesignCodex";
const MARKETPLACE_REF = "v0.1.0";
const PLUGIN = "svt-jewelry-design";
const PLUGIN_ID = `${PLUGIN}@${MARKETPLACE}`;
const MCP = "svt_jewelry_ui";
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function parseArgs(argv) {
  const [command = "doctor", ...flags] = argv;
  const allowedCommands = new Set(["bootstrap", "doctor", "update", "uninstall"]);
  if (!allowedCommands.has(command)) throw new Error(`unknown command: ${command}`);
  const allowedFlags = new Set(["--json", "--dry-run", "--offline"]);
  const unknown = flags.find((flag) => !allowedFlags.has(flag));
  if (unknown) throw new Error(`unknown option: ${unknown}`);
  return {
    command,
    json: flags.includes("--json"),
    dryRun: flags.includes("--dry-run"),
    offline: flags.includes("--offline"),
  };
}

function execute(command, args, { json = false } = {}) {
  const shell = process.platform === "win32" && /\.(?:cmd|bat)$/i.test(command);
  const result = spawnSync(command, args, { encoding: "utf8", windowsHide: true, shell });
  if (result.error) throw new Error(`unable to start ${args[0] || command}: ${result.error.message}`);
  if (result.status !== 0) {
    const detail = (result.stderr || result.stdout || "command failed").trim().split("\n")[0];
    throw new Error(detail);
  }
  if (!json) return result.stdout.trim();
  try {
    return JSON.parse(result.stdout);
  } catch {
    throw new Error(`invalid JSON returned by Codex command: ${args.slice(0, 3).join(" ")}`);
  }
}

function sourceMatches(source) {
  const normalized = String(source || "").replace(/\.git$/i, "").replace(/^git@github\.com:/i, "github.com/");
  return normalized === MARKETPLACE_SOURCE
    || normalized === `https://github.com/${MARKETPLACE_SOURCE}`
    || normalized === `ssh://git@github.com/${MARKETPLACE_SOURCE}`
    || normalized === `github.com/${MARKETPLACE_SOURCE}`;
}

function marketplaceEntry(payload) {
  return (payload.marketplaces || []).find(({ name }) => name === MARKETPLACE);
}

function installedEntries(payload) {
  return Array.isArray(payload.installed) ? payload.installed : [];
}

function pluginEntry(payload, id = PLUGIN_ID, { includeDisabled = false } = {}) {
  return installedEntries(payload).find(({ pluginId, installed, enabled }) => (
    pluginId === id
    && installed !== false
    && (includeDisabled || enabled !== false)
  ));
}

async function runtimeChecks() {
  const python = await resolvePython();
  const git = await resolveExecutable(["git"]);
  let pythonVersion = null;
  let gitVersion = null;
  if (python) {
    const result = spawnSync(python.command, [...python.argsPrefix, "--version"], { encoding: "utf8", windowsHide: true });
    pythonVersion = `${result.stdout || ""}${result.stderr || ""}`.trim();
  }
  if (git) {
    const result = spawnSync(git, ["--version"], { encoding: "utf8", windowsHide: true });
    gitVersion = `${result.stdout || ""}${result.stderr || ""}`.trim();
  }
  const gitMatch = /git version (\d+)\.(\d+)/i.exec(gitVersion || "");
  const gitOk = Boolean(gitMatch) && (
    Number(gitMatch[1]) > 2 || (Number(gitMatch[1]) === 2 && Number(gitMatch[2]) >= 30)
  );
  const nodeMajor = Number(process.versions.node.split(".")[0]);
  const pluginFiles = [
    join(ROOT, "plugins", PLUGIN, ".codex-plugin", "plugin.json"),
    join(ROOT, "plugins", PLUGIN, ".mcp.json"),
    join(ROOT, "plugins", PLUGIN, "mcp", "server.mjs"),
    join(ROOT, "plugins", PLUGIN, "scripts", "jdc.mjs"),
    join(ROOT, "plugins", PLUGIN, "scripts", "jewelry_image2_tool.py"),
    join(ROOT, "plugins", PLUGIN, "scripts", "jewelry_remix.py"),
    join(ROOT, "plugins", PLUGIN, "scripts", "jewelry_visual_workbench.py"),
  ];
  const uiFiles = [
    "jewelry-creation-brief.html",
    "jewelry-creation-gallery.html",
    "jewelry-design-gallery.html",
    "jewelry-followup.html",
    "jewelry-remix-brief.html",
    "jewelry-remix-gallery.html",
    "jewelry-retouch-comparison.html",
    "jewelry-visual-workbench.html",
  ].map((name) => join(ROOT, "plugins", PLUGIN, "mcp", name));
  const skillsRoot = join(ROOT, "plugins", PLUGIN, "skills");
  const skillCount = existsSync(skillsRoot)
    ? readdirSync(skillsRoot, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && existsSync(join(skillsRoot, entry.name, "SKILL.md"))).length
    : 0;
  return {
    node: { ok: nodeMajor >= 20, version: process.versions.node },
    python: { ok: /^Python 3\.(?:1\d|[2-9]\d)\b/.test(pythonVersion || ""), version: pythonVersion },
    git: { ok: gitOk, version: gitVersion },
    plugin: {
      ok: pluginFiles.every(existsSync) && uiFiles.every(existsSync) && skillCount === 15,
      skills: skillCount,
      uiResources: uiFiles.filter(existsSync).length,
    },
  };
}

function checksReady(checks) {
  return Object.values(checks).every(({ ok }) => ok);
}

async function inspectCodex(codex) {
  const marketplaces = execute(codex, ["plugin", "marketplace", "list", "--json"], { json: true });
  const plugins = execute(codex, ["plugin", "list", "--available", "--json"], { json: true });
  return { marketplaces, plugins };
}

function conflictReason(state) {
  const configured = marketplaceEntry(state.marketplaces);
  if (configured && !sourceMatches(configured.marketplaceSource?.source)) {
    return `marketplace ${MARKETPLACE} already points to a different source`;
  }
  const conflict = installedEntries(state.plugins).find(({ name, marketplaceName, enabled }) => (
    name === PLUGIN && marketplaceName !== MARKETPLACE && enabled !== false
  ));
  return conflict ? `enabled plugin ${conflict.pluginId} conflicts with ${PLUGIN_ID}` : null;
}

function action(label, args) {
  return { label, command: "codex", args };
}

function runAction(codex, item, dryRun) {
  if (!dryRun) execute(codex, [...item.args, "--json"], { json: true });
}

async function doctor(options) {
  const checks = await runtimeChecks();
  if (!checksReady(checks)) return { command: "doctor", status: "blocked", offline: options.offline, checks, actions: [] };
  if (options.offline) return { command: "doctor", status: "ready", offline: true, checks, actions: [] };
  const codex = await resolveCodex();
  checks.codex = { ok: Boolean(codex) };
  if (!codex) return { command: "doctor", status: "blocked", offline: false, checks, actions: [] };
  try {
    execute(codex, ["login", "status"]);
    checks.login = { ok: true };
    const state = await inspectCodex(codex);
    const conflict = conflictReason(state);
    checks.marketplace = { ok: Boolean(marketplaceEntry(state.marketplaces)) && !conflict };
    checks.installedPlugin = { ok: Boolean(pluginEntry(state.plugins)) };
    let mcp = null;
    if (checks.installedPlugin.ok) {
      try {
        mcp = execute(codex, ["mcp", "get", MCP, "--json"], { json: true });
      } catch {
        // A newly installed plugin is not loaded into the current Codex process yet.
      }
    }
    checks.mcp = { ok: mcp?.name === MCP && mcp?.enabled !== false };
    return {
      command: "doctor",
      status: conflict || !checks.marketplace.ok || !checks.installedPlugin.ok ? "blocked" : checks.mcp.ok ? "ready" : "restart_required",
      offline: false,
      checks,
      actions: [],
      ...(conflict ? { reason: conflict } : {}),
    };
  } catch (error) {
    checks.login = { ok: false };
    return { command: "doctor", status: "blocked", offline: false, checks, actions: [], reason: error.message };
  }
}

async function bootstrap(options) {
  if (options.dryRun) {
    return {
      command: "bootstrap", status: "restart_required", dryRun: true,
      actions: [
        action("add marketplace", ["plugin", "marketplace", "add", MARKETPLACE_SOURCE, "--ref", MARKETPLACE_REF]),
        action("install plugin", ["plugin", "add", PLUGIN_ID]),
      ],
    };
  }
  const checks = await runtimeChecks();
  if (!checksReady(checks)) return { command: "bootstrap", status: "blocked", dryRun: false, checks, actions: [], reason: "required runtimes are missing" };
  const codex = await resolveCodex();
  if (!codex) return { command: "bootstrap", status: "blocked", dryRun: false, checks, actions: [], reason: "Codex CLI was not found" };
  try {
    execute(codex, ["login", "status"]);
    checks.login = { ok: true };
  } catch {
    checks.login = { ok: false };
    return { command: "bootstrap", status: "blocked", dryRun: false, checks, actions: [], reason: "Codex is not logged in" };
  }
  let state = await inspectCodex(codex);
  const conflict = conflictReason(state);
  if (conflict) return { command: "bootstrap", status: "blocked", dryRun: false, checks, actions: [], reason: conflict };
  const actions = [];
  if (!marketplaceEntry(state.marketplaces)) {
    const item = action("add marketplace", ["plugin", "marketplace", "add", MARKETPLACE_SOURCE, "--ref", MARKETPLACE_REF]);
    runAction(codex, item, false);
    actions.push(item);
    state = await inspectCodex(codex);
  }
  if (!pluginEntry(state.plugins)) {
    const item = action("install plugin", ["plugin", "add", PLUGIN_ID]);
    runAction(codex, item, false);
    actions.push(item);
  }
  let mcpReady = false;
  if (actions.length === 0) {
    try {
      const mcp = execute(codex, ["mcp", "get", MCP, "--json"], { json: true });
      mcpReady = mcp?.name === MCP && mcp?.enabled !== false;
    } catch {
      // A full Codex restart loads the newly installed MCP into later tasks.
    }
  }
  return { command: "bootstrap", status: actions.length || !mcpReady ? "restart_required" : "ready", dryRun: false, checks, actions };
}

async function update(options) {
  const planned = [
    action("upgrade marketplace", ["plugin", "marketplace", "upgrade", MARKETPLACE]),
    action("refresh plugin", ["plugin", "add", PLUGIN_ID]),
  ];
  if (options.dryRun) return { command: "update", status: "restart_required", dryRun: true, actions: planned };
  const codex = await resolveCodex();
  if (!codex) return { command: "update", status: "blocked", dryRun: false, actions: [], reason: "Codex CLI was not found" };
  const before = await inspectCodex(codex);
  const conflict = conflictReason(before);
  if (conflict) return { command: "update", status: "blocked", dryRun: false, actions: [], reason: conflict };
  if (!marketplaceEntry(before.marketplaces)) return { command: "update", status: "blocked", dryRun: false, actions: [], reason: "run bootstrap before update" };
  runAction(codex, planned[0], false);
  const available = execute(codex, ["plugin", "list", "--marketplace", MARKETPLACE, "--available", "--json"], { json: true });
  const installed = pluginEntry(available);
  const candidate = (available.available || []).find(({ name }) => name === PLUGIN);
  const actions = [planned[0]];
  if (!installed || (candidate?.version && candidate.version !== installed.version)) {
    // Codex installs the new cache entry before switching the enabled plugin. Never remove the
    // working version first: a failed refresh must leave the previous installation available.
    runAction(codex, planned[1], false);
    actions.push(planned[1]);
  }
  return { command: "update", status: actions.length > 1 ? "restart_required" : "ready", dryRun: false, actions };
}

async function uninstall(options) {
  const remove = action("remove plugin", ["plugin", "remove", PLUGIN_ID]);
  if (options.dryRun) return { command: "uninstall", status: "ready", dryRun: true, actions: [remove] };
  const codex = await resolveCodex();
  if (!codex) return { command: "uninstall", status: "blocked", dryRun: false, actions: [], reason: "Codex CLI was not found" };
  const state = await inspectCodex(codex);
  const actions = [];
  if (pluginEntry(state.plugins, PLUGIN_ID, { includeDisabled: true })) {
    runAction(codex, remove, false);
    actions.push(remove);
  }
  return { command: "uninstall", status: actions.length ? "restart_required" : "ready", dryRun: false, actions };
}

function printResult(result, json) {
  if (json) {
    process.stdout.write(`${JSON.stringify(result)}\n`);
    return;
  }
  process.stdout.write(`JewelryDesignCodex ${result.command}: ${result.status}\n`);
  for (const item of result.actions || []) process.stdout.write(`- ${item.label}\n`);
  if (result.reason) process.stderr.write(`${result.reason}\n`);
}

async function main(argv = process.argv.slice(2)) {
  let options;
  try {
    options = parseArgs(argv);
    if (options.offline && options.command !== "doctor") throw new Error("--offline is only supported by doctor");
    const handlers = { bootstrap, doctor, update, uninstall };
    const result = await handlers[options.command](options);
    printResult(result, options.json);
    return result.status === "blocked" ? 1 : 0;
  } catch (error) {
    const result = { command: options?.command || argv[0] || "doctor", status: "blocked", reason: error.message, actions: [] };
    printResult(result, options?.json || argv.includes("--json"));
    return 1;
  }
}

const isDirectRun = process.argv[1]
  && realpathSync(fileURLToPath(import.meta.url)) === realpathSync(resolve(process.argv[1]));
if (isDirectRun) process.exitCode = await main();

export { main };
