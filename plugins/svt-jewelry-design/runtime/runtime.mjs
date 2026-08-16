import { constants, existsSync, realpathSync } from "node:fs";
import { access } from "node:fs/promises";
import { delimiter, extname, isAbsolute, join } from "node:path";

const WINDOWS_EXTENSIONS = [".EXE", ".CMD", ".BAT", ".COM"];

async function isExecutable(path, platform = process.platform) {
  if (!existsSync(path)) return false;
  if (platform === "win32") return true;
  try {
    await access(path, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function candidateNames(name, env, platform) {
  if (platform !== "win32" || extname(name)) return [name];
  const extensions = (env.PATHEXT || WINDOWS_EXTENSIONS.join(";"))
    .split(";")
    .filter(Boolean);
  return [name, ...extensions.map((extension) => `${name}${extension.toLowerCase()}`)];
}

async function resolveExecutable(names, { env = process.env, platform = process.platform, explicit } = {}) {
  const requested = explicit?.trim();
  if (requested) {
    if (!isAbsolute(requested) || !(await isExecutable(requested, platform))) {
      throw new Error(`Configured runtime is not an executable absolute path: ${requested}`);
    }
    return realpathSync(requested);
  }
  const directories = (env.PATH || "").split(delimiter).filter(Boolean);
  for (const name of names) {
    if (isAbsolute(name) && (await isExecutable(name, platform))) return realpathSync(name);
    for (const directory of directories) {
      for (const candidate of candidateNames(name, env, platform)) {
        const path = join(directory, candidate);
        if (await isExecutable(path, platform)) return realpathSync(path);
      }
    }
  }
  return null;
}

async function resolvePython(options = {}) {
  const { env = process.env, platform = process.platform } = options;
  const command = await resolveExecutable(
    platform === "win32" ? ["python", "python3", "py"] : ["python3", "python"],
    { ...options, explicit: env.JDC_PYTHON_BIN },
  );
  if (!command) return null;
  return { command, argsPrefix: platform === "win32" && /(?:^|[\\/])py(?:\.exe)?$/i.test(command) ? ["-3"] : [] };
}

async function resolveCodex(options = {}) {
  const { env = process.env, platform = process.platform } = options;
  if (env.JDC_CODEX_BIN?.trim()) {
    return resolveExecutable([], { ...options, explicit: env.JDC_CODEX_BIN });
  }
  const bundled = [];
  if (platform === "darwin") {
    const roots = [env.HOME && join(env.HOME, "Applications"), "/Applications"].filter(Boolean);
    for (const root of roots) {
      for (const app of ["Codex.app", "ChatGPT.app"]) {
        bundled.push(
          join(root, app, "Contents", "Resources", "codex"),
          join(root, app, "Contents", "Resources", "bin", "codex"),
          join(root, app, "Contents", "MacOS", "codex"),
        );
      }
    }
  } else if (platform === "win32") {
    const roots = [...new Set([
      env.LOCALAPPDATA && join(env.LOCALAPPDATA, "Programs"),
      env.ProgramFiles,
      env.PROGRAMFILES,
      env.ProgramW6432,
    ].filter(Boolean))];
    for (const root of roots) {
      bundled.push(
        join(root, "Codex", "resources", "codex.exe"),
        join(root, "ChatGPT", "resources", "codex.exe"),
        join(root, "OpenAI", "ChatGPT", "resources", "codex.exe"),
      );
    }
  }
  const desktopCli = await resolveExecutable(bundled, { ...options, env, platform });
  return desktopCli || resolveExecutable(["codex"], { ...options, env, platform });
}

export { resolveCodex, resolveExecutable, resolvePython };
