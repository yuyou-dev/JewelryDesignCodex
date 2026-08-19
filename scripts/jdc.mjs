#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync, realpathSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { resolveCodex, resolveExecutable, resolvePython } from "../plugins/svt-jewelry-design/runtime/runtime.mjs";

const MARKETPLACE = "jewelry-design-codex";
const MARKETPLACE_SOURCE = "yuyou-dev/JewelryDesignCodex";
const MARKETPLACE_REF = "v0.2.0";
const TARGET_VERSION = "0.2.0";
const PLUGIN = "svt-jewelry-design";
const PLUGIN_ID = `${PLUGIN}@${MARKETPLACE}`;
const OPTIONAL_PLUGIN_IDS = [
  `svt-jewelry-video@${MARKETPLACE}`,
  `svt-jewelry-feishu@${MARKETPLACE}`,
];
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

function versionOf(entry) {
  return typeof entry?.version === "string" && entry.version ? entry.version : null;
}

function enabledOfficialPlugins(payload) {
  const allowed = new Set([PLUGIN_ID, ...OPTIONAL_PLUGIN_IDS]);
  return installedEntries(payload)
    .filter(({ pluginId, installed, enabled }) => allowed.has(pluginId) && installed !== false && enabled !== false)
    .map(({ pluginId }) => pluginId);
}

function updateResult(overrides = {}) {
  return {
    command: "update",
    status: "blocked",
    dryRun: false,
    fromVersion: null,
    toVersion: TARGET_VERSION,
    migration: "fixed-release-ref",
    restoredPlugins: [],
    rolledBack: false,
    actions: [],
    ...overrides,
  };
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
    action("remove old fixed-ref marketplace", ["plugin", "marketplace", "remove", MARKETPLACE]),
    action("add v0.2.0 marketplace", ["plugin", "marketplace", "add", MARKETPLACE_SOURCE, "--ref", MARKETPLACE_REF]),
    action("restore core plugin", ["plugin", "add", PLUGIN_ID]),
  ];
  if (options.dryRun) return updateResult({ status: "restart_required", dryRun: true, actions: planned });
  const codex = await resolveCodex();
  if (!codex) return updateResult({ reason: "Codex CLI was not found" });
  const before = await inspectCodex(codex);
  const conflict = conflictReason(before);
  if (conflict) return updateResult({ reason: conflict });
  if (!marketplaceEntry(before.marketplaces)) return updateResult({ reason: "JewelryDesignCodex is not installed; follow INSTALL.md first" });
  const current = pluginEntry(before.plugins, PLUGIN_ID, { includeDisabled: true });
  const fromVersion = versionOf(current);
  if (!current) return updateResult({ fromVersion, reason: "the core plugin is not installed; follow INSTALL.md first" });
  const restoreIds = enabledOfficialPlugins(before.plugins);
  if (!restoreIds.includes(PLUGIN_ID)) restoreIds.unshift(PLUGIN_ID);

  if (fromVersion === TARGET_VERSION && current.enabled !== false) {
    const refresh = action("verify v0.2.0 marketplace", ["plugin", "marketplace", "upgrade", MARKETPLACE]);
    runAction(codex, refresh, false);
    const actions = [refresh];
    let after = await inspectCodex(codex);
    for (const id of restoreIds) {
      const entry = pluginEntry(after.plugins, id);
      if (entry && versionOf(entry) === TARGET_VERSION) continue;
      const restore = action(`refresh ${id}`, ["plugin", "add", id]);
      runAction(codex, restore, false); actions.push(restore);
      after = await inspectCodex(codex);
    }
    const installed = pluginEntry(after.plugins);
    return updateResult({
      status: !(installed && versionOf(installed) === TARGET_VERSION) ? "blocked" : actions.length > 1 ? "restart_required" : "ready",
      fromVersion,
      migration: "already-current",
      restoredPlugins: restoreIds,
      actions,
      ...(!(installed && versionOf(installed) === TARGET_VERSION) ? { reason: "v0.2.0 verification failed" } : {}),
    });
  }

  const oldRef = fromVersion ? `v${fromVersion}` : null;
  const actions = [];
  let removedOld = false;
  try {
    runAction(codex, planned[0], false); actions.push(planned[0]); removedOld = true;
    runAction(codex, planned[1], false); actions.push(planned[1]);
    for (const id of restoreIds) {
      const item = action(`restore ${id}`, ["plugin", "add", id]);
      runAction(codex, item, false); actions.push(item);
    }
    const after = await inspectCodex(codex);
    const installed = pluginEntry(after.plugins);
    if (!installed || versionOf(installed) !== TARGET_VERSION) throw new Error("target plugin version verification failed");
    return updateResult({ status: "restart_required", fromVersion, restoredPlugins: restoreIds, actions });
  } catch (error) {
    let rolledBack = false;
    if (removedOld && oldRef) {
      try {
        const configured = marketplaceEntry((await inspectCodex(codex)).marketplaces);
        if (configured) {
          const removePartial = action("remove incomplete target marketplace", ["plugin", "marketplace", "remove", MARKETPLACE]);
          runAction(codex, removePartial, false); actions.push(removePartial);
        }
        const restoreMarket = action(`restore ${oldRef} marketplace`, ["plugin", "marketplace", "add", MARKETPLACE_SOURCE, "--ref", oldRef]);
        runAction(codex, restoreMarket, false); actions.push(restoreMarket);
        for (const id of restoreIds) {
          const restore = action(`restore previous ${id}`, ["plugin", "add", id]);
          runAction(codex, restore, false); actions.push(restore);
        }
        const rolledState = await inspectCodex(codex);
        rolledBack = versionOf(pluginEntry(rolledState.plugins, PLUGIN_ID, { includeDisabled: true })) === fromVersion;
      } catch {
        rolledBack = false;
      }
    }
    return updateResult({ fromVersion, restoredPlugins: restoreIds, rolledBack, actions, reason: error.message });
  }
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
