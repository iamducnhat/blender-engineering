# Route chooser

Use this reference after the required preflight reread. Classify by visible form, intended use, target representation, and available capabilities. The route is a proposal until the first useful render/inspection confirms that it is preserving the requested identity.

## Target inference

Infer the target from the request and references:

- A 3D editable scene, Blender file, 3D render, animation-ready mesh/rig, or 3D export implies a Blender-capable route unless another authoring environment is explicitly named.
- If a runtime is named, select its geometry/rig/export profile and record the target-specific acceptance boundary. Do not assume that a GLB/FBX export proves native playback or runtime behavior.
- If no runtime is named, choose a finished 3D representation that best matches the brief, record the assumption, and include a target-neutral manifest. Do not invent a game-ready or rig-ready claim.

Read `animation-contract.md` whenever the requested 3D model must be rig-ready, deformation-tested, retargetable, or exported with explicit root/pivot, units, axes, or skeleton semantics.

## Form/use matrix

| Signal in the brief | Primary route | Preserve and check | Switch or hybridize when |
|---|---|---|---|
| Bottle, vase, knob, column, wheel, lathed product | Profile-first revolve/Spin | Axis, silhouette, thickness, seam, normals, openings, attachments | Handles, asymmetrical panels, or organic transitions dominate |
| Product, furniture, panel, machine, hard-surface prop | Named part graph plus primitives/curves/modifiers/booleans | Primary silhouette, panel hierarchy, support highlights, functional joins, scale | Curvature or likeness requires sculpt/generated base |
| Character, creature, face, cloth-like organic object | Sculpted/authored/generated base, cleanup, optional retopo | Shape hierarchy, pose/expressions, silhouette, deformation landmarks, provenance | Repetition/parametric variation is the dominant requirement |
| Room, diorama, kit, city, repeated environment | Scene graph, source library, instances/Geometry Nodes | Support/contact, composition, scale, visible relationships, detail rhythm | One hero object needs unique sculpt or manual polish |
| Print, fit, mechanism, measured assembly | Unit-aware parts, datums, constraints, dimensions, explicit mates | Intended dimensions, tolerances, clearance, thickness, articulation, export report | Exact fit cannot be guaranteed from missing measurements |

## Route selection questions the agent answers silently

1. What must read from the intended camera or view? Protect that silhouette before micro-detail.
2. Is the form controlled by a few dimensions/parameters, or is it an appearance/likeness problem?
3. Does the target need separate parts, deformation, UVs, materials, print fit, rig-ready geometry, or a 3D export?
4. Which capabilities are available now: Blender data API, render, external asset import, generator, export, target runtime?
5. Can the primary route produce the required representation, or only a preview? If only a preview, choose a hybrid or report `INCOMPLETE`.

Do not ask the novice to answer these in technical language. Convert the ordinary request into a contract and expose only assumptions that materially affect the delivered result.

## Procedural versus generated/asset versus hybrid

Choose procedural/parametric when:

- the shape is describable by profiles, dimensions, repetitions, constraints, or a small number of art parameters;
- deterministic reruns and editability matter;
- geometry must report measurements or preserve named relationships.

Choose an authored/imported/generated asset when:

- the visual identity is dominated by organic curvature, likeness, sculptural detail, or a reference-driven surface;
- a capable source asset exists and provenance/license can be recorded;
- building the form from primitives would flatten the requested style.

Choose a hybrid when the generated/asset base supplies the difficult shape but still needs part separation, cleanup, retopology, UV/material work, constraints, rigging, or camera-specific detail. Keep the original source and a checkpoint before destructive cleanup.

Do not promote a provider capability claim to a local capability. Run a cheap probe or inspect the returned artifact before committing the route. If a generator produces a splat, image, or non-editable representation, record that representation and do not call it a finished mesh.

## Stop and switch conditions

Switch route when any of these is true:

- the silhouette remains wrong after a localized repair;
- a required part/relationship cannot be expressed in the current representation;
- the route is spending detail to hide a primary proportion error;
- imported/generated topology cannot support the requested deformation, UV, print, or export target;
- the target runtime requires semantics absent from the current file;
- the helper/backend repeatedly fails for transport reasons and a deterministic local route can meet the same contract.

Preserve the best checkpoint before switching. Explain the cause as transport, representation, recipe, capability, or aesthetic mismatch. Do not silently downgrade the brief to fit the failing route.

## Route record

The receipt should contain:

```text
route_id and recipe
target representation/runtime
capability probe and version
source/generated asset provenance
protected criteria
assumptions and confidence
fallbacks attempted
checkpoint selected
checks and unresolved limitations
```

The route is successful only when the artifact and its use-specific checks support the requested deliverable. A completed procedural script or imported provider asset alone is not success.
