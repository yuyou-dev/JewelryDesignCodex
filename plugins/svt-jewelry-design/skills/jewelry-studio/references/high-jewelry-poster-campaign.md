# High-Jewelry Poster Campaign Method

Use this reference when a request asks for multiple ecommerce posters, campaign posters, customer
review poster sets, gallery delivery, or "each design gets several high-end posters".

This method is provider-neutral. It captures reusable poster planning and verification knowledge;
ordinary still-image execution follows the bundled plugin Image-2 runner unless the user
explicitly requests another provider in the current message.

## Campaign Unit

One poster equals one independent image output, prompt, file, and Image-2 job.

Do not count a collage, contact sheet, grid, or long strip as multiple posters unless the user
explicitly asks for a combined sheet. If the user says each source design needs three posters, create
three independent poster jobs and three final image files per design.

## Default Three-Slot Matrix

For broad ecommerce poster campaigns, use three complementary slots per source design:

1. `PDP Hero / Luxury Ecommerce Homepage`
   - Commercial first screen or product detail hero.
   - Product is dominant and immediately inspectable.
   - Include ecommerce hierarchy such as hero product area, product-card/PDP module, refined panel,
     controlled negative space, and optional neutral CTA/navigation marks.
   - No fake price, fake store UI, URL, QR code, social handle, or invented brand mark.

2. `Editorial Board / Lookbook Presentation`
   - High-jewelry proposal board or lookbook page.
   - Include product cutout, macro crop, category-correct wearing/detail crop when safe, color board,
     caption zone, and layered hierarchy.
   - The model crop supports scale and mood; it must not become the subject or hide jewelry.

3. `Macro Detail / Magazine Catalog`
   - Craft, gemstone, setting, chain, bail, hinge, clasp, or surface detail.
   - Use either `Japanese Magazine Catalog Page` or `default advanced jewelry poster`.
   - Include hero product plus detail modules, numbering/labels or paper/card/material layers.
   - Do not reduce this slot to another centered still life.

For a larger set, keep the first two slots stable and vary the third slot across `Japanese Magazine
Catalog Page`, `default advanced jewelry poster`, `American Fashion Collage`, or `Torn-Paper
Campaign` according to product category and model-safety constraints.

## Jewelry Truth Lock

Every poster prompt in a campaign must repeat the source product truth. Do not rely on an earlier
prompt or a shared brief alone.

Lock:

- source design id and source image path
- jewelry category and wearing location
- silhouette and proportions
- stone hierarchy, stone count, stone positions, and main stone shapes
- metal direction, finish, and plating/rhodium accents
- setting logic, chain/bail/hinge/clasp/link/connector logic
- left/right pair logic for earrings
- allowed changes limited to photography, crop, angle, lighting, background, cutout cleanup,
  product-card layout, macro crop, and poster composition

Sapphire and turquoise campaigns need explicit material language:

- sapphire is deep royal blue corundum with gemstone fire, not transparent blue glass
- turquoise is opaque polished mineral, cabochon, carved, or inlay-like, not transparent glass,
  cheap plastic, or generic jade

## Prompt Fields

Each final poster prompt should include:

- `Poster ID`
- `Source design ID`
- `Chosen poster template`
- `Template reason`
- `Required layout modules`
- `Jewelry truth reference`
- `Product fidelity locked`
- `Allowed photographic/layout changes`
- `Typography policy`
- `Poster differentiation`
- `Forbidden`
- `Expected output path`

For batch campaigns, use the runner's existing jobs and state mapping:

```text
poster_id -> source_design_id -> slot -> template -> source_image -> prompt_path ->
expected_output_path -> provider -> status -> dimensions -> sha256
```

## Poster Differentiation

Build a visible poster strategy into each prompt so the requested output does not collapse into a
plain product still life.

A high-jewelry poster must show a visible poster strategy. It may not collapse into:

- centered product plus soft background
- shallow reflection with one small title
- repeated product still-life with only a changed background
- equal-size grid pretending to be a magazine page
- product hidden by model, hair, clothing, props, paper, or UI panels

Require at least two visible poster-layout modules beyond the jewelry object, such as product card,
macro crop, model/detail crop, caption zone, page numbering, paper layer, art-scene surface, split
axis, ecommerce panel, or controlled negative-space hierarchy.

## Campaign Verification

Before delivery, verify objective delivery facts:

- requested source count times posters per source equals saved poster count
- each source design has the required slot count
- every poster has its own prompt path and output path
- dimensions were read from saved image files, not guessed
- declared aspect ratio is consistent with actual dimensions or recorded as provider variance
- no duplicate SHA256 groups unless intentional alternates are documented
- no poster is only a combined sheet when independent files were requested
- no automatic ranking, approval state, or subjective regeneration ran without an explicit request

## Common Failure Modes

- Treating ChatGPT or another external provider as required instead of an explicit provider
  exception.
- Generating three posters as one image.
- Reusing the same composition for every slot and changing only title or background.
- Redesigning the source jewelry: wrong category, changed main stone, extra stones, missing chain,
  wrong metal, or altered setting logic.
- Making sapphire look like transparent blue glass.
- Making turquoise transparent, plastic, jade-like, or glassy.
- Adding fake brand marks, prices, URLs, QR codes, social handles, watermarks, or random text.
- Letting model, hair, hands, fabric, props, product cards, or text cover the jewelry.
- Starting an unrequested aesthetic approval or regeneration pass after delivery.
