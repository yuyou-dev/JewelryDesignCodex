#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { delimiter, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { resolveCodex, resolvePython } from "../runtime/runtime.mjs";

const TOOLS = {
  image2: "jewelry_image2_tool.py",
  remix: "jewelry_remix.py",
  "visual-workbench": "jewelry_visual_workbench.py",
};

function usage() {
  return [
    "Usage: node scripts/jdc.mjs <image2|remix|visual-workbench> [arguments]",
    "",
    "Runs the plugin's bundled Python tools with one portable runtime resolver.",
  ].join("\n");
}

async function main(argv = process.argv.slice(2)) {
  const [tool, ...args] = argv;
  if (!tool || tool === "--help" || tool === "-h") {
    process.stdout.write(`${usage()}\n`);
    return 0;
  }
  const script = TOOLS[tool];
  if (!script) {
    process.stderr.write(`Unknown JewelryDesignCodex tool: ${tool}\n${usage()}\n`);
    return 2;
  }
  const python = await resolvePython();
  if (!python) {
    process.stderr.write("Python 3.10 or newer was not found. Run the JewelryDesignCodex bootstrap first.\n");
    return 127;
  }
  const codex = await resolveCodex();
  const env = { ...process.env };
  if (codex) env.PATH = [dirname(codex), env.PATH].filter(Boolean).join(delimiter);
  const result = spawnSync(
    python.command,
    [...python.argsPrefix, new URL(script, import.meta.url), ...args].map((value) => value instanceof URL ? fileURLToPath(value) : value),
    { stdio: "inherit", windowsHide: true, env },
  );
  if (result.error) {
    process.stderr.write(`Unable to start ${tool}: ${result.error.message}\n`);
    return 1;
  }
  return result.status ?? 1;
}

const isDirectRun = process.argv[1]
  && realpathSync(fileURLToPath(import.meta.url)) === realpathSync(resolve(process.argv[1]));
if (isDirectRun) process.exitCode = await main();

export { main };
