#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { resolvePython } from "../plugins/svt-jewelry-design/runtime/runtime.mjs";

const root = resolve(fileURLToPath(new URL("../", import.meta.url)));

function collect(directory) {
  const files = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if ([".git", "node_modules", "vendor", "__pycache__"].includes(entry.name)) continue;
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...collect(path));
    else if (entry.name.endsWith(".test.mjs")) files.push(path);
  }
  return files;
}

function run(command, args, cwd = root) {
  const result = spawnSync(command, args, { cwd, stdio: "inherit", windowsHide: true });
  if (result.error) throw result.error;
  return result.status ?? 1;
}

const nodeStatus = run(process.execPath, ["--test", ...collect(root)]);
if (nodeStatus !== 0) process.exit(nodeStatus);

const python = await resolvePython();
if (!python) {
  process.stderr.write("Python 3.10 or newer is required to run the bundled runner tests.\n");
  process.exit(1);
}
const pluginRoot = join(root, "plugins", "svt-jewelry-design");
process.exit(run(python.command, [
  ...python.argsPrefix,
  "-m", "unittest", "discover", "-b",
  "-s", "tests",
  "-p", "test_*.py",
], pluginRoot));
