# Scenes, kits, and procedural assemblies

Use this recipe for rooms, dioramas, architecture, environments, repeated kits, product arrangements, and any brief where relationships between many objects matter more than one monolithic mesh.

## Build order

1. Convert the brief into a scene graph: ground/support, primary subjects, secondary assemblies, repeated assets, camera, lighting, and material palette. Give each semantic part/instance a stable name or identifier.
2. Establish world scale, camera, composition, and main negative space with simple source assets. Check framing and support before adding detail.
3. Build reusable source assets, then place instances or Geometry Nodes distributions. Keep source geometry editable and deterministic. Record seed/parameters and collection membership.
4. Add relationships: support, contact, attachment, clearance, occlusion, path, and intentional overlap. A bounding-box overlap is only a broad-phase warning; inspect the actual relationship where it matters.
5. Vary repeated assets through controlled transforms, materials, rotations, and limited shape variants. Avoid identical rhythm and avoid random noise that weakens the composition.
6. Refine hero assets separately from background assets. Use camera-aware detail and UV/material allocation. Keep hidden surfaces lightweight only when they cannot affect shadows, reflections, alternate views, or required interactions.
7. Render hero, front/side/back or bird's-eye, and targeted section/underside views. Review composition, scale, readability, density, support, and lighting hierarchy.
8. Realize instances only for an explicit downstream need such as unique sculpt/edit, bake, or target export. Record the memory/complexity change and rerun checks.

## Procedural and instance guidance

- Use Geometry Nodes for repeated/parameterized structure, scattering, vegetation, kit families, and controlled variation. Keep aesthetic controls legible: proportion, density, rhythm, palette, seed, and camera framing.
- Use instances when many copies share source geometry. Keep semantic identity and world transform for each instance in the manifest.
- Use explicit mesh/assembly parts for hero objects, functional connections, or regions that need individual material, rig, or repair decisions.
- Do not turn a whole scene into one opaque generated mesh when the brief implies editable parts, relationships, or iteration.
- More objects do not automatically mean more detail. Complexity must preserve readability and hierarchy.

## Defect table

| Observation | Likely cause | Repair scope |
|---|---|---|
| Scene feels empty or cluttered | Composition/density hierarchy is wrong | Repair primary/secondary placement and negative space before detail |
| Objects float or intersect | Missing support/contact/clearance relation | Localize affected assembly; inspect ground, underside, and side views |
| Repetition looks procedural in a bad way | Identical transforms or uncontrolled randomization | Adjust source variation/seed and protect the focal subject |
| Background detail competes with hero | Material/value/scale hierarchy is flat | Reduce background density/contrast; keep hero silhouette readable |
| Scene opens with missing parts/materials | External dependencies or unrecorded collection/instance source | Pack/copy required dependencies, fresh-reopen, and report missing assets |
| View looks good only from hero camera | Composition or assets are camera-cheating | Render complementary views and make alternate-view requirements explicit |

## Acceptance

Pass when required subjects and relations are present in the evaluated scene, the composition reads from the intended views, repeated assets remain coherent, and the scene can be reopened with its declared dependencies. A scene render does not prove hidden assembly correctness; apply role-specific support, collision, material, rig, print, or export checks where requested.

Primary references: [Geometry Nodes introduction](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/introduction.html), [Instances](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/instances.html), [Blender Studio modeling guide](https://studio.blender.org/tools/artist-guide/asset-creation/modeling), and [SceneCraft](https://arxiv.org/abs/2403.01248).
