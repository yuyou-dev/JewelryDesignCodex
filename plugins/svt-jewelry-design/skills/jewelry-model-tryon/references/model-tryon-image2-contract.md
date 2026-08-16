# Jewelry Model Try-On Image-2 Contract

## Reference priority

1. Jewelry original: exact product design, silhouette, gemstone cut/color, metal, setting, and proportions.
2. Model original: exact identity, anatomy, pose, skin, clothing, camera, light, and background.
3. Placement composite: approximate location, scale, rotation, and pairing only. Ignore UI, handles,
   flat cutout light, and rough edge.
4. Optional cutout: boundary aid only, never the final material or shadow source.

## Category physics

- Ring: wrap the selected finger, match finger perspective, and hide the far shank naturally.
- Bracelet: wrap the wrist ellipse with gravity/contact and correct near/far occlusion.
- Necklace: follow the neck and collarbone curve with realistic chain gravity.
- Pendant: hang at the chain's lowest point with plausible front orientation and shadow.
- Earrings: connect to a real ear point; when paired, preserve one design but adapt each side's perspective and hair occlusion.
- Brooch: pin to the garment plane with fabric contact, folds, and shadow.

## Fusion and exclusions

Rebuild scene-matched perspective, color temperature, metal reflection, gemstone optics, contact
shadow, and occlusion. Avoid sticker effect, floating, hard cutout edges, duplicate jewelry, wrong
scale, changed face/body/hand, changed clothing, anatomy errors, intersections, text, logos, or UI.
