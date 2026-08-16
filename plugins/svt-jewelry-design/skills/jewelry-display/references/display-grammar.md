# Jewelry Display Grammar

This reference turns high-quality product-display references into reusable scene grammar. Use it
before writing prompts for `$jewelry-display`. The goal is a controlled product display, not a
poster, mood board, or campaign layout.

## Core Principle

The jewelry is the selling object. Props are display hardware, not decoration. A flower, branch,
silk fold, shell, vase, stone, paper shape, or hand must have one clear role:

- support: cradle, hook, rail, lip, fold, fork, or platform
- line: diagonal, vertical drop, S-curve, or edge-entry guide
- field: large low-detail quiet form that creates negative space
- frame: soft foreground or edge crop that directs attention

If a prop has no role, remove it from the prompt.

## Reference Deconstruction Checklist

For each reference image, extract structure rather than style words:

- aspect ratio and crop: square, 4:5, 3:4, vertical macro, horizontal still life
- product position: center, lower third, right third, off-center, edge-tension crop
- product scale: hero product 35-70%, medium 20-35%, tiny precise product 8-20%
- negative space: top, left, right, background field, flower field, sky-like field
- visual line: chain vertical, silk S-curve, branch diagonal, petal curve, hand line
- support contact: hook, lip, fold, fork, petal throat, stone groove, tabletop contact shadow
- occlusion boundary: what can be hidden, what must stay visible
- prop contrast: prop lower detail/lower contrast than jewelry unless it is the physical stage
- lighting: softbox, backlit silk, macro sparkle, directional shadow, high-key diffusion
- poster drift risk: text, brand block, price, logo, collage, campaign copy, decorative story

## Negative Space Rules

- Use 40-70% calm empty area for botanical, suspended, and premium ecommerce modes.
- Empty does not mean blank: it can be a pale wall, soft gradient, low-detail flower surface, sky-like
  color field, frosted glass, or quiet paper.
- The quiet area must have no random text, logo, dust, busy shadows, extra jewelry, or stray petals.
- Product can be small in negative-space images, but it must be the sharpest, highest-contrast,
  highest-value signal.
- If the product occupies under 20% of the frame, the composition must include a strong leading line:
  chain drop, stem diagonal, silk S-curve, branch arc, or petal edge.

## Asymmetry Rules

- Define one visual weight and one counterweight. Example: small sharp pendant at lower right,
  large soft flower at upper left.
- Use edge-entry props: branch from upper right, silk from top left, petal from lower edge, chain
  from top edge.
- Do not center everything after asking for asymmetry. Put the product on a third, near a support
  point, or at the end of a leading line.
- Asymmetric pairs are allowed: one earring higher, one ring angled away, one chain side longer.
  Both products must remain readable.

## Support Physics

- Describe how the product is held: hung over a vase lip, threaded through a flower throat, resting
  in a petal fold, hooked on a branch fork, cinching a silk ribbon, leaning on stone, or resting on a
  frosted glass plinth.
- Gravity must make sense. Chains hang downward. Bracelets arc with weight. Rings rest or hook at a
  visible point. Earrings need hooks/posts/backs when visible.
- Occlusion is allowed only at support points: chain back, ring underside, earring post back, clasp
  edge, or product back.
- Never hide the hero stone, pendant face, earring drops, ring shank closure, prongs, bezels, bail,
  clasp logic, or visible connection points.

## Botanical And Textile Props

- Use one botanical idea per image: single calla lily, single petal, one branch, one leaf, one pale
  flower, or one controlled flower cluster. Avoid bouquet logic.
- Flower and silk should be lower contrast or softly focused when the jewelry is small.
- For silk, specify transparency, one S-curve, backlit edge, and no fabric over stones.
- For branches, specify one clean branch path and exact hook/fork contact; avoid dense foliage.
- For petals, specify petal surface as a cradle or negative-space field; avoid petals crossing the
  product face.

## Product-Display Versus Poster

Product display:

- mostly text-free
- one product or product pair
- construction readable
- props serve support and scale
- useful for PDP, gallery, ecommerce detail, or designer review

Poster/campaign:

- brand text, collection title, price, QR code, logo, layout block, collage, or ad copy
- storytelling and graphic hierarchy may be stronger than product readability
- route to `$jewelry-poster` unless explicitly requested

When a reference includes brand text, extract spacing, support, prop hierarchy, crop, and lighting.
Do not ask image-2 to invent readable brand text.

## Prompt Blueprint

Write prompts in this order:

1. Output type and aspect ratio.
2. Product truth: category, materials, gemstones, setting, construction, scale, locked references.
3. Display mode and product-display goal.
4. Composition blueprint: product position, negative-space area, visual line, crop, counterweight.
5. Support physics: exact contact point and gravity/continuity.
6. Lighting and camera: lens, focus plane, softbox/backlight, shadow quality.
7. Background and prop hierarchy.
8. Forbidden elements and occlusion limits.

Do not start the prompt with atmosphere, flowers, fantasy, campaign, brand story, or color palette.
