# Hard-surface and panel recipe

Use this recipe for products, furniture, tools, machines, vehicles, props, enclosures, and designed panels. The goal is a readable part hierarchy and believable edge response. Topology is a means to that result; there is no universal all-quads or blanket closed-mesh rule.

## Build order

1. Read the reference for primary silhouette, major planes, panel boundaries, functional openings, supports, handles, fasteners, and camera-critical edges. Build a part graph before adding surface detail.
2. Establish units/scale and the main proportions with simple named parts. Inspect front, side, back, top, and hero views before committing detail.
3. Separate primary body, panels, inserts, fasteners, handles, hinges, and internal/hidden parts when their materials, transforms, or repair scopes differ. Use modifiers and source curves while the form is changing.
4. Resolve panel hierarchy: which surfaces are continuous, which are seams/recesses, which are overlays, and which are actual gaps or cavities. Avoid texture-only treatment when a camera-critical break needs geometry.
5. Use controlled bevels, support loops, creases, weighted normals, or shading settings to create highlights that explain the form. Apply scale before judging width. Limit bevels by angle, weight, or named groups instead of beveling every edge blindly.
6. Use booleans for real cuts and openings when they improve editability, but inspect their scale, normals, thin walls, intersections, and modifier order. Keep a pre-boolean checkpoint and apply only when the target/use requires it.
7. Add secondary/tertiary detail according to the camera and style grammar. Use instancing for repeated parts and explicit geometry for hero features whose individual placement matters.
8. Run structural and visual checks, then create UV/material/render handoff. Do not let material wear, bevel highlights, or lighting conceal an unresolved silhouette or connection.

## Geometry and topology decisions

- Use quads where they support deformation, SubD, clean selection, or predictable edits. Deliberate triangles/ngons are acceptable for static planar areas or hidden regions when they do not harm the requested use.
- Thin shells, curves, separate overlays, and overlapping boolean cutters can be correct for render or assembly roles. Only require manifold/watertight geometry when print, simulation, boolean stability, or a target export actually needs it.
- A bevel is not a panel design. A smooth highlight on the wrong plane is still wrong.
- A high polygon count is not detail quality. Preserve large shape, edge hierarchy, material contrast, and readability before adding micro screws or surface noise.
- Camera-hidden errors remain relevant when they affect silhouettes, shadows, reflections, assembly, deformation, or alternate requested views. Do not spend equal budget on every surface without checking use.

## Local defect table

| Observation | Likely cause | Repair scope |
|---|---|---|
| Product identity is weak despite many details | Primary silhouette/plane hierarchy is wrong | Restore body/panel checkpoint; repair proportions and major planes |
| Panel edge is too soft or catches an unexpected highlight | Bevel width, scale, normals, or support treatment is wrong | Adjust named edge group/bevel/normals; rerender close-up |
| Boolean creates pinching, shading spikes, or missing faces | Scale, cutter overlap, normals, or modifier order | Restore pre-boolean checkpoint; fix cutter and scale locally |
| Handle/hinge appears detached | Part graph lacks support/contact or transform is wrong | Repair attachment and clearance; inspect side/back/underside |
| Repeated details look mechanical and noisy | No density hierarchy or uncontrolled instancing | Reduce instances, introduce controlled variation, protect hero areas |
| Beauty render hides invalid geometry | Lighting/camera is doing the work | Run clay/wire and alternate views; fix geometry before material polish |

## Acceptance

Pass when the requested identity is legible from the intended views, named parts have believable relationships, critical edges read under neutral lighting, and the evaluated mesh/material state meets the use profile. A render prop may retain separate overlays or thin shells; a print or simulation profile needs stricter checks. Record the profile instead of declaring one topology policy universal.

Primary references: [Blender Studio modeling guide](https://studio.blender.org/tools/artist-guide/asset-creation/modeling), [Blender Studio live retopology notes](https://studio.blender.org/blog/live-retopology-at-bcon22/), [Bevel Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/bevel.html), and [Subdivision Surface Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/subdivision_surface.html).
