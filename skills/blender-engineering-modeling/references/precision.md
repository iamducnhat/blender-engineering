# Measured, print, fit, and CAD-like recipe

Load this recipe when the brief names dimensions, tolerances, clearance, fit, fabrication, 3D printing, machining, a mechanism, or CAD-like accuracy. A visually plausible render is not dimensional evidence. First decide which measurements are requirements and which are inferred from an image or an approximate reference.

## Contract before geometry

1. Record units, axis convention, scale, origin/datums, and the required precision. Set the scene unit policy before creating parts; do not repair a scale mismatch at export by silently changing the object.
2. Extract the smallest set of explicit dimensions and constraints. Mark inferred values, reference-image estimates, and assumptions. If the request leaves a dimension underdetermined, choose and report a coherent assumption rather than pretending it was measured.
3. Build a named part graph with interfaces, mates, supports, axes, holes, joints, and moving envelopes. Keep design parameters and source profiles editable where a revision is likely.
4. Use snapping, numeric transforms, constraints, curves, modifiers, or a parametric/procedural route according to the task. Blender precision controls improve repeatable input; they are not a general CAD constraint solver.
5. Evaluate the final geometry in object mode and report bounding-box dimensions, key datum-to-datum distances, part count, and tolerances. Report measured values from the saved artifact, not values copied from the generation prompt.

## Choose the use profile

- **Visual prop:** prioritize silhouette, proportion, readable interfaces, and camera-aware detail. Report approximate dimensions if useful; do not invent manufacturing guarantees.
- **Fit or mechanism:** test rest/open/closed poses, joint limits, contact, clearance, collision, insertion direction, and the required envelope. An intentional overlap must be named; an unexplained intersection is a defect.
- **Print/fabrication:** apply only the requested process profile. Check scale, wall/thickness, normals, non-manifold/loose geometry, overhang/support assumptions, minimum gaps, and the chosen export. A closed/manifold mesh is a use-specific requirement, not a universal modeling rule.
- **CAD-like assembly:** retain semantic parts and mates, keep constraints/parameters legible, and produce a dimension/assumption report. A polished mesh with no relation data does not prove assembly correctness.

## Defect table

| Observation | Likely cause | Repair scope |
|---|---|---|
| Overall size is right but interfaces do not meet | Wrong datum, origin, axis, or unit assumption | Restore the dimensional checkpoint; repair the local mate and rerun envelope checks |
| Parts appear to fit in a hero view but collide when moved | No motion envelope or only a bounding-box check | Test named states and repair the constrained interface |
| Printed part has holes, zero-thickness areas, or fragile walls | Geometry route ignored process limits | Preserve the visual source; repair wall/gap/normal/manifold issues under the print profile |
| Reported dimensions differ after modifiers/export | Measurement was taken from source or unapplied transform | Measure evaluated saved geometry and record modifier/export policy |
| “Exact” result is based only on a photograph | Source does not determine scale or hidden dimensions | Mark inferred values and lower the claim to approximate/uncertain |

## Acceptance

Pass only the checks required by the declared profile. Include a measurement report, assumptions, tolerance/clearance policy, and the artifact version. Keep `NOT_TESTED` visible when a print process, native CAD solver, target mechanism, or exported file was not actually checked. Pair precision gates with multi-view visual review: exact dimensions cannot rescue a wrong silhouette or unreadable design.

Primary references: [Blender precision controls](https://docs.blender.org/manual/en/latest/scene_layout/object/editing/transform/control/precision.html), [Blender units](https://docs.blender.org/manual/en/latest/scene_layout/scene/properties.html#units), [Blender Mesh API](https://docs.blender.org/api/5.2/bpy.types.Mesh.html), and [Khronos glTF Asset Auditor](https://github.com/KhronosGroup/gltf-asset-auditor).
