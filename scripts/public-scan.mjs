#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repository = resolve(fileURLToPath(new URL("../", import.meta.url)));
const ignoredContentFiles = new Set([
  "scripts/public-scan.mjs",
  "tests/public-release.test.mjs",
]);
// Verified through GitHub's public-emails API for yuyou-dev. Public profile identity is allowed;
// machine-local, private, or unverified addresses remain forbidden.
const allowedCommitEmails = new Set([
  "noreply@github.com",
  "yy18314@gmail.com",
]);
const forbiddenNames = [
  /(?:^|\/)(?:\.DS_Store|__pycache__)(?:\/|$)/,
  /\.pyc$/,
  /(?:^|\/)\.env(?:\.|$)/,
  /(?:^|\/)(?:auth|credentials?)\.json$/i,
  /(?:^|\/)id_(?:rsa|ed25519)(?:\.pub)?$/i,
];
const forbiddenContent = [
  ["macOS user home", /\/Users\/[A-Za-z0-9._-]+\//],
  ["Windows user home", /[A-Za-z]:\\Users\\[^\\\r\n]+\\/],
  ["Linux user home", /\/home\/[A-Za-z0-9._-]+\//],
  ["private source repository", /SVT-Jewelry(?:DesignPlugins|-Skills-Image-2)/],
  ["Codex task link", /codex:\/\/threads\//],
  ["GitHub token", /gh[opusr]_[A-Za-z0-9_]{20,}/],
  ["OpenAI-style secret", /sk-[A-Za-z0-9_-]{20,}/],
  ["Slack token", /xox[baprs]-[A-Za-z0-9-]{10,}/],
  ["private key", /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/],
  ["bearer credential", /Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{12,}/i],
  ["assigned API key", /(?:OPENAI_API_KEY|API_KEY|CLIENT_SECRET)\s*=\s*["']?[^\s"']{12,}/i],
  ["Codex credential file", /\.codex[\\/]auth\.json/],
];

function files() {
  const output = execFileSync("git", ["ls-files", "--cached", "--others", "--exclude-standard", "-z"], {
    cwd: repository,
    encoding: "buffer",
  });
  return output.toString("utf8").split("\0").filter(Boolean);
}

const candidates = files();
const findings = [];

try {
  // GitHub Actions checks pull requests through a synthetic merge commit that is never published
  // to the protected, linear-history main branch. Scan every real (non-merge) source commit.
  const identities = execFileSync("git", ["log", "--no-merges", "--format=%ae%x00%ce", "--all"], {
    cwd: repository,
    encoding: "utf8",
  }).split("\n").filter(Boolean);
  for (const identity of identities) {
    for (const email of identity.split("\0")) {
      if (email && !allowedCommitEmails.has(email) && !email.endsWith("@users.noreply.github.com")) {
        findings.push({ file: ".git", rule: "public commit email must be GitHub noreply or an approved public profile address" });
      }
    }
  }
} catch {
  findings.push({ file: ".git", rule: "unable to verify public commit identities" });
}

for (const file of candidates) {
  const normalized = file.replaceAll("\\", "/");
  if (!existsSync(resolve(repository, file))) continue;
  for (const pattern of forbiddenNames) {
    if (pattern.test(normalized)) findings.push({ file: normalized, rule: "forbidden file name" });
  }
  if (ignoredContentFiles.has(normalized)) continue;
  const text = readFileSync(resolve(repository, file)).toString("utf8");
  for (const [rule, pattern] of forbiddenContent) {
    if (pattern.test(text)) findings.push({ file: normalized, rule });
  }
}

if (findings.length) {
  for (const finding of findings) process.stderr.write(`${finding.file}: ${finding.rule}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`Public release scan passed (${candidates.length} files).\n`);
}
