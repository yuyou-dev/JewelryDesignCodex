#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const skillDir = path.resolve(__dirname, "..");
const referencesDir = path.join(skillDir, "references");
const compileScript = path.join(__dirname, "compile-display-prompt.mjs");

const requiredModeIds = [
  "white_gallery_product",
  "botanical_negative_space",
  "botanical_support_still_life",
  "asymmetric_suspended_display",
  "silk_suspension_display",
  "editorial_still_life",
  "hand_wearing_product_macro",
  "craft_macro",
];

const sampleBriefs = [
  ["lapis-platinum-white-jade-ring", "botanical_negative_space"],
  ["platinum-diamond-necklace", "silk_suspension_display"],
  ["high-jewelry-earrings", "asymmetric_suspended_display"],
];

const failures = [];

function fail(message) {
  failures.push(message);
}

function read(file) {
  return fs.readFileSync(file, "utf8");
}

function readJson(file) {
  return JSON.parse(read(file));
}

function assertIncludes(file, content, phrases) {
  for (const phrase of phrases) {
    if (!content.includes(phrase)) {
      fail(`${path.relative(process.cwd(), file)} missing required phrase: ${phrase}`);
    }
  }
}

function checkModes() {
  const file = path.join(referencesDir, "display-modes.json");
  const data = readJson(file);
  const ids = data.modes.map((mode) => mode.id).sort();
  if (JSON.stringify(ids) !== JSON.stringify([...requiredModeIds].sort())) {
    fail(`display-modes.json mode ids mismatch. Expected ${requiredModeIds.join(", ")}; found ${ids.join(", ")}`);
  }
  for (const mode of data.modes) {
    for (const field of ["id", "label", "default_aspect_ratio", "negative_space_ratio", "product_scale", "prop_policy"]) {
      if (!mode[field]) fail(`display-modes.json ${mode.id || "(unknown mode)"} missing ${field}`);
    }
    for (const field of ["composition_templates", "support_physics", "lighting_camera", "forbidden"]) {
      if (!Array.isArray(mode[field]) || mode[field].length === 0) {
        fail(`display-modes.json ${mode.id} must define non-empty ${field}`);
      }
    }
  }
  for (const step of ["product_truth", "display_mode", "composition_blueprint", "support_physics", "lighting_camera", "negative_space_background", "forbidden_elements"]) {
    if (!data.compile_order.includes(step)) fail(`display-modes.json compile_order missing ${step}`);
  }
}

function checkReferences() {
  const grammarPath = path.join(referencesDir, "display-grammar.md");
  const rubricPath = path.join(referencesDir, "review-rubric.md");
  const systemPromptPath = path.join(referencesDir, "product-display-image2-system-prompt.md");
  assertIncludes(grammarPath, read(grammarPath), [
    "Reference Deconstruction Checklist",
    "Negative Space Rules",
    "Asymmetry Rules",
    "Support Physics",
    "Product-Display Versus Poster",
    "Prompt Blueprint",
  ]);
  assertIncludes(rubricPath, read(rubricPath), [
    "Product Readability",
    "Material Truth",
    "Composition Quality",
    "Negative Space Quality",
    "Support Credibility",
    "Poster Drift Control",
  ]);
  assertIncludes(systemPromptPath, read(systemPromptPath), [
    "single source of truth",
    "display-grammar.md",
    "display-modes.json",
    "review-rubric.md",
    "product display, not a campaign poster",
  ]);
}

function checkCompilerWithSamples() {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "jewelry-display-v2-"));
  try {
    for (const [sampleName, mode] of sampleBriefs) {
      const briefPath = path.join(referencesDir, "sample-briefs", `${sampleName}.json`);
      if (!fs.existsSync(briefPath)) {
        fail(`Missing sample brief: ${path.relative(process.cwd(), briefPath)}`);
        continue;
      }
      const outDir = path.join(tempRoot, sampleName);
      execFileSync("node", [compileScript, "--brief", briefPath, "--mode", mode, "--count", "2", "--out", outDir], {
        cwd: process.cwd(),
        stdio: "pipe",
      });
      const shotPlansPath = path.join(outDir, "shot-plans.json");
      const reviewPath = path.join(outDir, "review-checklist.json");
      if (!fs.existsSync(shotPlansPath)) fail(`${sampleName} did not create shot-plans.json`);
      if (!fs.existsSync(reviewPath)) fail(`${sampleName} did not create review-checklist.json`);
      const shotPlans = readJson(shotPlansPath);
      if (shotPlans.shots.length !== 2) fail(`${sampleName} expected 2 shots, found ${shotPlans.shots.length}`);
      const ids = new Set();
      for (const shot of shotPlans.shots) {
        ids.add(shot.id);
        for (const field of ["product_truth", "display_mode", "composition_blueprint", "support_physics", "lighting_camera", "negative_space_background", "prompt_file"]) {
          if (!shot[field]) fail(`${sampleName}/${shot.id} missing ${field}`);
        }
        const promptPath = path.join(outDir, shot.prompt_file);
        if (!fs.existsSync(promptPath)) {
          fail(`${sampleName}/${shot.id} missing prompt file`);
          continue;
        }
        const prompt = read(promptPath);
        const firstLine = prompt.split(/\r?\n/, 1)[0];
        if (firstLine !== "$imagegen") fail(`${sampleName}/${shot.id} prompt must start with $imagegen`);
        for (const phrase of [
          "Direct image-generation worker mode",
          "Do not inspect repository files",
          "Do not read skills or documentation",
          "Do not run shell commands",
          "Return only the generated image result",
          "Use gpt-image-2",
          "Only return the generated image",
          "do not write files",
          "do not create jobs",
          "do not update task state",
          "do not assemble reports",
          "do not perform post-processing",
          "PRODUCT TRUTH LOCK",
          "DISPLAY MODE",
          "COMPOSITION BLUEPRINT",
          "SUPPORT PHYSICS",
          "occlusion limit",
          "FORBIDDEN ELEMENTS AND NEGATIVE CONSTRAINTS",
        ]) {
          if (!prompt.includes(phrase)) fail(`${sampleName}/${shot.id} prompt missing ${phrase}`);
        }
        for (const phrase of ["add-job", "generate --workspace", "assemble-markdown"]) {
          if (prompt.includes(phrase)) fail(`${sampleName}/${shot.id} prompt must not include runner command phrase: ${phrase}`);
        }
      }
      if (ids.size !== shotPlans.shots.length) fail(`${sampleName} shot ids are not unique`);
    }
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
}

checkModes();
checkReferences();
checkCompilerWithSamples();

if (failures.length > 0) {
  console.error(`Jewelry display V2 check failed:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}

console.log("Jewelry display V2 check passed.");
