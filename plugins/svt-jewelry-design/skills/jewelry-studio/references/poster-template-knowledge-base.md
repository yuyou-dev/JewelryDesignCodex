# Poster Template Knowledge Base

Use this knowledge base before writing any jewelry poster, ecommerce hero, lookbook, magazine page,
or collage prompt. Template selection is semantic and design-led: infer the user's intent, product
category, allowed model use, ratio, commercial context, and desired visual richness. Do not treat
these templates as rigid keyword replacement rules.

## Template Selection

1. Understand the request: poster count, aspect ratio, commercial use, supplied copy, whether model
   wearing is allowed, and whether the user asked for ecommerce, magazine, collage, campaign, or
   only "高级感海报".
2. Extract product constraints from the jewelry truth reference: category, metal, gemstones, stone
   count and positions, chain/bail/flower/leaf/connector logic, scale, and wearing structure.
3. Choose one template card per output. For a broad request like "几张高级海报", choose a
   complementary set instead of repeating the same still-life logic.
4. If no card clearly matches, use `default advanced jewelry poster` and still require structured
   modules, hierarchy, and anti-still-life-degeneration checks.
5. Record the selected template card and template selection reason in every final prompt using the
   exact fields `Chosen poster template`, `Template reason`, `Required layout modules`, and
   `Anti-degeneration check`.

## Shared Rules

- Product fidelity comes before visual drama.
- One requested poster means one independent poster output or one recorded generation attempt.
- Multi-design ecommerce poster campaigns should normally use a complementary three-slot matrix per
  source design: `PDP Hero / Luxury Ecommerce Homepage`, `Editorial Board / Lookbook Presentation`,
  and `Macro Detail / Magazine Catalog`.
- Text stays minimal unless the template intentionally needs magazine/catalog text.
- Layout modules must serve the product: hero product, model detail, cutout, art scene, paper layer,
  product card, numbering, caption, or negative space.
- For every prompt, include an `anti-still-life-degeneration` constraint: the poster may not collapse
  into only centered product, soft background, shallow reflection, and one small title.
- This must read as a designed poster layout, not a plain product still life.
- Keep at least two visible poster-layout modules beyond the jewelry object.
- Do not collapse the composition into a centered necklace on a simple background.
- Product fidelity is locked, but layout hierarchy must remain poster-grade.
- `Generated` is a production status, not a visual approval status. Keep image review and brand
  approval separate from file creation or optional external delivery.

## Template Cards

### Editorial Presentation Board

- Applicable intent: high-end brand presentation, lookbook board, "高级感几张海报", campaign board,
  or when the user wants a richer layout but did not request ecommerce UI.
- Trigger signals: presentation board, lookbook, brand mood, several premium posters, model wearing
  allowed, editorial visual.
- Layout structure: one atmospheric partial model-wearing image, one close-up wearing/detail crop,
  one or two clean product cutouts, and a refined color board with controlled overlap.
- Required modules: model atmosphere, detail crop, product cutout, clear title/caption zone, negative
  space.
- Product fidelity rules: all modules must show the same SKU; cutouts must preserve exact stones,
  chain, bails, leaves, flowers, and metal direction.
- Text rules: one short title or supplied copy; no fake brand, price, URL, QR code, social handle, or
  watermark.
- Aspect fit: usually 3:4, also works as 4:5 social cover.
- Forbidden degeneration: do not make a single centered product still-life; do not let the board
  become equal-size grid cells.
- Review focus: clean cutout edges, model supports jewelry, modules have hierarchy.

### Luxury Ecommerce Homepage

- Applicable intent: ecommerce homepage, PDP hero, landing page, product cards, Best Sellers,
  lookbook landing, or commercial home visual.
- Trigger signals: ecommerce, homepage, PDP, hero, shop, product card, Best Sellers, landing page.
- Layout structure: soft natural or ivory background, centered content panel, hero product area,
  product card modules, partial model detail, artistic scene, small navigation or CTA when requested.
- Required modules: hero area, product card or PDP module, one model/detail/art scene module, clean
  commercial negative space.
- Product fidelity rules: product cards and hero product must remain the same SKU or declared SKU
  family; no random variants.
- Text rules: only supplied brand/copy or neutral ecommerce labels; no fake prices unless supplied.
- Aspect fit: 9:16, long homepage poster, or 3:4 ecommerce concept when requested.
- Forbidden degeneration: do not call it ecommerce if it lacks product-card, PDP, panel, navigation,
  CTA, or other homepage structure.
- Review focus: commercial hierarchy, no fake checkout UI, no marketplace clutter.

### Torn-Paper Campaign

- Applicable intent: luxury campaign, print ad, tactile editorial poster, fashion poster with paper
  layers.
- Trigger signals: paper, torn, magazine ad, campaign, tactile, print, layered, editorial drama.
- Layout structure: matte paper background, upper torn opening with partial model wearing, lower
  torn foreground edge, jewelry crossing or interacting with paper layers.
- Required modules: paper layer, torn opening, partial wearing or product reveal, spatial shadow,
  restrained copy.
- Product fidelity rules: jewelry must be spatially coherent with skin and paper; paper cannot hide
  key stones, chain links, bails, or pendant logic.
- Text rules: short title/caption only; keep away from torn-edge product detail.
- Aspect fit: usually 3:4.
- Forbidden degeneration: do not make flat paper texture behind a centered product; torn paper must
  create real foreground/background hierarchy.
- Review focus: believable paper fibers, real layer shadows, jewelry remains readable.

### Left-Right Split Poster

- Applicable intent: clean advertising poster, social cover, ecommerce header, wearing plus product
  comparison.
- Trigger signals: split, wearing effect, model on one side, product detail, before/after, comparison.
- Layout structure: left partial model-wearing crop; right same-product cutout on plain or pale
  background; small text block near product.
- Required modules: partial model crop, same-product cutout, split axis, small copy zone.
- Product fidelity rules: worn jewelry and cutout must match; hair/clothing cannot obscure key
  jewelry details.
- Text rules: one short line or supplied copy; no full UI unless the request asks ecommerce.
- Aspect fit: usually 9:16, can adapt to 3:4 with a wider split.
- Forbidden degeneration: do not create two unrelated product views or a simple product-only
  still-life.
- Review focus: same SKU on both sides, clear split hierarchy, model does not dominate.

### Japanese Magazine Catalog Page

- Applicable intent: editorial catalog, magazine page, product explanation, curated page layout,
  text-rich high-end fashion page.
- Trigger signals: magazine, catalog, page, Japanese, editorial labels, numbering, product details.
- Layout structure: white/warm-white page, one dominant hero product, smaller cutout/detail modules,
  numbering, short captions, category labels, and airy magazine text hierarchy.
- Required modules: hero product, at least two smaller detail/product modules, numbering or labels,
  page-like typography.
- Product fidelity rules: detail modules must be derived from the same SKU or clearly declared
  detail crops; no random extra products.
- Text rules: richer text is allowed but must remain short, decorative, and not obscure jewelry.
- Aspect fit: usually 3:4.
- Forbidden degeneration: not a grid, not marketplace collage, not one product with empty margins.
- Review focus: editorial hierarchy, readable modules, no text clutter over jewelry.

### American Fashion Collage

- Applicable intent: Pinterest-style jewelry moodboard, Instagram shopping board, American fashion
  editorial collage, relaxed lifestyle poster.
- Trigger signals: collage, moodboard, fashion board, Pinterest, Instagram, styling, outfit, sketch.
- Layout structure: product-led composition with paper scraps, labels, line sketches, tape, stamps,
  outfit cutouts, plant/shell/architecture drawings, ribbon, or notes chosen from jewelry mood.
- Required modules: hero product, at least three mood elements, one label/caption zone, layered
  paper or sketch structure.
- Product fidelity rules: collage elements must support the jewelry mood and not become substitute
  products; the jewelry remains the visual anchor.
- Text rules: small notes or labels only; no random brand or price.
- Aspect fit: usually 3:4.
- Forbidden degeneration: do not use unrelated props; do not make decorative clutter around a
  centered product.
- Review focus: product-led hierarchy, breathable layering, mood elements match the jewelry.

### default advanced jewelry poster

- Applicable intent: fallback for broad requests such as "几张高级海报", "好看一点", "高级感",
  "3:4海报", or "广告图" when no stronger named card is implied.
- Template selection reason: use this only after checking the six named cards and finding no
  stronger match, or use it as one member of a broad multi-poster set.
- Layout structure: build a multi-module premium poster from jewelry-specific design logic.
- Required modules: hero product plus at least two of detail crop, partial wearing crop, product
  cutout, art-scene object, material surface, paper/card layer, caption zone, or controlled negative
  space.
- If no model reference is supplied, use product cutout, macro detail, material surface, paper/card
  layer, boutique-window stage, or editorial page hierarchy instead of reducing the image to plain
  product photography.
- Product fidelity rules: every module must preserve the same product identity. The art scene may
  change lighting, material, surface, and crop only.
- Text rules: one short title or supplied copy; use no text if the layout is already balanced.
- Aspect fit: 3:4 by default unless user specifies another ratio.
- Forbidden degeneration: anti-still-life-degeneration is mandatory. Do not output only a centered
  product on a soft gradient, a shallow reflection, and one small title.
- Review focus: visible layout strategy, multiple hierarchy layers, product remains premium and
  accurate.

## Broad Request Defaults

For "几张高级海报" with no stricter direction, use complementary templates:

- 4 posters: editorial presentation board, torn-paper campaign, Japanese magazine catalog page,
  American fashion collage.
- If model wearing is unsafe or not desired, replace model-heavy cards with default advanced jewelry
  poster or a product-only magazine/catalog interpretation.
- If the user explicitly asks ecommerce, include luxury ecommerce homepage.
- If the user explicitly asks wearing effect, include left-right split poster.

For "每款做 3 张电商海报", "每个 SKU 做海报库", or similar campaign requests, use:

- Slot A: `Luxury Ecommerce Homepage` as `PDP Hero`.
- Slot B: `Editorial Presentation Board` as a high-end proposal/lookbook board.
- Slot C: `Japanese Magazine Catalog Page` or `default advanced jewelry poster` as macro detail,
  craft, or catalog explanation.

Do not let all three slots share the same composition. Each slot must have a distinct commercial
purpose and visible module hierarchy while preserving the same source jewelry truth.

## Review Checklist

- Did the final prompt name a selected template card and template selection reason?
- Did the prompt include layout modules from that card?
- Did the prompt preserve jewelry truth before describing the poster?
- Did it include anti-still-life-degeneration?
- For broad multi-poster requests, are templates complementary rather than repeated still-life
  variants?
- Would the prompt still be valid if the jewelry product changed category?
- For campaigns, does every source design have the requested slot count and independent output
  files?
- Are dimensions and duplicate checks based on saved outputs rather than planned ratios alone?
