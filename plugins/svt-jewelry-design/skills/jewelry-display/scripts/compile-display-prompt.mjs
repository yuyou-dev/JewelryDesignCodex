#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const skillDir = path.resolve(__dirname, "..");
const referencesDir = path.join(skillDir, "references");
const modesPath = path.join(referencesDir, "display-modes.json");
const systemPromptPath = path.join(referencesDir, "product-display-image2-system-prompt.md");
const directImageWorkerGuard = "Direct image-generation worker mode: Use the built-in image generation tool now. Do not inspect repository files. Do not read skills or documentation. Do not run shell commands. Do not create, edit, move, copy, save, or write files yourself. Do not create jobs. Do not update task state. Do not assemble reports. Do not perform post-processing. Return only the generated image result.";

function usage() {
  return `Usage:
  node compile-display-prompt.mjs --brief <brief.json> --mode <mode-id> --count <n> --out <dir> [--aspect-ratio <ratio>] [--grammar-tags <tag,tag>]

Outputs:
  shot-plans.json
  review-checklist.json
  prompts/<shot-id>.prompt.txt`;
}

function parseArgs(argv) {
  const parsed = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      throw new Error(`Unexpected positional argument: ${token}`);
    }
    const key = token.slice(2);
    const value = argv[i + 1];
    if (!value || value.startsWith("--")) {
      parsed[key] = true;
    } else {
      parsed[key] = value;
      i += 1;
    }
  }
  return parsed;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function list(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  return String(value).split(",").map((item) => item.trim()).filter(Boolean);
}

function sentence(value, fallback = "not specified") {
  if (!value) return fallback;
  if (Array.isArray(value)) return value.filter(Boolean).join("; ");
  if (typeof value === "object") return Object.entries(value).map(([key, val]) => `${key}: ${sentence(val, "")}`).join("; ");
  return String(value);
}

function normalizeBrief(rawBrief) {
  const materials = list(rawBrief.materials);
  const gemstones = list(rawBrief.gemstones || rawBrief.stones);
  const constraints = list(rawBrief.constraints || rawBrief.must_keep);
  return {
    product_name: rawBrief.product_name || rawBrief.name || "unnamed jewelry product",
    category: rawBrief.category || rawBrief.type || "jewelry",
    materials,
    gemstones,
    construction: rawBrief.construction || rawBrief.structure || "",
    design: rawBrief.design || rawBrief.description || "",
    product_truth: rawBrief.product_truth || rawBrief.truth || "",
    scale: rawBrief.scale || "",
    constraints,
    forbidden: list(rawBrief.forbidden),
  };
}

function extractSystemPrompt() {
  const markdown = fs.readFileSync(systemPromptPath, "utf8");
  const match = markdown.match(/## System Prompt\s+```text\s*([\s\S]*?)\s*```/);
  if (!match) throw new Error(`System prompt block not found in ${systemPromptPath}`);
  return match[1].trim();
}

function getMode(id) {
  const modesDoc = readJson(modesPath);
  const mode = modesDoc.modes.find((item) => item.id === id);
  if (!mode) {
    const known = modesDoc.modes.map((item) => item.id).join(", ");
    throw new Error(`Unknown display mode "${id}". Known modes: ${known}`);
  }
  return { modesDoc, mode };
}

function choose(items, index) {
  if (!Array.isArray(items) || items.length === 0) return "";
  return items[index % items.length];
}

function buildProductTruth(brief) {
  const lines = [
    `product name: ${brief.product_name}`,
    `category: ${brief.category}`,
    `materials: ${brief.materials.length ? brief.materials.join(", ") : "not specified"}`,
    `gemstones and decorative stones: ${brief.gemstones.length ? brief.gemstones.join(", ") : "not specified"}`,
    `construction: ${sentence(brief.construction)}`,
    `design identity: ${sentence(brief.design)}`,
    `scale and wearable logic: ${sentence(brief.scale)}`,
    `locked product truth: ${sentence(brief.product_truth)}`,
  ];
  if (brief.constraints.length) lines.push(`must keep: ${brief.constraints.join("; ")}`);
  return lines.join("\n");
}

function buildShot({ brief, mode, aspectRatio, grammarTags, index, count }) {
  const id = `${mode.id}-${String(index + 1).padStart(2, "0")}`;
  const composition = choose(mode.composition_templates, index);
  const support = choose(mode.support_physics, index);
  const lighting = choose(mode.lighting_camera, index);
  const propForbidden = [...(mode.forbidden || []), ...brief.forbidden];
  const productTruth = buildProductTruth(brief);
  const negativeSpace = `${mode.negative_space_ratio} calm negative space; product scale: ${mode.product_scale}; prop policy: ${mode.prop_policy}`;
  const supportContact = `${support}; occlusion limit: support may hide only non-selling back/underside contact points; never cover hero stones, prongs, bezels, pendant face, earring drops, clasp logic, ring shank closure, bail, or visible connection points.`;
  const prompt = [
    "$imagegen",
    directImageWorkerGuard,
    "Use gpt-image-2 to generate one finished high-jewelry product display image. Only return the generated image; do not write files, do not create jobs, do not update task state, do not assemble reports, and do not perform post-processing.",
    "",
    `Output type and aspect ratio: finished high-jewelry product display image, ${aspectRatio}.`,
    "",
    "PRODUCT TRUTH LOCK:",
    productTruth,
    "",
    "DISPLAY MODE:",
    `${mode.id} (${mode.label}). This is product display, not a campaign poster.`,
    "",
    "COMPOSITION BLUEPRINT:",
    `${composition}. Use this as the shot plan ${index + 1} of ${count}. Keep the jewelry as the sharpest and highest-value visual signal.`,
    "",
    "SUPPORT PHYSICS:",
    supportContact,
    "",
    "LIGHTING AND CAMERA:",
    lighting,
    "",
    "NEGATIVE SPACE AND BACKGROUND:",
    negativeSpace,
    "",
    "REFERENCE GRAMMAR TAGS:",
    grammarTags.length ? grammarTags.join(", ") : "none supplied; follow the selected display mode grammar.",
    "",
    "FORBIDDEN ELEMENTS AND NEGATIVE CONSTRAINTS:",
    [
      "no readable brand text, logo, watermark, price, QR code, social handle, label, magazine layout, poster title block, collage, or campaign copy",
      "no extra jewelry pieces beyond the requested product",
      "no random bouquet, busy tabletop, dirty shadow, noisy background, impossible floating, broken chain continuity, cropped product edge, distorted hand, melted metal, or plastic-looking gems",
      propForbidden.length ? `mode-specific forbidden cues: ${propForbidden.join(", ")}` : "",
      "repeat material truth exactly; do not redesign the jewelry or substitute materials",
    ].filter(Boolean).join("; "),
  ].join("\n");

  return {
    id,
    display_mode: mode.id,
    aspect_ratio: aspectRatio,
    grammar_tags: grammarTags,
    product_truth: productTruth,
    composition_blueprint: composition,
    support_physics: supportContact,
    lighting_camera: lighting,
    negative_space_background: negativeSpace,
    forbidden_elements: propForbidden,
    prompt,
    prompt_file: path.join("prompts", `${id}.prompt.txt`),
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    return;
  }
  for (const required of ["brief", "mode", "out"]) {
    if (!args[required]) throw new Error(`Missing --${required}\n${usage()}`);
  }

  const count = Number.parseInt(args.count || "1", 10);
  if (!Number.isInteger(count) || count < 1) throw new Error("--count must be a positive integer");

  const briefPath = path.resolve(args.brief);
  const outDir = path.resolve(args.out);
  const brief = normalizeBrief(readJson(briefPath));
  const { modesDoc, mode } = getMode(args.mode);
  const aspectRatio = args["aspect-ratio"] || mode.default_aspect_ratio || "4:5";
  const grammarTags = list(args["grammar-tags"]);
  const systemPrompt = extractSystemPrompt();

  fs.mkdirSync(path.join(outDir, "prompts"), { recursive: true });

  const shots = Array.from({ length: count }, (_, index) => buildShot({
    brief,
    mode,
    aspectRatio,
    grammarTags,
    index,
    count,
  }));

  for (const shot of shots) {
    fs.writeFileSync(path.join(outDir, shot.prompt_file), `${shot.prompt}\n`, "utf8");
  }

  const shotPlans = {
    schema_version: 1,
    role: "jewelry-display",
    compile_order: modesDoc.compile_order,
    source_brief: path.relative(process.cwd(), briefPath),
    system_prompt_source: path.relative(process.cwd(), systemPromptPath),
    system_prompt_excerpt: systemPrompt.split(/\r?\n/).slice(0, 6).join("\n"),
    mode: mode.id,
    aspect_ratio: aspectRatio,
    count,
    shots: shots.map(({ prompt, ...shot }) => shot),
  };

  const reviewChecklist = {
    schema_version: 1,
    role: "jewelry-display",
    pass_threshold: {
      total_minimum: 24,
      minimum_per_criterion: 3,
      poster_drift_minimum: 4,
    },
    criteria: [
      "product_readability",
      "material_truth",
      "composition_quality",
      "negative_space_quality",
      "support_credibility",
      "poster_drift_control",
    ],
    shots: shots.map((shot) => ({
      id: shot.id,
      prompt_file: shot.prompt_file,
      checklist: [
        "product is first visual signal",
        "materials match product truth",
        "display mode is clear and not mixed",
        "negative space is intentional and clean",
        "support contact and gravity are believable",
        "no poster typography, brand text, price, QR code, watermark, or collage",
      ],
    })),
  };

  fs.writeFileSync(path.join(outDir, "shot-plans.json"), `${JSON.stringify(shotPlans, null, 2)}\n`, "utf8");
  fs.writeFileSync(path.join(outDir, "review-checklist.json"), `${JSON.stringify(reviewChecklist, null, 2)}\n`, "utf8");
  console.log(`Compiled ${shots.length} jewelry display prompt(s) to ${outDir}`);
}

try {
  main();
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
