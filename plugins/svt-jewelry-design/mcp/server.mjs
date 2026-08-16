#!/usr/bin/env node

import { randomUUID } from "node:crypto";
import { existsSync, lstatSync, mkdirSync, readFileSync, realpathSync, statSync, writeFileSync } from "node:fs";
import { basename, extname, isAbsolute, join, relative, resolve, sep } from "node:path";
import readline from "node:readline";
import { fileURLToPath } from "node:url";
import { compactImage } from "./portable-image.mjs";

const SERVER_VERSION = "0.1.0";
const RESOURCE_URI = "ui://svt-jewelry/followup-questions/v4.html";
const COMPARISON_RESOURCE_URI = "ui://svt-jewelry/retouch-comparison/v10.html";
const REMIX_BRIEF_RESOURCE_URI = "ui://svt-jewelry/remix-brief/v7.html";
const REMIX_GALLERY_RESOURCE_URI = "ui://svt-jewelry/remix-gallery/v7.html";
const CREATION_BRIEF_RESOURCE_URI = "ui://svt-jewelry/creation-brief/v4.html";
const CREATION_GALLERY_RESOURCE_URI = "ui://svt-jewelry/creation-gallery/v6.html";
const DESIGN_GALLERY_RESOURCE_URI = "ui://svt-jewelry/design-gallery/v2.html";
const VISUAL_WORKBENCH_RESOURCE_URI = "ui://svt-jewelry/visual-workbench/v6.html";
const RESOURCE_MIME_TYPE = "text/html;profile=mcp-app";
const widgetHtml = readFileSync(new URL("./jewelry-followup.html", import.meta.url), "utf8");
const brandAssets = {
  name: "苏哇科技",
  static: imageFileDataUri(new URL("../assets/brand/logo-static.png", import.meta.url), "image/png"),
  header: imageFileDataUri(new URL("../assets/brand/logo-header.webp", import.meta.url), "image/webp"),
  loading: imageFileDataUri(new URL("../assets/brand/logo-loading.webp", import.meta.url), "image/webp"),
};
const REMIX_DESIGN_SYSTEMS = ["gold", "gem_set"];
const remixTaxonomy = JSON.parse(readFileSync(new URL("../skills/jewelry-remix/references/remix-taxonomy.v2.json", import.meta.url), "utf8"));
const remixTaxonomyUi = {
  schemaVersion: remixTaxonomy.schema_version,
  designSystems: Object.fromEntries(Object.entries(remixTaxonomy.design_systems).map(([id, system]) => [id, {
    label: system.label,
    themes: system.themes.map(({ id: optionId, label }) => [optionId, label]),
    styles: system.styles.map(({ id: optionId, label }) => [optionId, label]),
    morphologies: system.morphologies.map(({ id: optionId, label }) => [optionId, label]),
    materials: system.materials.map(({ id: optionId, label }) => [optionId, label]),
  }])),
};
const comparisonHtml = brandedHtml("./jewelry-retouch-comparison.html");
const remixBriefHtml = brandedHtml("./jewelry-remix-brief.html");
const remixGalleryHtml = brandedHtml("./jewelry-remix-gallery.html");
const creationBriefHtml = brandedHtml("./jewelry-creation-brief.html");
const creationGalleryHtml = brandedHtml("./jewelry-creation-gallery.html");
const designGalleryHtml = brandedHtml("./jewelry-design-gallery.html");
const visualWorkbenchHtml = brandedHtml("./jewelry-visual-workbench.html");
const MAX_IMAGE_BYTES = 24 * 1024 * 1024;
const MAX_PREVIEW_CHARS = Number(process.env.SVT_JEWELRY_UI_PREVIEW_BUDGET_CHARS || 720 * 1024);

function imageFileDataUri(url, mimeType) {
  return `data:${mimeType};base64,${readFileSync(url).toString("base64")}`;
}

function brandedHtml(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8")
    .replaceAll("{{BRAND_NAME}}", brandAssets.name)
    .replaceAll("{{BRAND_STATIC_DATA_URI}}", brandAssets.static)
    .replaceAll("{{BRAND_HEADER_DATA_URI}}", brandAssets.header)
    .replaceAll("{{BRAND_LOADING_DATA_URI}}", brandAssets.loading)
    .replaceAll("{{REMIX_TAXONOMY_JSON}}", JSON.stringify(remixTaxonomyUi));
}

const optionSchema = {
  type: "object",
  required: ["id", "label"],
  properties: {
    id: { type: "string" },
    label: { type: "string" },
    description: { type: "string" },
    preview: { type: "string", description: "Optional self-contained data:image URL for a visual card." },
    previewPath: { type: "string", description: "Optional absolute local image path; the server prepares a bounded UI-only preview." },
  },
};

const fieldSchema = {
  type: "object",
  required: ["id", "label", "type"],
  properties: {
    id: { type: "string" },
    label: { type: "string" },
    type: { type: "string", enum: ["text", "single", "multi"] },
    description: { type: "string" },
    placeholder: { type: "string" },
    otherPlaceholder: { type: "string" },
    required: { type: "boolean" },
    options: { type: "array", minItems: 2, maxItems: 8, items: optionSchema },
  },
};

const formTool = {
  name: "ask_jewelry_followup_questions",
  title: "Ask jewelry follow-up questions",
  description:
    "Render one compact adaptive jewelry-design clarification card in Codex or another MCP Apps host. Ordinary clarification uses one consolidated round only. The narrow jewelry-grill-me exception may call this tool across multiple rounds, with at most four unresolved questions per round, until the user confirms the shared brief. Use only when answers change product identity or workflow; never ask for provider cost or internal job selection. Supports text, single-select, multi-select, explicit __other__ options, and one visual-choice field with up to eight self-contained or task-local previews. No file upload fields.",
  inputSchema: {
    type: "object",
    required: ["title", "fields"],
    properties: {
      title: { type: "string" },
      prompt: { type: "string" },
      submitLabel: { type: "string" },
      messagePrefix: { type: "string" },
      formId: { type: "string" },
      fields: { type: "array", minItems: 1, maxItems: 4, items: fieldSchema },
    },
  },
  annotations: { readOnlyHint: true, openWorldHint: false },
  _meta: {
    ui: { resourceUri: RESOURCE_URI },
    "openai/outputTemplate": RESOURCE_URI,
    "openai/toolInvocation/invoking": "正在准备珠宝设计问题",
    "openai/toolInvocation/invoked": "请确认设计方向",
  },
};

const comparisonTool = {
  name: "show_jewelry_retouch_comparison",
  title: "苏哇科技 · 珠宝精修对比",
  description:
    "Render one to eight read-only before/after drag comparisons after jewelry retouching succeeds. Use legacy beforePath/afterPath for one pair or pairs with stable RETOUCH-A..H ids for multiple images. Every path must be a real local file from the same task. This presentation tool does not retouch, approve, rank, or count as another deliverable. On success do not repeat compared images inline; use inline fallback only when unavailable or erroring.",
  inputSchema: {
    type: "object",
    properties: {
      beforePath: { type: "string", description: "Absolute local path to the source image." },
      afterPath: { type: "string", description: "Absolute local path to the retouched image." },
      pairs: {
        type: "array",
        minItems: 1,
        maxItems: 8,
        items: {
          type: "object",
          required: ["beforePath", "afterPath"],
          properties: {
            id: { type: "string", pattern: "^RETOUCH-[A-H]$" },
            title: { type: "string" },
            caption: { type: "string" },
            beforePath: { type: "string" },
            afterPath: { type: "string" },
            beforeLabel: { type: "string" },
            afterLabel: { type: "string" },
          },
        },
      },
      title: { type: "string" },
      caption: { type: "string" },
      beforeLabel: { type: "string" },
      afterLabel: { type: "string" },
      initialPairId: { type: "string", pattern: "^RETOUCH-[A-H]$" },
      initialPosition: { type: "number", minimum: 0, maximum: 100 },
    },
    anyOf: [{ required: ["pairs"] }, { required: ["beforePath", "afterPath"] }],
  },
  annotations: { readOnlyHint: true, openWorldHint: false },
  _meta: {
    ui: { resourceUri: COMPARISON_RESOURCE_URI },
    "openai/outputTemplate": COMPARISON_RESOURCE_URI,
    "openai/toolInvocation/invoking": "正在准备精修前后对比",
    "openai/toolInvocation/invoked": "可拖动查看精修对比",
  },
};

const remixBriefTool = {
  name: "ask_jewelry_remix_brief",
  title: "苏哇科技 · 爆款二创方向",
  description:
    "Render the dedicated compact intake for a jewelry 爆款二创 workflow after one real source jewelry image is available. This product-mode form may ask for 4 or 8 independent candidates, structure fidelity, intensity, fusion, theme, morphology, style, and material/craft. It does not upload files, choose provider cost or batch details, or generate images. Skip it when the user already supplied a complete remix brief.",
  inputSchema: {
    type: "object",
    properties: {
      title: { type: "string" },
      prompt: { type: "string" },
      formId: { type: "string" },
      hasReferenceImages: { type: "boolean" },
      defaults: {
        type: "object",
        properties: {
          count: { type: "integer", enum: [4, 8] },
          designSystem: { type: "string", enum: REMIX_DESIGN_SYSTEMS },
          structureFidelity: { type: "string", enum: ["high", "medium", "low"] },
          intensity: { type: "string", enum: ["subtle", "balanced", "bold"] },
          fusionStrategy: { type: "string", enum: ["shape_grafting", "pattern_translation", "structural_rebuild"] },
          themes: { type: "array", items: { type: "string" } },
          morphologies: { type: "array", items: { type: "string" } },
          styles: { type: "array", items: { type: "string" } },
          materials: { type: "array", items: { type: "string" } },
          customThemes: { type: "string" },
          customMorphologies: { type: "string" },
          customStyles: { type: "string" },
          customMaterials: { type: "string" },
          referenceRole: { type: "string" },
          direction: { type: "string" },
        },
      },
    },
  },
  annotations: { readOnlyHint: true, openWorldHint: false },
  _meta: {
    ui: { resourceUri: REMIX_BRIEF_RESOURCE_URI },
    "openai/outputTemplate": REMIX_BRIEF_RESOURCE_URI,
    "openai/toolInvocation/invoking": "正在准备爆款二创问卷",
    "openai/toolInvocation/invoked": "请确认二创方向",
  },
};

const remixCandidateSchema = {
  type: "object",
  required: ["id", "title", "path", "summary", "useCase"],
  properties: {
    id: { type: "string", pattern: "^REMIX-[A-H]$" },
    title: { type: "string" },
    path: { type: "string" },
    summary: { type: "string" },
    useCase: { type: "string" },
  },
};

const remixGalleryTool = {
  name: "show_jewelry_remix_gallery",
  title: "苏哇科技 · 爆款二创 Gallery",
  description:
    "Render the final read-only jewelry remix Gallery after exactly 4 or 8 independent candidate files exist. Every candidate compares against the same source image. Selection records one neutral stable asset context for the user's next instruction; it does not generate, approve, rank, mutate, or preselect another workflow. On success, do not repeat source/candidate images inline; use inline images only when this tool is unavailable or returns an error.",
  inputSchema: {
    type: "object",
    required: ["sourcePath", "candidates"],
    properties: {
      sourcePath: { type: "string", description: "Absolute local path to the source jewelry image." },
      title: { type: "string" },
      caption: { type: "string" },
      initialCandidateId: { type: "string", pattern: "^REMIX-[A-H]$" },
      initialPosition: { type: "number", minimum: 0, maximum: 100 },
      candidates: {
        oneOf: [
          { type: "array", minItems: 4, maxItems: 4, items: remixCandidateSchema },
          { type: "array", minItems: 8, maxItems: 8, items: remixCandidateSchema },
        ],
      },
    },
  },
  annotations: { readOnlyHint: true, openWorldHint: false },
  _meta: {
    ui: { resourceUri: REMIX_GALLERY_RESOURCE_URI },
    "openai/outputTemplate": REMIX_GALLERY_RESOURCE_URI,
    "openai/toolInvocation/invoking": "正在准备二创对比",
    "openai/toolInvocation/invoked": "可逐款滑动对比",
  },
};

const CREATION_WORKFLOWS = ["poster", "catalog", "display"];
const CREATION_GALLERY_WORKFLOWS = [
  ...CREATION_WORKFLOWS,
  "grid",
  "grid_redraw",
  "reference_sheet",
  "tryon",
];
const CREATION_BRIEF_FIELDS = {
  poster: ["mode", "aspectRatio", "composition", "typography"],
  catalog: ["mode", "channel", "background", "style"],
  display: ["mode", "aspectRatio", "sceneIntensity", "background"],
};

const creationBriefTool = {
  name: "ask_jewelry_creation_brief",
  title: "苏哇科技 · 珠宝视觉创作方向",
  description:
    "Render one compact tailored intake for jewelry poster, catalog, or product-display creation. Use only when an unresolved template/profile/display mode changes the creative family, and skip fields already answered by the user. It does not upload files, select provider cost, or override an explicit delivery count.",
  inputSchema: {
    type: "object",
    required: ["workflow"],
    properties: {
      workflow: { type: "string", enum: CREATION_WORKFLOWS },
      title: { type: "string" },
      prompt: { type: "string" },
      formId: { type: "string" },
      hasSourceImages: { type: "boolean" },
      unresolvedFields: {
        type: "array",
        minItems: 1,
        maxItems: 4,
        uniqueItems: true,
        items: { type: "string", enum: ["mode", "aspectRatio", "composition", "typography", "channel", "background", "style", "sceneIntensity"] },
        description: "Only fields whose answers are still unresolved. Omit to show all workflow fields.",
      },
      defaults: {
        type: "object",
        properties: {
          mode: { type: "string" },
          aspectRatio: { type: "string" },
          composition: { type: "string" },
          typography: { type: "string" },
          channel: { type: "string" },
          background: { type: "string" },
          sceneIntensity: { type: "string" },
          style: { type: "string" },
          direction: { type: "string" },
        },
      },
    },
  },
  annotations: { readOnlyHint: true, openWorldHint: false },
  _meta: {
    ui: { resourceUri: CREATION_BRIEF_RESOURCE_URI },
    "openai/outputTemplate": CREATION_BRIEF_RESOURCE_URI,
    "openai/toolInvocation/invoking": "正在准备珠宝视觉创作方向",
    "openai/toolInvocation/invoked": "请确认创作方向",
  },
};

const creationItemSchema = {
  type: "object",
  required: ["id", "title", "path"],
  properties: {
    id: { type: "string", pattern: "^(POSTER|CATALOG|DISPLAY|GRID|REDRAW|SHEET|TRYON)-[A-Z0-9]+(?:-[A-Z0-9]+)*$", maxLength: 64 },
    title: { type: "string" },
    path: { type: "string" },
    summary: { type: "string" },
    useCase: { type: "string" },
    slot: { type: "string" },
  },
};

const creationGalleryTool = {
  name: "show_jewelry_creation_gallery",
  title: "苏哇科技 · 珠宝视觉成品 Gallery",
  description:
    "Render one to twelve completed poster, catalog, display, grid, grid-redraw, or reference-sheet images in a compact vertical-rail Gallery. Call only with real local files and stable workflow-prefixed asset ids. Selection records one neutral stable asset context for the user's next instruction; it does not approve, rank, regenerate, or preselect a follow-up workflow. On success do not repeat Gallery media inline; use inline fallback on error or missing output.",
  inputSchema: {
    type: "object",
    required: ["workflow", "items"],
    properties: {
      workflow: { type: "string", enum: CREATION_GALLERY_WORKFLOWS },
      title: { type: "string" },
      caption: { type: "string" },
      initialAssetId: { type: "string", pattern: "^(POSTER|CATALOG|DISPLAY|GRID|REDRAW|SHEET|TRYON)-[A-Z0-9]+(?:-[A-Z0-9]+)*$", maxLength: 64 },
      items: { type: "array", minItems: 1, maxItems: 12, items: creationItemSchema },
    },
  },
  annotations: { readOnlyHint: true, openWorldHint: false },
  _meta: {
    ui: { resourceUri: CREATION_GALLERY_RESOURCE_URI },
    "openai/outputTemplate": CREATION_GALLERY_RESOURCE_URI,
    "openai/toolInvocation/invoking": "正在准备珠宝视觉成品",
    "openai/toolInvocation/invoked": "可逐张浏览成品",
  },
};

const DESIGN_ID_PATTERN = "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$";
const designItemSchema = {
  type: "object",
  required: ["id", "title", "path"],
  properties: {
    id: { type: "string", pattern: DESIGN_ID_PATTERN, maxLength: 64 },
    title: { type: "string" },
    path: { type: "string" },
    pieceType: { type: "string" },
    summary: { type: "string" },
    materials: { type: "string" },
    gemstones: { type: "string" },
    craft: { type: "string" },
    useCase: { type: "string" },
  },
};

const designGalleryTool = {
  name: "show_jewelry_design_gallery",
  title: "苏哇科技 · 珠宝设计成品 Gallery",
  description:
    "Render one to twelve completed ordinary jewelry-design images in a compact vertical-rail Gallery. For ordinary design preserve each real runner job id. For sketch_design use the four logical stable ids SKETCH-A through SKETCH-D while keeping the scoped output paths. Selection records one neutral stable asset context for the user's next instruction; it does not approve, rank, regenerate, or preselect a follow-up workflow. On success do not repeat Gallery media inline; use inline fallback for every real successful image when this tool is unavailable, errors, or the completed count exceeds twelve.",
  inputSchema: {
    type: "object",
    required: ["items"],
    properties: {
      title: { type: "string" },
      caption: { type: "string" },
      sourceWorkflow: { type: "string", enum: ["design", "sketch_design"] },
      initialDesignId: { type: "string", pattern: DESIGN_ID_PATTERN, maxLength: 64 },
      items: { type: "array", minItems: 1, maxItems: 12, items: designItemSchema },
    },
  },
  annotations: { readOnlyHint: true, openWorldHint: false },
  _meta: {
    ui: { resourceUri: DESIGN_GALLERY_RESOURCE_URI },
    "openai/outputTemplate": DESIGN_GALLERY_RESOURCE_URI,
    "openai/toolInvocation/invoking": "正在准备珠宝设计成品",
    "openai/toolInvocation/invoked": "可逐款浏览设计",
  },
};

const VISUAL_CATEGORIES = ["ring", "bracelet", "necklace", "pendant", "earrings", "brooch", "other"];
const TRYON_CATEGORIES = VISUAL_CATEGORIES.filter((category) => category !== "other");
const visualReferenceSchema = {
  type: "object",
  required: ["path", "role"],
  properties: {
    path: { type: "string" },
    role: { type: "string", enum: ["material", "craft", "style", "structure", "mood"] },
  },
};

const localEditorTool = {
  name: "open_jewelry_local_editor",
  title: "苏哇科技 · 珠宝局部重绘画布",
  description:
    "Open the fullscreen-capable visual workbench for local jewelry changes, put-it-here placement, or freehand-sketch-to-jewelry design. sketch_design may start from a blank canvas without sourcePath; local_edit and put_here still require one task-local source image. The canvas records spatial intent and saves a draft for the existing gpt-image-2 runner; it does not generate or rank images.",
  inputSchema: {
    type: "object",
    required: ["workspacePath", "mode", "category"],
    properties: {
      workspacePath: { type: "string", description: "Absolute active artifacts/runs/<task-id> workspace." },
      sourcePath: { type: "string", description: "Task-local product or sketch image. Optional only when mode is sketch_design and the designer starts from a blank canvas." },
      stonePath: { type: "string", description: "Optional task-local main-stone image for cutout and placement." },
      mode: { type: "string", enum: ["local_edit", "put_here", "sketch_design"] },
      category: { type: "string", enum: VISUAL_CATEGORIES },
      customCategory: { type: "string", maxLength: 40 },
      title: { type: "string" },
      referenceImages: { type: "array", maxItems: 4, items: visualReferenceSchema },
      defaults: {
        type: "object",
        properties: {
          instruction: { type: "string" }, preserve: { type: "string" }, change: { type: "string" },
          material: { type: "string" }, style: { type: "string" }, ratio: { type: "string" },
        },
      },
    },
  },
  annotations: { readOnlyHint: true, openWorldHint: false },
  _meta: {
    ui: { resourceUri: VISUAL_WORKBENCH_RESOURCE_URI },
    "openai/outputTemplate": VISUAL_WORKBENCH_RESOURCE_URI,
    "openai/toolInvocation/invoking": "正在打开珠宝局部重绘画布",
    "openai/toolInvocation/invoked": "可在画布中标注设计意图",
  },
};

const tryonEditorTool = {
  name: "open_jewelry_tryon_editor",
  title: "苏哇科技 · 珠宝模特佩戴画布",
  description:
    "Open the fullscreen-capable visual workbench to cut out one jewelry product and place it approximately on a model before gpt-image-2 generation. V1 supports rings, bracelets, necklaces, pendants, earrings, and brooches. All paths must already be copied into the active task workspace. This tool saves placement intent; it does not generate or rank images.",
  inputSchema: {
    type: "object",
    required: ["workspacePath", "jewelryPath", "modelPath", "category"],
    properties: {
      workspacePath: { type: "string", description: "Absolute active artifacts/runs/<task-id> workspace." },
      jewelryPath: { type: "string", description: "Absolute task-local jewelry product image path." },
      modelPath: { type: "string", description: "Absolute task-local model image path." },
      category: { type: "string", enum: TRYON_CATEGORIES },
      title: { type: "string" },
      defaults: {
        type: "object",
        properties: {
          instruction: { type: "string" }, pair: { type: "boolean" }, ratio: { type: "string" },
          x: { type: "number", minimum: 0, maximum: 1 }, y: { type: "number", minimum: 0, maximum: 1 },
          scale: { type: "number", minimum: 0.02, maximum: 2 }, rotation: { type: "number", minimum: -180, maximum: 180 },
        },
      },
    },
  },
  annotations: { readOnlyHint: true, openWorldHint: false },
  _meta: {
    ui: { resourceUri: VISUAL_WORKBENCH_RESOURCE_URI },
    "openai/outputTemplate": VISUAL_WORKBENCH_RESOURCE_URI,
    "openai/toolInvocation/invoking": "正在打开珠宝模特佩戴画布",
    "openai/toolInvocation/invoked": "可拖动首饰确认佩戴位置",
  },
};

const visualDraftTool = {
  name: "save_jewelry_visual_draft",
  title: "保存珠宝画布草稿",
  description:
    "Persist one visual-workbench draft inside the exact active artifacts/runs/<task-id> workspace. Called by the Apps UI after the designer confirms local-edit or try-on placement. Returns a stable draft id and workspace-relative files for the compiler; it does not generate an image.",
  inputSchema: {
    type: "object",
    required: ["workspacePath", "workflow", "state", "compositeDataUrl"],
    properties: {
      workspacePath: { type: "string" },
      workflow: { type: "string", enum: ["local_edit", "tryon"] },
      state: { type: "object" },
      compositeDataUrl: { type: "string" },
      cutoutDataUrl: { type: "string" },
      cutoutPreviewDataUrl: { type: "string" },
    },
  },
  annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false },
};

function send(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function cleanText(value, fallback = "") {
  return typeof value === "string" ? value.trim() : fallback;
}

function normalizeForm(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("tool arguments must be an object");
  }

  const title = cleanText(input.title);
  const fields = Array.isArray(input.fields) ? input.fields : [];
  if (!title) throw new Error("title is required");
  if (fields.length < 1 || fields.length > 4) throw new Error("fields must contain 1 to 4 items");

  const fieldIds = new Set();
  const normalizedFields = fields.map((field, index) => {
    if (!field || typeof field !== "object" || Array.isArray(field)) {
      throw new Error(`field ${index + 1} must be an object`);
    }
    const id = cleanText(field.id);
    const label = cleanText(field.label);
    const type = cleanText(field.type);
    if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id)) {
      throw new Error(`field ${index + 1} has an invalid id`);
    }
    if (fieldIds.has(id)) throw new Error(`duplicate field id: ${id}`);
    if (!label) throw new Error(`field ${id} requires a label`);
    if (!["text", "single", "multi"].includes(type)) {
      throw new Error(`field ${id} has an unsupported type`);
    }
    fieldIds.add(id);

    const options = Array.isArray(field.options)
      ? field.options.map((option, optionIndex) => {
          const optionId = cleanText(option?.id);
          const optionLabel = cleanText(option?.label);
          if (!optionId || !optionLabel) {
            throw new Error(`field ${id} option ${optionIndex + 1} requires id and label`);
          }
          const preview = cleanText(option.preview);
          const previewPath = cleanText(option.previewPath);
          if (preview && previewPath) {
            throw new Error(`field ${id} option ${optionId} must use preview or previewPath, not both`);
          }
          if (preview && !preview.startsWith("data:image/")) {
            throw new Error(`field ${id} option ${optionId} preview must be a data:image URL`);
          }
          return {
            id: optionId,
            label: optionLabel,
            ...(cleanText(option.description) ? { description: cleanText(option.description) } : {}),
            ...(preview ? { preview } : {}),
            ...(previewPath ? { previewPath } : {}),
          };
        })
      : [];

    if (type !== "text" && options.length < 2) {
      throw new Error(`field ${id} requires at least two options`);
    }
    if (options.length > 8) {
      throw new Error(`field ${id} options must contain 2 to 8 items`);
    }

    const optionIds = new Set();
    for (const option of options) {
      if (optionIds.has(option.id)) throw new Error(`field ${id} has duplicate option id: ${option.id}`);
      optionIds.add(option.id);
    }

    return {
      id,
      label,
      type,
      required: field.required === true,
      ...(cleanText(field.description) ? { description: cleanText(field.description) } : {}),
      ...(cleanText(field.placeholder) ? { placeholder: cleanText(field.placeholder) } : {}),
      ...(cleanText(field.otherPlaceholder)
        ? { otherPlaceholder: cleanText(field.otherPlaceholder) }
        : {}),
      ...(options.length ? { options } : {}),
    };
  });

  const normalizedForm = {
    formId: cleanText(input.formId) || randomUUID(),
    title,
    prompt: cleanText(input.prompt),
    submitLabel: cleanText(input.submitLabel) || "提交设计方向",
    messagePrefix: cleanText(input.messagePrefix) || "已提交珠宝设计方向",
    fields: normalizedFields,
  };
  const visualFields = normalizedFields.filter((field) => field.options?.some((option) => option.preview || option.previewPath));
  if (visualFields.length > 1) {
    throw new Error("visual previews must be grouped into one choice field per form");
  }
  const previewSize = visualFields.flatMap((field) => field.options || [])
    .reduce((total, option) => total + (option.preview?.length || 0), 0);
  if (previewSize > 720 * 1024) {
    throw new Error("visual previews exceed the shared 720 KiB form budget");
  }
  return normalizedForm;
}

function detachFormMedia(normalizedForm) {
  const formMedia = {};
  const localOptions = normalizedForm.fields.flatMap((field) => (field.options || [])
    .filter((option) => option.previewPath)
    .map((option) => ({
      key: `${field.id}\u0000${option.id}`,
      image: localImage(option.previewPath, `${field.id}.${option.id}.previewPath`),
    })));
  const localPreviews = localOptions.length
    ? previewMedia(localOptions.map(({ image }) => image), "followup-form")
    : [];
  const localPreviewByKey = new Map(localOptions.map(({ key }, index) => [key, localPreviews[index]]));
  const fields = normalizedForm.fields.map((field) => {
    if (!field.options) return field;
    const options = field.options.map(({ preview, previewPath, ...option }) => {
      const preparedPreview = preview || localPreviewByKey.get(`${field.id}\u0000${option.id}`);
      if (preparedPreview) {
        formMedia[field.id] ??= {};
        formMedia[field.id][option.id] = preparedPreview;
      }
      return option;
    });
    return { ...field, options };
  });
  const combinedSize = Object.values(formMedia)
    .flatMap((options) => Object.values(options))
    .reduce((total, preview) => total + preview.length, 0);
  if (combinedSize > 720 * 1024) {
    throw new Error("visual previews exceed the shared 720 KiB form budget");
  }
  return { form: { ...normalizedForm, fields }, formMedia };
}

function fallbackText(form) {
  const lines = [form.title];
  if (form.prompt) lines.push(form.prompt);
  for (const field of form.fields) {
    const required = field.required ? "（必填）" : "";
    const options = field.options?.map((option) => option.label).join(" / ");
    lines.push(`- ${field.label}${required}${options ? `：${options}` : ""}`);
  }
  lines.push("If an interactive card is unavailable, ask these questions once in normal chat.");
  return lines.join("\n");
}

function toolResult(input) {
  const { form, formMedia } = detachFormMedia(normalizeForm(input));
  return {
    content: [{ type: "text", text: fallbackText(form) }],
    structuredContent: { form },
    _meta: {
      ui: { resourceUri: RESOURCE_URI },
      "openai/outputTemplate": RESOURCE_URI,
      formId: form.formId,
      ...(Object.keys(formMedia).length ? { formMedia } : {}),
    },
  };
}

const IMAGE_MIME_TYPES = new Map([
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
]);

function localImage(pathValue, fieldName) {
  const path = cleanText(pathValue);
  if (!path) throw new Error(`${fieldName} is required`);
  if (!isAbsolute(path)) throw new Error(`${fieldName} must be an absolute local path`);
  const mimeType = IMAGE_MIME_TYPES.get(extname(path).toLowerCase());
  if (!mimeType) throw new Error(`${fieldName} must be a PNG or JPEG image`);
  const stat = statSync(path);
  if (!stat.isFile()) throw new Error(`${fieldName} must point to a file`);
  if (stat.size > MAX_IMAGE_BYTES) throw new Error(`${fieldName} exceeds the 24 MB UI limit`);
  const data = readFileSync(path).toString("base64");
  return { path, name: basename(path), mimeType, data };
}

function taskWorkspace(pathValue) {
  const path = cleanText(pathValue);
  if (!path || !isAbsolute(path)) throw new Error("workspacePath must be an absolute artifacts/runs/<task-id> path");
  const resolvedWorkspace = resolve(path);
  if (lstatSync(resolvedWorkspace).isSymbolicLink()) throw new Error("workspacePath must not be a symbolic link");
  const workspace = realpathSync(resolvedWorkspace);
  const parts = workspace.split(sep).filter(Boolean);
  const taskId = parts.at(-1) || "";
  if (parts.at(-3) !== "artifacts" || parts.at(-2) !== "runs" || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(taskId)) {
    throw new Error("workspacePath must be the exact active artifacts/runs/<task-id> directory");
  }
  const stat = statSync(workspace);
  if (!stat.isDirectory()) throw new Error("workspacePath must point to a directory");
  return workspace;
}

function withinWorkspace(workspace, pathValue, fieldName) {
  const path = cleanText(pathValue);
  if (!path) throw new Error(`${fieldName} is required`);
  const candidate = resolve(workspace, path);
  const canonical = realpathSync(candidate);
  const canonicalRel = relative(workspace, canonical);
  if (!canonicalRel || canonicalRel.startsWith(`..${sep}`) || canonicalRel === ".." || isAbsolute(canonicalRel)) {
    if (!canonicalRel) return canonical;
    throw new Error(`${fieldName} must not escape the active workspace through a symbolic link`);
  }
  return canonical;
}

function safeDraftDirectory(workspace, directory) {
  const rel = relative(workspace, directory);
  if (!rel || rel.startsWith(`..${sep}`) || rel === ".." || isAbsolute(rel)) throw new Error("draft directory must stay inside the active workspace");
  let cursor = workspace;
  for (const part of rel.split(sep)) {
    cursor = join(cursor, part);
    if (existsSync(cursor) && lstatSync(cursor).isSymbolicLink()) throw new Error("draft directory must not contain symbolic links");
  }
  mkdirSync(directory, { recursive: true });
  const canonical = realpathSync(directory);
  if (relative(workspace, canonical).startsWith(`..${sep}`)) throw new Error("draft directory escaped the active workspace");
  return canonical;
}

function workspaceImage(workspace, pathValue, fieldName) {
  return localImage(withinWorkspace(workspace, pathValue, fieldName), fieldName);
}

function visualReferences(workspace, rawReferences) {
  if (rawReferences === undefined) return [];
  if (!Array.isArray(rawReferences) || rawReferences.length > 4) {
    throw new Error("referenceImages must contain at most 4 items");
  }
  const allowed = ["material", "craft", "style", "structure", "mood"];
  return rawReferences.map((reference, index) => {
    if (!reference || typeof reference !== "object" || Array.isArray(reference)) {
      throw new Error(`referenceImages[${index}] must be an object`);
    }
    const role = cleanText(reference.role);
    if (!allowed.includes(role)) throw new Error(`referenceImages[${index}].role is unsupported`);
    return { role, ...workspaceImage(workspace, reference.path, `referenceImages[${index}].path`) };
  });
}

function visualWorkbenchResult(input, workflow) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("tool arguments must be an object");
  }
  const workspace = taskWorkspace(input.workspacePath);
  const defaults = input.defaults && typeof input.defaults === "object" && !Array.isArray(input.defaults) ? input.defaults : {};
  if (workflow === "local_edit") {
    const mode = cleanText(input.mode);
    const category = cleanText(input.category);
    if (!["local_edit", "put_here", "sketch_design"].includes(mode)) throw new Error("mode is required and must be local_edit, put_here, or sketch_design");
    if (!VISUAL_CATEGORIES.includes(category)) throw new Error("category is required and unsupported");
    const customCategory = cleanText(input.customCategory);
    if (category === "other" && (!customCategory || customCategory.length > 40)) throw new Error("customCategory is required and must be at most 40 characters when category is other");
    const source = cleanText(input.sourcePath) ? workspaceImage(workspace, input.sourcePath, "sourcePath") : null;
    if (!source && mode !== "sketch_design") throw new Error("sourcePath is required for local_edit and put_here");
    const stone = cleanText(input.stonePath) ? workspaceImage(workspace, input.stonePath, "stonePath") : null;
    const references = visualReferences(workspace, input.referenceImages);
    const images = [...(source ? [source] : []), ...(stone ? [stone] : []), ...references];
    const previews = previewMedia(images, "visual-workbench");
    const visualWorkbench = {
      sessionId: randomUUID(), workflow, workspacePath: workspace, mode, category,
      ...(category === "other" ? { customCategory } : {}),
      title: cleanText(input.title) || (mode === "sketch_design" ? "随手画转珠宝" : mode === "put_here" ? "定点局部设计" : "珠宝局部重绘"),
      ...(source ? { source: { path: source.path, name: source.name, mimeType: source.mimeType } } : {}),
      ...(stone ? { stone: { path: stone.path, name: stone.name, mimeType: stone.mimeType } } : {}),
      referenceImages: references.map(({ path, name, mimeType, role }) => ({ path, name, mimeType, role })),
      defaults: {
        instruction: cleanText(defaults.instruction), preserve: cleanText(defaults.preserve), change: cleanText(defaults.change),
        material: cleanText(defaults.material), style: cleanText(defaults.style), ratio: cleanText(defaults.ratio) || "1:1",
      },
    };
    let cursor = source ? 1 : 0;
    return {
      content: [{ type: "text", text: `${visualWorkbench.title}\n${source ? `源图: ${source.path}` : "空白画板：未提供源图"}\n请在 Apps UI 中完成绘制或标注并保存草稿；若画布不可用，请改用文字说明设计意图。` }],
      structuredContent: { visualWorkbench },
      _meta: {
        ui: { resourceUri: VISUAL_WORKBENCH_RESOURCE_URI },
        "openai/outputTemplate": VISUAL_WORKBENCH_RESOURCE_URI,
        visualWorkbenchMedia: {
          ...(source ? { source: previews[0] } : {}),
          ...(stone ? { stone: previews[cursor++] } : {}),
          references: Object.fromEntries(references.map((_, index) => [`REF-${index + 1}`, previews[cursor + index]])),
        },
      },
    };
  }

  const category = cleanText(input.category);
  if (!TRYON_CATEGORIES.includes(category)) throw new Error("category is unsupported");
  const jewelry = workspaceImage(workspace, input.jewelryPath, "jewelryPath");
  const model = workspaceImage(workspace, input.modelPath, "modelPath");
  const previews = previewMedia([jewelry, model], "visual-workbench");
  const visualWorkbench = {
    sessionId: randomUUID(), workflow, workspacePath: workspace, category,
    title: cleanText(input.title) || "珠宝模特佩戴",
    jewelry: { path: jewelry.path, name: jewelry.name, mimeType: jewelry.mimeType },
    model: { path: model.path, name: model.name, mimeType: model.mimeType },
    defaults: {
      instruction: cleanText(defaults.instruction), pair: defaults.pair === true,
      ratio: cleanText(defaults.ratio) || "3:4",
      x: Number.isFinite(Number(defaults.x)) ? Math.min(1, Math.max(0, Number(defaults.x))) : 0.5,
      y: Number.isFinite(Number(defaults.y)) ? Math.min(1, Math.max(0, Number(defaults.y))) : 0.55,
      scale: Number.isFinite(Number(defaults.scale)) ? Math.min(2, Math.max(0.02, Number(defaults.scale))) : 0.24,
      rotation: Number.isFinite(Number(defaults.rotation)) ? Math.min(180, Math.max(-180, Number(defaults.rotation))) : 0,
    },
  };
  return {
    content: [{ type: "text", text: `${visualWorkbench.title}\n珠宝: ${jewelry.path}\n模特: ${model.path}\n请在 Apps UI 中确认近似佩戴位置并保存草稿。` }],
    structuredContent: { visualWorkbench },
    _meta: {
      ui: { resourceUri: VISUAL_WORKBENCH_RESOURCE_URI },
      "openai/outputTemplate": VISUAL_WORKBENCH_RESOURCE_URI,
      visualWorkbenchMedia: { jewelry: previews[0], model: previews[1] },
    },
  };
}

function decodeVisualDataUrl(value, label) {
  const raw = cleanText(value);
  const match = /^data:image\/(png|jpeg);base64,([A-Za-z0-9+/=]+)$/.exec(raw);
  if (!match) throw new Error(`${label} must be a PNG or JPEG data URL`);
  const buffer = Buffer.from(match[2], "base64");
  if (!buffer.length || buffer.length > 3 * 1024 * 1024) throw new Error(`${label} must be between 1 byte and 3 MB`);
  return { buffer, extension: match[1] === "jpeg" ? "jpg" : "png" };
}

function validateDraftState(workspace, workflow, state) {
  if (workflow === "local_edit") {
    const mode = cleanText(state.mode);
    if (cleanText(state.sourcePath)) withinWorkspace(workspace, state.sourcePath, "state.sourcePath");
    else if (mode !== "sketch_design") throw new Error("state.sourcePath is required for local_edit and put_here");
    if (cleanText(state.stonePath)) withinWorkspace(workspace, state.stonePath, "state.stonePath");
    visualReferences(workspace, state.referenceImages);
    if (!["local_edit", "put_here", "sketch_design"].includes(mode)) throw new Error("state.mode is unsupported");
    if (!VISUAL_CATEGORIES.includes(state.category)) throw new Error("state.category is unsupported");
    if (state.category === "other" && (!cleanText(state.customCategory) || cleanText(state.customCategory).length > 40)) throw new Error("state.customCategory is required and must be at most 40 characters when category is other");
    if (state.schemaVersion !== 2) throw new Error("state.schemaVersion must be 2");
    const annotations = state.annotations === undefined ? [] : state.annotations;
    if (!Array.isArray(annotations) || annotations.length > 8) throw new Error("state.annotations must contain at most 8 items");
    if (["local_edit", "put_here"].includes(mode) && annotations.length < 1) throw new Error("local_edit and put_here require at least one annotation");
    const ids = new Set();
    annotations.forEach((annotation, index) => {
      if (!annotation || typeof annotation !== "object" || Array.isArray(annotation)) throw new Error(`state.annotations[${index}] must be an object`);
      const kind = cleanText(annotation.kind);
      const id = cleanText(annotation.id);
      const expected = kind === "anchor" ? /^ANCHOR-[0-9]{2}$/ : kind === "region" ? /^REGION-[0-9]{2}$/ : null;
      if (!expected || !expected.test(id)) throw new Error(`state.annotations[${index}] has an invalid id or kind`);
      if (ids.has(id)) throw new Error("state.annotations ids must be unique");
      ids.add(id);
      if (!cleanText(annotation.instruction)) throw new Error(`${id}.instruction is required`);
      const geometry = kind === "anchor" ? annotation.position : annotation.bounds;
      const keys = kind === "anchor" ? ["x", "y"] : ["x", "y", "width", "height"];
      if (!geometry || typeof geometry !== "object" || Array.isArray(geometry) || keys.some((key) => !Number.isFinite(Number(geometry[key])) || Number(geometry[key]) < 0 || Number(geometry[key]) > 1)) {
        throw new Error(`${id}.${kind === "anchor" ? "position" : "bounds"} must use normalized coordinates`);
      }
      if (kind === "region" && (Number(geometry.width) === 0 || Number(geometry.height) === 0 || Number(geometry.x) + Number(geometry.width) > 1 || Number(geometry.y) + Number(geometry.height) > 1)) throw new Error(`${id}.bounds must have non-zero size and stay inside the canvas`);
    });
    if (mode === "sketch_design" && cleanText(state.stonePath) && state.cutoutConfirmed !== true) {
      throw new Error("stone-assisted sketch_design requires confirmed cutout");
    }
  } else {
    withinWorkspace(workspace, state.jewelryPath, "state.jewelryPath");
    withinWorkspace(workspace, state.modelPath, "state.modelPath");
    if (!TRYON_CATEGORIES.includes(state.category)) throw new Error("state.category is unsupported");
    if (!state.transform || typeof state.transform !== "object" || Array.isArray(state.transform)) throw new Error("state.transform is required");
  }
}

function visualDraftResult(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new Error("tool arguments must be an object");
  const workspace = taskWorkspace(input.workspacePath);
  const workflow = cleanText(input.workflow);
  if (!["local_edit", "tryon"].includes(workflow)) throw new Error("workflow must be local_edit or tryon");
  const state = input.state && typeof input.state === "object" && !Array.isArray(input.state) ? input.state : null;
  if (!state) throw new Error("state must be an object");
  const stateJson = JSON.stringify(state);
  if (stateJson.length > 64 * 1024) throw new Error("state exceeds the 64 KiB draft limit");
  validateDraftState(workspace, workflow, state);
  const composite = decodeVisualDataUrl(input.compositeDataUrl, "compositeDataUrl");
  const cutout = cleanText(input.cutoutDataUrl) ? decodeVisualDataUrl(input.cutoutDataUrl, "cutoutDataUrl") : null;
  const cutoutPreview = cleanText(input.cutoutPreviewDataUrl) ? decodeVisualDataUrl(input.cutoutPreviewDataUrl, "cutoutPreviewDataUrl") : null;
  if (cleanText(state.stonePath) && state.cutoutConfirmed === true && (!cutout || !cutoutPreview)) throw new Error("confirmed stone cutout requires cutoutDataUrl and cutoutPreviewDataUrl");
  const prefix = workflow === "local_edit" ? "LOCAL" : "TRYON";
  const id = `${prefix}-${randomUUID().replaceAll("-", "").slice(0, 8).toUpperCase()}`;
  const directory = join(workspace, "visual-workbench", id);
  safeDraftDirectory(workspace, directory);
  const compositeRelative = `visual-workbench/${id}/composite.${composite.extension}`;
  writeFileSync(join(workspace, compositeRelative), composite.buffer);
  const cutoutRelative = cutout ? `visual-workbench/${id}/cutout.${cutout.extension}` : "";
  if (cutout) writeFileSync(join(workspace, cutoutRelative), cutout.buffer);
  const cutoutPreviewRelative = cutoutPreview ? `visual-workbench/${id}/cutout-preview.${cutoutPreview.extension}` : "";
  if (cutoutPreview) writeFileSync(join(workspace, cutoutPreviewRelative), cutoutPreview.buffer);
  const draftRelative = `visual-workbench/${id}/draft.json`;
  const draft = {
    schema_version: 2, id, workflow, createdAt: new Date().toISOString(), state,
    assets: { composite: compositeRelative, ...(cutout ? { cutout: cutoutRelative } : {}), ...(cutoutPreview ? { cutoutPreview: cutoutPreviewRelative } : {}) },
  };
  writeFileSync(join(workspace, draftRelative), `${JSON.stringify(draft, null, 2)}\n`, "utf8");
  const visualDraft = {
    id, workflow, draftPath: draftRelative, compositePath: compositeRelative,
    ...(cutout ? { cutoutPath: cutoutRelative } : {}),
    ...(cutoutPreview ? { cutoutPreviewPath: cutoutPreviewRelative } : {}),
  };
  return {
    content: [{ type: "text", text: `已保存画布草稿 ${id}。\nCurrent visual draft (JSON): ${JSON.stringify(visualDraft)}` }],
    structuredContent: { visualDraft },
  };
}

function previewMedia(images, label) {
  let previews = images.map((image) => `data:${image.mimeType};base64,${image.data}`);
  if (!withinPreviewBudget(previews)) {
    const attempts = [[640, 55], [420, 45], [320, 40], [240, 35], [160, 30], [120, 25]];
    for (const [maxDimension, quality] of attempts) {
      previews = previewDataUris(images, maxDimension, quality);
      if (withinPreviewBudget(previews)) break;
    }
  }
  if (!withinPreviewBudget(previews)) {
    throw new Error(`${label} previews exceed the inline UI payload limit`);
  }
  return previews;
}

function comparisonResult(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("tool arguments must be an object");
  }
  const rawPairs = Array.isArray(input.pairs) && input.pairs.length
    ? input.pairs
    : [{
        id: "RETOUCH-A",
        title: input.title,
        caption: input.caption,
        beforePath: input.beforePath,
        afterPath: input.afterPath,
        beforeLabel: input.beforeLabel,
        afterLabel: input.afterLabel,
      }];
  if (rawPairs.length > 8) throw new Error("pairs must contain 1 to 8 completed items");
  const requestedPosition = Number(input.initialPosition);
  const initialPosition = Number.isFinite(requestedPosition)
    ? Math.min(100, Math.max(0, requestedPosition))
    : 50;
  const pairs = rawPairs.map((pair, index) => {
    if (!pair || typeof pair !== "object" || Array.isArray(pair)) {
      throw new Error(`pair ${index + 1} must be an object`);
    }
    const id = `RETOUCH-${"ABCDEFGH"[index]}`;
    if (cleanText(pair.id) && cleanText(pair.id) !== id) {
      throw new Error(`pair ${index + 1} id must be ${id}`);
    }
    const before = localImage(pair.beforePath, `${id}.beforePath`);
    const after = localImage(pair.afterPath, `${id}.afterPath`);
    return {
      id,
      title: cleanText(pair.title) || (rawPairs.length === 1 ? cleanText(input.title) || "珠宝精修前后对比" : `精修对比 ${index + 1}`),
      caption: cleanText(pair.caption),
      initialPosition,
      before: { label: cleanText(pair.beforeLabel) || "精修前", ...before },
      after: { label: cleanText(pair.afterLabel) || "精修后", ...after },
    };
  });
  const previews = previewMedia(pairs.flatMap(({ before, after }) => [before, after]), "comparison");
  const pairMedia = Object.fromEntries(pairs.map((pair, index) => [pair.id, {
    before: previews[index * 2],
    after: previews[index * 2 + 1],
  }]));
  const requestedPairId = cleanText(input.initialPairId);
  const initialPairId = pairs.some(({ id }) => id === requestedPairId) ? requestedPairId : pairs[0].id;
  const comparison = {
    title: cleanText(input.title) || "珠宝精修前后对比",
    caption: cleanText(input.caption),
    initialPairId,
    initialPosition,
    pairs: pairs.map(({ id, title, caption, before, after }) => ({
      id, title, caption,
      before: { label: before.label, path: before.path, name: before.name, mimeType: before.mimeType },
      after: { label: after.label, path: after.path, name: after.name, mimeType: after.mimeType },
    })),
  };
  if (pairs.length === 1) {
    comparison.before = comparison.pairs[0].before;
    comparison.after = comparison.pairs[0].after;
  }
  const lines = pairs.flatMap((pair) => [
    `- ${pair.id} ${pair.before.label}: ${pair.before.path}`,
    `- ${pair.id} ${pair.after.label}: ${pair.after.path}`,
  ]);

  return {
    content: [
      {
        type: "text",
        text: `${comparison.title}\n${lines.join("\n")}\nIf the comparison card is unavailable, show every source/output pair inline using these paths.`,
      },
    ],
    structuredContent: { comparison },
    _meta: {
      ui: { resourceUri: COMPARISON_RESOURCE_URI },
      "openai/outputTemplate": COMPARISON_RESOURCE_URI,
      comparisonMedia: {
        pairs: pairMedia,
        ...(pairs.length === 1 ? pairMedia[pairs[0].id] : {}),
      },
    },
  };
}

const REMIX_DEFAULTS = {
  schemaVersion: 2,
  designSystem: "",
  count: 4,
  structureFidelity: "medium",
  intensity: "balanced",
  fusionStrategy: "pattern_translation",
  themes: [],
  morphologies: [],
  styles: [],
  materials: [],
  customThemes: "",
  customMorphologies: "",
  customStyles: "",
  customMaterials: "",
  referenceRole: "style",
  direction: "",
};

function pickEnum(value, allowed, fallback) {
  return allowed.includes(value) ? value : fallback;
}

function stringArray(value, fallback) {
  if (!Array.isArray(value)) return fallback;
  const items = value.map((item) => cleanText(item)).filter(Boolean);
  return items.length ? [...new Set(items)] : fallback;
}

function remixSelection(defaults, designSystem, field) {
  if (!designSystem) return [];
  const allowed = new Set((remixTaxonomy.design_systems?.[designSystem]?.[field] || []).map(({ id }) => id));
  allowed.add("other");
  return stringArray(defaults[field], []).filter((id) => allowed.has(id));
}

function normalizeRemixBrief(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("tool arguments must be an object");
  }
  const defaults = input.defaults && typeof input.defaults === "object" && !Array.isArray(input.defaults)
    ? input.defaults
    : {};
  const designSystem = pickEnum(defaults.designSystem, REMIX_DESIGN_SYSTEMS, REMIX_DEFAULTS.designSystem);
  return {
    formId: cleanText(input.formId) || randomUUID(),
    title: cleanText(input.title) || "确认爆款二创方向",
    prompt: cleanText(input.prompt) || "原款图负责结构，这一轮只确认变化幅度与设计语言。",
    hasReferenceImages: input.hasReferenceImages === true,
    schemaVersion: 2,
    designSystem,
    count: defaults.count === 8 ? 8 : 4,
    structureFidelity: pickEnum(defaults.structureFidelity, ["high", "medium", "low"], REMIX_DEFAULTS.structureFidelity),
    intensity: pickEnum(defaults.intensity, ["subtle", "balanced", "bold"], REMIX_DEFAULTS.intensity),
    fusionStrategy: pickEnum(defaults.fusionStrategy, ["shape_grafting", "pattern_translation", "structural_rebuild"], REMIX_DEFAULTS.fusionStrategy),
    themes: remixSelection(defaults, designSystem, "themes"),
    morphologies: remixSelection(defaults, designSystem, "morphologies"),
    styles: remixSelection(defaults, designSystem, "styles"),
    materials: remixSelection(defaults, designSystem, "materials"),
    customThemes: cleanText(defaults.customThemes),
    customMorphologies: cleanText(defaults.customMorphologies),
    customStyles: cleanText(defaults.customStyles),
    customMaterials: cleanText(defaults.customMaterials),
    referenceRole: pickEnum(defaults.referenceRole, ["line", "material", "craft", "composition", "mood", "style"], REMIX_DEFAULTS.referenceRole),
    direction: cleanText(defaults.direction),
  };
}

function remixBriefResult(input) {
  const remixBrief = normalizeRemixBrief(input);
  return {
    content: [{
      type: "text",
      text: `${remixBrief.title}\n请确认 4 或 8 个独立方向、结构保留、创改强度、融合策略、主题、形态、风格与材质工艺。\nIf the interactive form is unavailable, ask this dedicated remix brief once in normal chat.`,
    }],
    structuredContent: { remixBrief },
    _meta: {
      ui: { resourceUri: REMIX_BRIEF_RESOURCE_URI },
      "openai/outputTemplate": REMIX_BRIEF_RESOURCE_URI,
      formId: remixBrief.formId,
    },
  };
}

function previewDataUris(images, maxDimension, quality) {
  return images.map((image) => {
    const preview = compactImage(image, maxDimension, quality);
    return `data:${preview.mimeType};base64,${preview.data.toString("base64")}`;
  });
}

function withinPreviewBudget(previews) {
  return previews.reduce((total, preview) => total + preview.length, 0) <= MAX_PREVIEW_CHARS;
}

function galleryMedia(source, candidates) {
  const images = [source, ...candidates];
  const previews = previewMedia(images, "remix");
  return {
    source: previews[0],
    candidates: Object.fromEntries(candidates.map((candidate, index) => [candidate.id, previews[index + 1]])),
  };
}

function remixGalleryResult(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("tool arguments must be an object");
  }
  const rawCandidates = Array.isArray(input.candidates) ? input.candidates : [];
  if (![4, 8].includes(rawCandidates.length)) {
    throw new Error("candidates must contain exactly 4 or 8 completed items");
  }
  const expectedIds = "ABCDEFGH".slice(0, rawCandidates.length).split("").map((letter) => `REMIX-${letter}`);
  const candidates = rawCandidates.map((candidate, index) => {
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
      throw new Error(`candidate ${index + 1} must be an object`);
    }
    const id = cleanText(candidate.id);
    if (id !== expectedIds[index]) throw new Error(`candidate ${index + 1} id must be ${expectedIds[index]}`);
    const image = localImage(candidate.path, `${id}.path`);
    return {
      ...image,
      id,
      title: cleanText(candidate.title) || id,
      summary: cleanText(candidate.summary),
      useCase: cleanText(candidate.useCase),
    };
  });
  const source = localImage(input.sourcePath, "sourcePath");
  const media = galleryMedia(source, candidates);
  const requestedPosition = Number(input.initialPosition);
  const initialPosition = Number.isFinite(requestedPosition)
    ? Math.min(100, Math.max(0, requestedPosition))
    : 50;
  const initialCandidateId = expectedIds.includes(cleanText(input.initialCandidateId))
    ? cleanText(input.initialCandidateId)
    : expectedIds[0];
  const gallery = {
    title: cleanText(input.title) || "珠宝爆款二创",
    caption: cleanText(input.caption),
    initialCandidateId,
    initialPosition,
    source: { path: source.path, name: source.name, mimeType: source.mimeType, label: "原款" },
    candidates: candidates.map(({ id, title, summary, useCase, path, name, mimeType }) => ({
      id, title, summary, useCase, path, name, mimeType,
    })),
  };
  const lines = candidates.map((candidate) => `- ${candidate.id} ${candidate.title}: ${candidate.path}`);
  return {
    content: [{
      type: "text",
      text: `${gallery.title}\n- 原款: ${source.path}\n${lines.join("\n")}\nIf the Gallery is unavailable, show the source and all candidate images inline using these paths.`,
    }],
    structuredContent: { gallery },
    _meta: {
      ui: { resourceUri: REMIX_GALLERY_RESOURCE_URI },
      "openai/outputTemplate": REMIX_GALLERY_RESOURCE_URI,
      galleryMedia: media,
    },
  };
}

const CREATION_DEFAULTS = {
  poster: {
    title: "确认珠宝海报方向",
    prompt: "确认版式与传播场景，产品事实仍由原图锁定。",
    mode: "editorial_board",
    aspectRatio: "3:4",
    composition: "product_led",
    typography: "minimal",
    style: "luxury_editorial",
  },
  catalog: {
    title: "确认珠宝画册方向",
    prompt: "确认画册档位与渠道，已明确的交付数量不会被改变。",
    mode: "core_five",
    aspectRatio: "1:1",
    channel: "pdp",
    background: "clean_light",
    style: "consistent_commerce",
  },
  display: {
    title: "确认珠宝展示方向",
    prompt: "确认展示模式与场景强度，珠宝始终是第一视觉信号。",
    mode: "editorial_still_life",
    aspectRatio: "3:4",
    sceneIntensity: "balanced",
    background: "quiet_neutral",
    style: "product_focused",
  },
};

function normalizeCreationBrief(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("tool arguments must be an object");
  }
  const workflow = cleanText(input.workflow);
  if (!CREATION_WORKFLOWS.includes(workflow)) throw new Error("workflow must be poster, catalog, or display");
  const fallback = CREATION_DEFAULTS[workflow];
  const defaults = input.defaults && typeof input.defaults === "object" && !Array.isArray(input.defaults)
    ? input.defaults
    : {};
  const allowedFields = CREATION_BRIEF_FIELDS[workflow];
  const requestedFields = Array.isArray(input.unresolvedFields) ? input.unresolvedFields : allowedFields;
  const unresolvedFields = [...new Set(requestedFields)].filter((field) => allowedFields.includes(field));
  if (!unresolvedFields.length || unresolvedFields.length !== requestedFields.length) {
    throw new Error(`unresolvedFields must contain only unresolved ${workflow} fields`);
  }
  return {
    formId: cleanText(input.formId) || randomUUID(),
    workflow,
    title: cleanText(input.title) || fallback.title,
    prompt: cleanText(input.prompt) || fallback.prompt,
    hasSourceImages: input.hasSourceImages === true,
    unresolvedFields,
    mode: cleanText(defaults.mode) || fallback.mode,
    aspectRatio: cleanText(defaults.aspectRatio) || fallback.aspectRatio,
    composition: cleanText(defaults.composition) || fallback.composition || "",
    typography: cleanText(defaults.typography) || fallback.typography || "",
    channel: cleanText(defaults.channel) || fallback.channel || "",
    background: cleanText(defaults.background) || fallback.background || "",
    sceneIntensity: cleanText(defaults.sceneIntensity) || fallback.sceneIntensity || "",
    style: cleanText(defaults.style) || fallback.style,
    direction: cleanText(defaults.direction),
  };
}

function creationBriefResult(input) {
  const creationBrief = normalizeCreationBrief(input);
  return {
    content: [{
      type: "text",
      text: `${creationBrief.title}\nworkflow: ${creationBrief.workflow}\n请确认专用创作表单中的方向。If the interactive form is unavailable, ask this brief once in normal chat.`,
    }],
    structuredContent: { creationBrief },
    _meta: {
      ui: { resourceUri: CREATION_BRIEF_RESOURCE_URI },
      "openai/outputTemplate": CREATION_BRIEF_RESOURCE_URI,
      formId: creationBrief.formId,
    },
  };
}

const CREATION_PREFIX = {
  poster: "POSTER",
  catalog: "CATALOG",
  display: "DISPLAY",
  grid: "GRID",
  grid_redraw: "REDRAW",
  reference_sheet: "SHEET",
  tryon: "TRYON",
};
const CREATION_TITLES = {
  poster: "珠宝海报",
  catalog: "珠宝画册",
  display: "珠宝展示",
  grid: "珠宝九宫格",
  grid_redraw: "九宫格拆分重绘",
  reference_sheet: "珠宝结构参考图",
  tryon: "珠宝模特佩戴",
};

function creationGalleryResult(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("tool arguments must be an object");
  }
  const workflow = cleanText(input.workflow);
  if (!CREATION_GALLERY_WORKFLOWS.includes(workflow)) {
    throw new Error("workflow must be poster, catalog, display, grid, grid_redraw, reference_sheet, or tryon");
  }
  const rawItems = Array.isArray(input.items) ? input.items : [];
  if (rawItems.length < 1 || rawItems.length > 12) throw new Error("items must contain 1 to 12 completed assets");
  const prefix = CREATION_PREFIX[workflow];
  const idPattern = new RegExp(`^${prefix}-[A-Z0-9]+(?:-[A-Z0-9]+)*$`);
  const itemIds = new Set();
  const items = rawItems.map((item, index) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`item ${index + 1} must be an object`);
    }
    const id = cleanText(item.id);
    if (id.length > 64) throw new Error(`item ${index + 1} id must be at most 64 characters`);
    if (!idPattern.test(id)) throw new Error(`item ${index + 1} id must start with ${prefix}- and contain uppercase letters, numbers, or hyphen-separated segments`);
    if (itemIds.has(id)) throw new Error("creation item ids must be unique");
    itemIds.add(id);
    const image = localImage(item.path, `${id}.path`);
    return {
      id,
      title: cleanText(item.title) || `${CREATION_TITLES[workflow]} ${index + 1}`,
      summary: cleanText(item.summary),
      useCase: cleanText(item.useCase),
      slot: cleanText(item.slot),
      ...image,
    };
  });
  const previews = previewMedia(items, "creation");
  const media = {
    items: Object.fromEntries(items.map((item, index) => [item.id, previews[index]])),
  };
  const requestedId = cleanText(input.initialAssetId);
  if (requestedId && !idPattern.test(requestedId)) {
    throw new Error(`initialAssetId must start with ${prefix}- and use the stable asset-id format`);
  }
  if (requestedId.length > 64) throw new Error("initialAssetId must be at most 64 characters");
  const initialAssetId = items.some(({ id }) => id === requestedId) ? requestedId : items[0].id;
  const creationGallery = {
    workflow,
    title: cleanText(input.title) || CREATION_TITLES[workflow],
    caption: cleanText(input.caption),
    initialAssetId,
    items: items.map(({ id, title, summary, useCase, slot, path, name, mimeType }) => ({
      id, title, summary, useCase, slot, path, name, mimeType,
    })),
  };
  return {
    content: [{
      type: "text",
      text: `${creationGallery.title}\n${items.map(({ id, title, path }) => `- ${id} ${title}: ${path}`).join("\n")}\nIf the Gallery is unavailable, show every completed image inline using these paths.`,
    }],
    structuredContent: { creationGallery },
    _meta: {
      ui: { resourceUri: CREATION_GALLERY_RESOURCE_URI },
      "openai/outputTemplate": CREATION_GALLERY_RESOURCE_URI,
      creationMedia: media,
    },
  };
}

function designGalleryResult(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("tool arguments must be an object");
  }
  const rawItems = Array.isArray(input.items) ? input.items : [];
  if (rawItems.length < 1 || rawItems.length > 12) throw new Error("items must contain 1 to 12 completed designs");
  const sourceWorkflow = cleanText(input.sourceWorkflow) === "sketch_design" ? "sketch_design" : "design";
  const idPattern = new RegExp(DESIGN_ID_PATTERN);
  const itemIds = new Set();
  const items = rawItems.map((item, index) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`item ${index + 1} must be an object`);
    }
    const id = cleanText(item.id);
    if (id.length > 64) throw new Error(`item ${index + 1} id must be at most 64 characters`);
    if (!idPattern.test(id)) throw new Error(`item ${index + 1} id must use the stable runner-id format`);
    if (itemIds.has(id)) throw new Error("design item ids must be unique");
    itemIds.add(id);
    const image = localImage(item.path, `${id}.path`);
    return {
      id,
      title: cleanText(item.title) || `珠宝设计 ${index + 1}`,
      pieceType: cleanText(item.pieceType),
      summary: cleanText(item.summary),
      materials: cleanText(item.materials),
      gemstones: cleanText(item.gemstones),
      craft: cleanText(item.craft),
      useCase: cleanText(item.useCase),
      ...image,
    };
  });
  if (sourceWorkflow === "sketch_design") {
    const expected = ["SKETCH-A", "SKETCH-B", "SKETCH-C", "SKETCH-D"];
    if (items.length !== expected.length || items.some((item, index) => item.id !== expected[index])) {
      throw new Error("sketch_design items must use SKETCH-A through SKETCH-D in order");
    }
  }
  const previews = previewMedia(items, "design");
  const requestedId = cleanText(input.initialDesignId);
  if (requestedId.length > 64) throw new Error("initialDesignId must be at most 64 characters");
  if (requestedId && !idPattern.test(requestedId)) throw new Error("initialDesignId must use the stable runner-id format");
  const initialDesignId = items.some(({ id }) => id === requestedId) ? requestedId : items[0].id;
  const designGallery = {
    sourceWorkflow,
    title: cleanText(input.title) || "珠宝设计成品",
    caption: cleanText(input.caption),
    initialDesignId,
    items: items.map(({ id, title, pieceType, summary, materials, gemstones, craft, useCase, path, name, mimeType }) => ({
      id, title, pieceType, summary, materials, gemstones, craft, useCase, path, name, mimeType,
    })),
  };
  return {
    content: [{
      type: "text",
      text: `${designGallery.title}\n${items.map(({ id, title, path }) => `- ${id} ${title}: ${path}`).join("\n")}\nIf the Gallery is unavailable, show every completed design inline using these paths.`,
    }],
    structuredContent: { designGallery },
    _meta: {
      ui: { resourceUri: DESIGN_GALLERY_RESOURCE_URI },
      "openai/outputTemplate": DESIGN_GALLERY_RESOURCE_URI,
      designMedia: { items: Object.fromEntries(items.map((item, index) => [item.id, previews[index]])) },
    },
  };
}

function errorResult(error) {
  return {
    isError: true,
    content: [{ type: "text", text: `Unable to render jewelry UI: ${error.message}` }],
  };
}

const TOOL_REGISTRY = [
  { descriptor: formTool, run: (arguments_) => toolResult(arguments_) },
  { descriptor: comparisonTool, run: (arguments_) => comparisonResult(arguments_) },
  { descriptor: remixBriefTool, run: (arguments_) => remixBriefResult(arguments_ || {}) },
  { descriptor: remixGalleryTool, run: (arguments_) => remixGalleryResult(arguments_) },
  { descriptor: creationBriefTool, run: (arguments_) => creationBriefResult(arguments_ || {}) },
  { descriptor: creationGalleryTool, run: (arguments_) => creationGalleryResult(arguments_) },
  { descriptor: designGalleryTool, run: (arguments_) => designGalleryResult(arguments_) },
  { descriptor: localEditorTool, run: (arguments_) => visualWorkbenchResult(arguments_, "local_edit") },
  { descriptor: tryonEditorTool, run: (arguments_) => visualWorkbenchResult(arguments_, "tryon") },
  { descriptor: visualDraftTool, run: (arguments_) => visualDraftResult(arguments_) },
];

const RESOURCE_REGISTRY = [
  { uri: RESOURCE_URI, name: "SVT Jewelry follow-up form", description: "Interactive jewelry-design clarification card.", html: widgetHtml },
  { uri: COMPARISON_RESOURCE_URI, name: "SVT Jewelry retouch comparison", description: "Read-only draggable comparison for source and retouched jewelry images.", html: comparisonHtml },
  { uri: REMIX_BRIEF_RESOURCE_URI, name: "SVT Jewelry remix brief", description: "Compact product-mode intake for 4/8 jewelry remix directions.", html: remixBriefHtml },
  { uri: REMIX_GALLERY_RESOURCE_URI, name: "SVT Jewelry remix Gallery", description: "Source/candidate slider Gallery for completed jewelry remix sets.", html: remixGalleryHtml },
  { uri: CREATION_BRIEF_RESOURCE_URI, name: "苏哇科技珠宝视觉创作表单", description: "Tailored compact intake for poster, catalog, and product-display creation.", html: creationBriefHtml },
  { uri: CREATION_GALLERY_RESOURCE_URI, name: "苏哇科技珠宝视觉成品 Gallery", description: "Compact vertical-rail Gallery for completed poster, catalog, display, grid, redraw, and reference-sheet assets.", html: creationGalleryHtml },
  { uri: DESIGN_GALLERY_RESOURCE_URI, name: "苏哇科技珠宝设计成品 Gallery", description: "Compact vertical-rail Gallery for one to twelve completed ordinary jewelry designs.", html: designGalleryHtml },
  { uri: VISUAL_WORKBENCH_RESOURCE_URI, name: "苏哇科技珠宝视觉工作台", description: "Fullscreen-capable canvas for local redraw, sketch-to-jewelry, and model try-on placement.", html: visualWorkbenchHtml },
];

async function handle(message) {
  if (!message || message.jsonrpc !== "2.0") return;
  if (message.method?.startsWith("notifications/")) return;

  if (message.method === "initialize") {
    send({
      jsonrpc: "2.0",
      id: message.id,
      result: {
        protocolVersion: message.params?.protocolVersion || "2025-06-18",
        capabilities: { tools: {}, resources: {} },
        serverInfo: { name: "svt_jewelry_ui", version: SERVER_VERSION },
        instructions:
          "Use ask_jewelry_followup_questions for ordinary workflow-changing clarification; ask_jewelry_remix_brief for dedicated 4/8 remix; and ask_jewelry_creation_brief for unresolved poster, catalog, or display families. Use open_jewelry_local_editor for local redraw, put-it-here, or sketch-to-jewelry spatial intent; use open_jewelry_tryon_editor for approximate jewelry placement on a model. Their UI saves a task-local visual draft before the existing Image-2 runner compiles and generates. Use show_jewelry_retouch_comparison for 1-8 real retouch pairs, show_jewelry_remix_gallery after all 4/8 remix files exist, show_jewelry_creation_gallery for 1-12 real poster/catalog/display/grid/grid-redraw/reference-sheet assets, and show_jewelry_design_gallery for 1-12 real ordinary jewelry-design outputs. Gallery selections are neutral asset context: wait for the user's next instruction instead of inferring a follow-up workflow.",
      },
    });
    return;
  }

  if (message.method === "tools/list") {
    send({ jsonrpc: "2.0", id: message.id, result: { tools: TOOL_REGISTRY.map(({ descriptor }) => descriptor) } });
    return;
  }

  if (message.method === "tools/call") {
    const entry = TOOL_REGISTRY.find(({ descriptor }) => descriptor.name === message.params?.name);
    if (!entry) {
      send({ jsonrpc: "2.0", id: message.id, result: errorResult(new Error("unknown tool")) });
      return;
    }
    try {
      const result = entry.run(message.params.arguments);
      send({ jsonrpc: "2.0", id: message.id, result });
    } catch (error) {
      send({ jsonrpc: "2.0", id: message.id, result: errorResult(error) });
    }
    return;
  }

  if (message.method === "resources/list") {
    send({
      jsonrpc: "2.0",
      id: message.id,
      result: {
        resources: RESOURCE_REGISTRY.map(({ uri, name, description }) => ({ uri, name, description, mimeType: RESOURCE_MIME_TYPE })),
      },
    });
    return;
  }

  if (message.method === "resources/read") {
    const uri = message.params?.uri;
    const resource = RESOURCE_REGISTRY.find((entry) => entry.uri === uri);
    if (!resource) {
      send({ jsonrpc: "2.0", id: message.id, error: { code: -32002, message: "resource not found" } });
      return;
    }
    send({
      jsonrpc: "2.0",
      id: message.id,
      result: {
        contents: [
          {
            uri,
            mimeType: RESOURCE_MIME_TYPE,
            text: resource.html,
            _meta: {
              ui: {
                prefersBorder: false,
                csp: { connectDomains: [], resourceDomains: [] },
              },
              "openai/widgetPrefersBorder": false,
            },
          },
        ],
      },
    });
    return;
  }

  send({
    jsonrpc: "2.0",
    id: message.id ?? null,
    error: { code: -32601, message: `method not found: ${message.method}` },
  });
}

export { handle, RESOURCE_MIME_TYPE, RESOURCE_REGISTRY, SERVER_VERSION, TOOL_REGISTRY };

const isDirectRun = process.argv[1]
  && realpathSync(fileURLToPath(import.meta.url)) === realpathSync(resolve(process.argv[1]));

if (isDirectRun) {
  readline.createInterface({ input: process.stdin }).on("line", (line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    try {
      handle(JSON.parse(trimmed)).catch((error) => {
        send({ jsonrpc: "2.0", id: null, error: { code: -32603, message: error.message } });
      });
    } catch (error) {
      send({ jsonrpc: "2.0", id: null, error: { code: -32700, message: error.message } });
    }
  });
}
