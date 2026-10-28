# UV, material, lighting, and render handoff

Use this reference after the major form is stable or when the brief explicitly requires materials, textures, UVs, lighting, or a presentation render. Materials should clarify shape, part hierarchy, and style; they must not hide unresolved modeling defects.

## Build order

1. Write a short style grammar: palette, value hierarchy, roughness range, edge response, pattern scale, wear language, transparency/emission policy, and lighting mood. Separate observed reference facts from interpretation.
2. Decide whether a feature belongs in geometry, a curve/instance, a material, a texture, or post-processing. Use geometry for camera-critical silhouette and parallax; use shading for repeatable surface variation; do not add invisible complexity merely to increase counts.
3. Freeze major shape and topology decisions before unwrapping. Keep a high-detail or procedural source when baking/reprojection may be needed. Preserve material slots and semantic names through repairs.
4. Unwrap according to the use and camera. Allocate texel density to focal regions, keep seams where they are defensible, and run a test grid/checker render. A successful unwrap operation is not proof that the visible texture is undistorted.
5. Build materials with explicit, deterministic parameters. Test base color/value, roughness, normal/bump scale, metallic/transmission, and texture color space under neutral lighting before adding dramatic lights.
6. Render a neutral clay pass, material pass, and final presentation pass. Compare hero, front/side/back/top or targeted underside/close-up views. Keep overlays, score prompts, and diagnostic labels out of the final beauty evidence.
7. Pack or copy required images, procedural inputs, fonts, and HDRIs when delivery requires a self-contained file. Fresh-reopen the saved artifact and verify that materials and textures still resolve.

An absolute path that works on the author machine is not a portable delivery.
Keep required external files in the delivery tree with relative paths, or pack
them when the format supports it. Include a hashed dependency manifest and
reopen a relocated bundle copy. Confirm each required dependency is embedded or
inside that copy; an ordinary fresh process can still see an author-only path.
Preserve source files and do not hide or move the user's originals to run a test.

## Camera and detail budget

- Give the largest detail budget to silhouette, landmarks, contact edges, and the requested viewing distance. A pore or scratch cannot repair a wrong proportion.
- Let background and hidden surfaces use simpler materials only when they cannot affect requested shadows, reflections, alternate views, deformation, or export.
- Use controlled variation for procedural materials and record the seed/parameters. Random noise without scale or hierarchy reads as dirt and can make a clean design look broken.
- Keep lighting from becoming a substitute for geometry. If a bevel or panel reads only under one flattering light, inspect its shape in clay and alternate lights.

## Defect table

| Observation | Likely cause | Repair scope |
|---|---|---|
| Texture is stretched or seams are conspicuous | UVs were made before shape settled or islands are poorly allocated | Re-unwrap the affected region and rerun a test-grid render |
| Material makes a wrong form look convincing | Strong light, roughness, or normal map is masking geometry | Restore neutral/clay evidence and repair the form |
| Object looks flat despite correct base color | Value/roughness hierarchy, bevel, normals, or scale is missing | Repair the affected material/edge group, then inspect shape |
| Procedural detail is noisy or repeats obviously | Seed, scale, density, or variation is uncontrolled | Expose deterministic parameters and reduce detail before adding more |
| Final file opens without images or has pink/missing materials | External dependencies were not packed or recorded | Restore the material checkpoint, pack/copy dependencies, fresh-reopen |
| Render quality changes between runs | Unrecorded camera, color-management, samples, or seed state | Record render settings and rerun from the accepted checkpoint |

## Acceptance

Pass when the style grammar is coherent, required materials/UVs resolve after reopen, focal forms remain readable under neutral and final lighting, and the render set exposes rather than conceals defects. Report whether textures are packed, external, procedural, or unavailable. A beauty render is evidence for appearance only; it does not prove topology, rig, print, export, or runtime quality.

Primary references: [Blender UV unwrapping introduction](https://docs.blender.org/manual/en/latest/modeling/meshes/uv/unwrapping/introduction.html), [Blender Studio modeling guide](https://studio.blender.org/tools/artist-guide/asset-creation/modeling), [Geometry Nodes introduction](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/introduction.html), and [Blender glTF material guidance](https://docs.blender.org/manual/en/latest/addons/import_export/scene_gltf2.html).
