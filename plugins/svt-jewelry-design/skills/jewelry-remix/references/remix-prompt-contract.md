# Jewelry Remix Prompt Contract

Use this reference after a real source image and the remix brief exist.

## Brief shape

The compiler accepts one JSON object with:

- `schema_version`: exactly `2`;
- `count`: exactly `4` or `8`;
- `source`: workspace-relative source image path;
- `identity`: `type`, `silhouette`, `proportions`, `focal_materials`, `construction`,
  `locked_parts[]`, and `editable_parts[]`;
- `preferences`: `design_system`, `structure_fidelity`, `intensity`, `fusion_strategy`,
  `themes[]`, `morphologies[]`, `styles[]`, `materials[]`, and optional `direction`;
- `references[]`: optional workspace-relative `{path, role}` entries;
- `candidates[]`: stable `REMIX-*` entries with `title`, `positioning`, `difference`, `theme`,
  `morphology`, `style`, `material_craft`, `change_scope`, and `use_case`.

Allowed stable values:

- `design_system`: `gold | gem_set`
- `structure_fidelity`: `high | medium | low`
- `intensity`: `subtle | balanced | bold`
- `fusion_strategy`: `shape_grafting | pattern_translation | structural_rebuild`

Read `remix-taxonomy.v2.json` for the stable IDs allowed in each design system. The four selection
arrays contain IDs, not display labels. An array may include `other` only when the corresponding
`custom_themes`, `custom_morphologies`, `custom_styles`, or `custom_materials` text is non-empty.
The compiler validates the system boundary and resolves the IDs to Chinese prompt language.
The Apps UI message uses camelCase (`schemaVersion`, `designSystem`, `customThemes`,
`customMorphologies`, `customStyles`, `customMaterials`). When saving the compiler brief, map these
to the snake_case fields above and set `schema_version: 2`; do not replace the selected IDs with labels.

Candidate `theme`, `morphology`, `style`, and `material_craft` fields remain concise designer-facing
Chinese branch descriptions. They may elaborate the selected taxonomy but must not contradict its
design system.

Each prepare invocation keeps the designer-facing `REMIX-A` through `REMIX-H` ids in the matrix and
Gallery, while adding a unique batch suffix to runner ids, prompt files, and output paths. Validate
and generate from the exact current `remix/jobs.json` manifest so a later round cannot select or
overwrite an earlier Remix round in the same workspace.

## Branch matrix

| ID | Default role | Difference objective |
| --- | --- | --- |
| REMIX-A | Conservative commercial | Smallest structural change; easiest commercial landing |
| REMIX-B | Motif-forward | Make the selected motif unmistakable through jewelry structure |
| REMIX-C | Craft/material | Lead with setting, surface, metal, and gemstone treatment |
| REMIX-D | Bold concept | Strongest visual memory while remaining wearable |
| REMIX-E | High jewelry | Richer collectible massing and setting hierarchy |
| REMIX-F | Daily lightweight | Reduce volume and craft burden for daily wear |
| REMIX-G | Cultural symbol | Translate cultural language without copying a branded silhouette |
| REMIX-H | Series extension | Build a transferable module for another jewelry type or suite |

Do not use color-only differences. Every branch needs a unique change scope and a visible shift on
at least three of motif, morphology, construction, craft/material, proportion, or use case.

## Identity and reference rules

- The source image controls jewelry type, silhouette, proportion, focal stone, construction, and wearable logic.
- Other references control only their stated role: line, material, craft, composition, or mood.
- Convert motifs into jewelry structure through edges, openwork, relief, setting rhythm, linked
  modules, or local volume. Do not paste a flat symbol onto the product.
- Use one independent prompt and one independent output per stable ID.

## Rendering default

Use a 1:1 centered single-product image on white or very light gray, with realistic precious-metal
reflection, gemstone transparency/fire, a clean silhouette, and a subtle contact shadow. Exclude
text, logos, watermarks, certificates, prices, extra products, floating stones, broken supports,
unwearable devices, toy/plastic appearance, and multi-design collages.
