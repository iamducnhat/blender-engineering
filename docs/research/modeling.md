# Modeling knowledge for a one-prompt Blender skill

Research cutoff: 2026-10-27. The companion source ledger is `modeling-sources.json`; it preserves all 98 records from the seven-ledger OSINT snapshot, including each record's original ID, title, URL, read depth, findings, and limitations. The modeling-specific records are `M01`–`M14`; the other IDs provide control, practitioner, agentic, QA, generative, and harness evidence used by the routing and acceptance rules below. Sources were fetched from their original pages or repositories at the recorded depth. The Studio course indexes are firsthand production guidance, but paid lesson videos were not downloaded.

## Product contract

The target user can describe what they want and judge whether the render looks right. They do not need to know Blender, topology, modifiers or scripting, and they are not expected to coach the agent through mistakes. Therefore the skill must own the technical decomposition, route selection, scene construction, visual inspection and repair loop.

The skill should treat a prompt as a compact design brief:

1. **Intent and use** — hero image, turntable, animation, game asset, 3D print, CAD-like fit, or reusable procedural family.
2. **Reference and style** — supplied image(s), named style, visual adjectives, material cues and what must remain recognizable.
3. **Shape hierarchy** — primary silhouette, secondary construction/panel/limb forms, tertiary surface detail.
4. **View and scale** — hero camera, useful angles, units/dimensions if known, and which areas can be hidden or simplified.
5. **Deliverable** — `.blend`, still/turntable, clean mesh, UV/materials, export, dimensional report or procedural controls.

When a field is missing, infer a conservative default and write the assumption into the report. Ask a question only when an ambiguity can change the modeling route materially (for example, “must this deform?” or “is 45 mm a hard dimension?”). Do not make the user supply implementation instructions.

## Route chooser

Choose one primary route before generating detail. Routes can be combined, but the order matters: the first route establishes the main shape and topology strategy; the later routes add assemblies, materials or presentation.

| Detected request | Primary recipe | Why this route | Required checks |
|---|---|---|---|
| Bottle, vase, cup, knob, column, wheel, lamp body, any radial silhouette | **Profile → Spin/lathe → seam/normals → attachments** (M01) | A 2D profile preserves the important silhouette with few editable controls. Spin is designed for lathe-like forms. | Radial symmetry, profile inflections, opening/wall thickness, welded seam, outside normals, top/bottom caps, hero-camera highlights. |
| Product shell, panel, enclosure, weapon, machine, hard-surface prop | **Silhouette blockout → part boundaries → modifier-first construction → controlled bevel/normal pass** (M03, M09) | Bevel, Solidify, Mirror, Array, Boolean and Edge Split keep iteration fast; panel readability comes from boundaries and highlights, not dense arbitrary topology. | Major outline in orthographic and hero views; gap/overlap logic; bevel width relative to scale; normals; shading at grazing light; no lost primary forms after detail. |
| Character, creature, hand, cloth, deforming organic asset | **Primitive/sculpt or generated mesh → design/pose tests → retopology → detail reprojection → UV/materials** (M04, M10, M11) | The Studio workflow develops the shape first and optimizes topology for deformation, UVs, shading and rigging afterward. | Expression/pose range; edge flow at joints/face; volume retained after SubD; UV stretch; original high-detail source preserved. |
| Room, street, kit, architecture, repeated props, vegetation or variant family | **Semantic assemblies → source assets → collections/instances/Geometry Nodes → controlled variation → camera/material pass** (M06, M07, M12, M14) | Instances avoid duplicating mesh data and procedural graphs expose variant controls while retaining a reusable scene scaffold. | Deterministic seed; instance/readability hierarchy; realize only when unique edits/export require it; camera composition; viewport performance. |
| CAD-like part, measured object, fit/print or engineering requirement | **Units/datum assumptions → exact transforms/snapping → measured constraints → inspect/report** (M08, M09) | Blender provides precision transforms and snapping but is not a full parametric CAD solver; dimensions must be explicit and reported. | Unit system; extents, holes, wall thickness and clearances; named axes/datums; observed vs intended values; tolerance assumptions; manifold/normal check for print. |
| Any asset whose visual identity depends on materials, texture, or presentation | **Stable geometry → UV seams/unwarp → test-grid/stretch check → material/look-dev → target-camera render** (M05, M09, M14) | UV work is most stable after major geometry changes; camera-aware texel density and material response determine whether detail reads. | Test image; seam placement; texel density by camera importance; roughness/normal scale; hidden-surface budget; still plus clay/wire evidence. |

### Routing rules that prevent common failures

- If the object is mostly a surface of revolution, do not start by piling primitives around it. Build and preserve the profile, then add non-radial handles, labels or seams as separate pieces (M01).
- If a hard-surface part is judged from one hero camera, still validate the silhouette in front/side/top or a three-quarter turn. Camera-hidden geometry may be lightweight, but it must not break shadows, reflections, assembly or the requested use (M09, M14).
- If deformation, pose or expression is part of the request, automatic remesh is only a preparation step. Final edge flow is a design decision and must be checked around joints and landmarks (M04, M10, M11).
- If the request contains repeated elements, do not manually duplicate hundreds of unique meshes. Keep one source asset and use collections/instances or Geometry Nodes; realize only at a declared handoff point (M06, M07, M12, M14).
- If the request contains dimensions, do not silently infer a scale from a beauty image. Record the assumed units and return a report with measured extents and unresolved tolerances (M08, M09).
- If the request contains “high detail”, first ask which detail is visible at the target camera and which is only a texture/normal/bake. A dense mesh that does not improve silhouette, highlight response or close-up readability is wasted complexity (M02, M05, M09, M14).
- Blockout is a reversible planning stage, not a ceiling on final quality. Once the silhouette and route are approved, continue through construction, surface detail, UV/materials and presentation gates when the brief asks for a finished model.

## Modeling recipes

### Recipe A — rotational product / bottle

1. Parse the reference into a vertical axis, overall height/radius, profile landmarks (base, shoulder, neck, lip) and wall/opening requirements.
2. Create a deliberately sparse 2D half-profile with enough points to capture silhouette changes. Keep the profile editable and named.
3. Place the 3D cursor on the axis, orient the working view, spin 360° with an intentional radial step count, auto-merge the seam and recalculate outside normals (M01).
4. Add thickness/opening with a separate inner profile, Solidify or controlled inset only when the design calls for it. Do not fill an opening that should be hollow.
5. Add non-radial details as named children: handle, spout, cap, label recess, seam, thread or grip. Use Mirror/Array/Curve/Bevel selectively (M03, M09).
6. Inspect the silhouette in orthographic front/side/top and the target camera. Use a grazing light to reveal dents, waviness or a bad seam. Add SubD only if the base cage and loops produce the intended smoothness (M02).
7. Run a material/UV pass after the shape is stable. Put seams in hidden or natural locations, apply a test grid and render a close-up of the shoulder/lip where highlight quality matters (M05, M14).

**Fallback:** If symmetry breaks visibly, keep the rotational base and move asymmetric edits into separate meshes. If the user actually wants a freeform organic vessel, switch to sculpt/remesh rather than forcing a Spin route.

### Recipe B — hard-surface panels and mechanical props

1. Convert the prompt/reference into a part list: shell, panel, seam/gap, fastener, hinge, control, cable and contact surface. Preserve a semantic collection for each group.
2. Establish units and a scale reference. Use blueprint/photo dimensions when present; otherwise mark assumptions. Match rough width/height/depth with a wire or simple-cube blockout (M09).
3. Lock the primary silhouette and large plane breaks before adding small details. Use Mirror for symmetry, Solidify for thin plates, Array/instances for repeated elements and Boolean only where it makes the design easier to edit (M09, M12).
4. Make panel boundaries readable: actual gaps/insets where the camera needs depth, bevels for controlled highlight rolloff, and separate parts where movement or material changes require it. Do not carve every line into one dense shell.
5. Use Bevel with scale-aware width and Angle/Weight/Vertex Group limits. Use Harden Normals or an equivalent shading strategy so broad planes remain visually flat (M03).
6. If SubD is used, add support loops/creases only at edges that need a specific radius or hold. The modifier's behavior is governed by edge placement and normals; triangles/ngons can remain in stable, non-deforming regions when they do not create shading problems (M02, M10).
7. Test simple movement or part separation before committing. A simplified animation/assembly test often exposes wrong pivots, impossible clearances or a silhouette that collapses when parts move (M09).
8. Refine in descending importance: silhouette, major planes, panel hierarchy, contact/assembly logic, medium details, then screws/knurling/textures. Inspect from multiple angles and at the final camera (M09, M14).
9. Deliver applied scale, sane normals, named collections, placeholder/basic materials, UVs and a modifier/assumption report. Keep the editable source when a modifier remains valuable (M09).

**Fallback:** If booleans leave messy curvature, preserve the approved silhouette and retopologize only the camera-critical or deformed area; do not spend the entire pass chasing invisible all-quad purity.

### Recipe C — organic character or creature

1. Extract design intent: proportions, planar/rounded stylization, landmarks, expression range, pose range, clothing layers and camera distance (M11, M12).
2. Start with primitive forms or a generated base mesh. Sculpt/shape the primary masses first; perform proportion and expression tests before final topology decisions (M04, M10, M11).
3. If the source is a scan or AI mesh, preserve it as a high-detail source. Use voxel remesh for sculpt cleanup or a Quad remesh for a SubD/Multires starting point, while treating the result as provisional (M04).
4. Draw a requirement map over the model: edge-flow direction, primary/secondary creases, articulation boundaries, landmarks and intended deformation. Retopologize around those requirements rather than uniformly covering the object (M10, M11).
5. Use relatively even quads where SubD, sculpt layers, UVs or deformation need them. Allow deliberate triangles/ngons in stable regions if they preserve the required shape, selection and performance; “all quads everywhere” is not the acceptance criterion (M04, M10).
6. Test face, jaw, shoulder, elbow, wrist, hip, knee, fingers and clothing compression. Add proximity loops where a crease must hold under subdivision and articulation loops where a joint must move (M02, M10, M11).
7. Reproject/bake sculpted detail onto the retopo and use UVs/materials for details that do not alter silhouette or deformation. Keep the high-detail source for revisions (M05, M10, M12).
8. Render a neutral clay, wireframe and hero look. The judge should be able to see whether the character reads because of design, shape hierarchy, edge flow, surface detail or lighting (M02, M10, M11).

**Fallback:** For a static bust or background creature, reduce articulation and retopo work according to use. For an animated hero, do not accept a one-click auto-retopo as final without pose/expression evidence.

### Recipe D — scene, kit and procedural assembly

1. Build a semantic scene graph: environment, hero asset, secondary assets, repeated kit pieces, lighting/camera and materials. Use collections and stable names so the result can be inspected without Blender expertise.
2. Model one clean source for every repeated form. Use object/collection instances or Geometry Nodes to distribute, rotate, scale and vary them; keep a deterministic seed and exposed controls (M06, M07, M12, M14).
3. Keep geometry as instances while applying operations that can be shared. Realize only when per-copy topology must change, for baking/export or when the final handoff requires unique meshes; report the memory cost (M07).
4. Choose variation that supports the visual brief: controlled scale/rotation/color bands, rhythm, clustering and negative space. Randomness must not destroy composition or make the scene look noisy.
5. Use a camera-responsive preview. The final camera, turntable and a simple clay pass should be available before expensive textures or high subdivision (M02, M14).
6. Add materials by role and contrast: primary surface, accent, recess/contact, transparent/emissive and environment. Keep a small palette unless the reference demands variety.
7. For repeated procedural details, use adaptive or camera-aware density where possible. Preserve hero exceptions as explicit geometry so the main read is not flattened by a generator (M02, M12, M14).

**Fallback:** If procedural nodes obscure why a result looks wrong, freeze a chosen variant into named source objects for the visual pass, while keeping the generator in a separate collection for future edits.

### Recipe E — CAD-like precision / print / fit

1. Translate natural language into a dimensional contract: units, reference datums, overall extents, hole/slot sizes, wall thickness, clearances, symmetry and acceptable tolerance. Mark inferred values as assumptions.
2. Use exact typed transforms, axis constraints and snapping, not mouse-only placement. Maintain named empties/axes or a simple measurement sheet that records each critical feature (M08).
3. Construct with parameterized primitives, profile/curve operations, Boolean cuts or modifier stacks that retain editability. For repeated holes/fasteners, use arrays/instances with explicit spacing.
4. Verify dimensions after modifiers are applied or evaluated. Compare intended values with measured extents, inspect manifoldness/normals, check wall thickness and clearances, and record any unresolved tolerance.
5. For 3D printing, use a watertight outer shell and a physically plausible wall/thickness route. For visual CAD-like renders, preserve the same dimensions but do not imply engineering certification.
6. Deliver the `.blend`, a rendered inspection sheet and a machine-readable report. The report must state units, assumptions, measured values, route, modifiers, and what was not verified (M08, M09).

**Fallback:** If the prompt asks for constraints the available Blender route cannot enforce, say so in the report and build a visually consistent approximation with the constraints exposed as editable parameters. Do not present an approximate model as a certified CAD part.

### Recipe F — UV, materials and render handoff

1. Freeze large geometry edits before the final unwrap. Keep a working UV only if it helps guide modeling, but expect cleanup after topology changes (M05).
2. Mark seams according to material breaks, hidden/low-attention edges and natural construction seams. Unwrap, adjust settings, apply a distortion test grid and fix the most visible stretch first (M05).
3. Allocate texel density by camera importance and material role. High-resolution hero surfaces can coexist with reduced or textureless hidden surfaces when they do not affect shadows/reflections or the stated use (M09, M14).
4. Build a small material system with readable physical cues: base color, roughness, specular/metallic response, normal/bump scale and edge wear only where the reference supports it. Do not use texture noise to compensate for a wrong silhouette.
5. Render at least: hero look, neutral clay, wire/retopo view and one alternate angle. Compare primary silhouette, shape hierarchy, detail density, highlight continuity and camera-hidden errors before accepting the result (M02, M05, M09, M11, M14).

## Universal acceptance gates

These gates are shared by every route. They are intentionally about visible function and handoff quality, not a rigid modeling ideology.

1. **Reference gate:** the chosen style/reference and any inferred assumptions are recorded. If the concept is ambiguous, the agent creates a small contact sheet of plausible directions and picks one before detailed modeling (M09, M11, M12).
2. **Silhouette gate:** primary form reads in flat clay from hero and alternate angles. The agent must inspect outline, major negative spaces and proportions before adding tertiary detail (M02, M09, M10, M14).
3. **Shape-hierarchy gate:** primary, secondary and tertiary details are visually distinct. Detail density follows feature importance and camera distance; hidden geometry is not overbuilt unless it affects light, assembly or use (M02, M05, M09).
4. **Topology gate:** topology is fit for its use. SubD and deformation require deliberate flow/loops/normals; stable static surfaces may retain deliberate triangles/ngons. There is no universal all-quads pass condition (M04, M10, M11).
5. **Shading gate:** no unexpected dents, black patches, broken normals, bevel pinching, boolean seams or SubD collapse in the rendered view. Recalculate/check normals and inspect a grazing-light pass (M02, M03, M09, M10).
6. **Complexity gate:** viewport and render budgets are explicit. Use low control cages, instances, adaptive subdivision and procedural sharing where they preserve the look; avoid dense geometry whose only effect is a hidden or unreadable detail (M02, M06, M07, M12, M14).
7. **UV/material gate:** stable geometry has a usable unwrap, a distortion check, sensible texel density and materials that support the reference. Texture detail cannot conceal a broken silhouette (M05, M09, M10).
8. **Use gate:** animation assets survive basic pose/expression tests; CAD/print assets pass dimension/manifold checks; scene assets have named collections, pivots and source/instance logic; still assets have a camera and a reproducible render (M08, M09, M10, M11, M14).
9. **Handoff gate:** save `.blend`, render evidence, chosen route, assumptions, parameters/seeds, modifier stack, object/collection map, known limitations and a concise next-edit recipe. This lets a non-expert judge the result without becoming the technical operator (M10, M13, M14).

## One-shot execution protocol

The skill's internal prompt should cause the following loop without asking the user to provide Blender instructions:

1. **Parse and classify.** Extract subject, style, use, camera, dimensions and deliverables. Pick one primary route and explain it in one sentence.
2. **Declare assumptions.** Write units, symmetry, deformation, camera and hidden-surface assumptions into a small manifest.
3. **Build a reversible blockout.** Use source profiles, primitives, collections, instances and modifiers. Save a checkpoint before applying destructive operations.
4. **Self-review visually.** Render clay/outline/alternate-angle evidence. Check silhouette, proportion, shape hierarchy and camera-hidden artifacts.
5. **Repair by priority.** Fix primary silhouette first, then secondary construction, then shading/topology, then tertiary detail. Never add detail to avoid fixing a large-form error.
6. **Complete the use-specific pass.** Retopo/pose tests for organic assets; bevel/normals/assembly for hard-surface; instances/GN for scenes; units/measurements/report for CAD; UV/material/render for look-dev.
7. **Render a judgeable handoff.** Provide hero render plus clay/wire/alternate view and a short plain-language report. The user can say “the shoulder is too wide” or “the bevel is too sharp” from the images without knowing how to edit the mesh.
8. **Preserve editability.** Keep named source objects, profiles, node groups and parameters. Apply modifiers only when required for export, final static geometry or a declared handoff.

## Non-goals and evidence boundaries

- These sources support a route-selection and review discipline; they do not prove that a single generic prompt can produce a production-ready arbitrary model without a visual feedback loop.
- Blender Studio pages describe real artist workflows, but a paid curriculum index is not evidence that every lesson is accessible or that the agent has watched it.
- The Blender Developer Blog asset-pipeline post is a 2021 design proposal. Use it for principles (interactive, non-destructive, integrated asset systems), not as a claim that every planned feature exists in Blender 5.2.
- Automatic voxel/Quad remesh, Geometry Nodes and generated scripts are acceleration tools. They do not replace design reference, camera review, deformation tests or explicit dimensional verification.
- A beauty render can hide topology, scale and manifold errors. Always pair it with a clay/wire/inspection view appropriate to the requested use.

