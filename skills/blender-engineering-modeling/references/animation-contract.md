# Animation-ready geometry and rig/export handoff

Read this reference when a modeled asset must support later rigging, deformation, retargeting, or a 3D runtime export. It defines the modeling handoff only: full motion authoring, native state machines, and temporal performance belong to a target-specific animation workflow.

## Handoff contract

Record these fields before changing topology or preparing an export:

```text
asset_id
target_profile and intended 3D runtime/export
coordinate system, units, scale, and up axis
rest pose and primary/fallback root or pivot
semantic part and bone map, including names that must survive export
deformation requirements and test poses
mesh, material, UV, and source/generated provenance
declared motion slots or clip names, if the brief already supplies them
export format, modifier/bake policy, and readback checks
native-runtime acceptance status
```

Do not infer rig readiness from a beauty render, a dense mesh, or an automatic quad remesh. Preserve a source checkpoint before retopology, destructive remesh, weighting, modifier application, or export preparation.

## Geometry and rig decisions

- Keep topology around joints, face landmarks, hands, feet, and silhouette transitions appropriate to the requested deformation. Quads are useful where they support deformation or SubD; deliberate triangles/ngons can remain elsewhere when the use permits them.
- Freeze units, axes, rest pose, object origins, and root/pivot policy before creating constraints or export data. Record whether displacement is intended to be authored in the asset or applied by the host runtime.
- Test the required neutral, extreme, contact, and silhouette poses on evaluated geometry. Record the pose names, affected parts, visible failures, and whether the repair changed topology, weights, shape keys, or the rig.
- Keep semantic part/bone names stable. Preserve the high-detail/generated source and the animation-ready version as related artifacts so later baking or rework remains possible.
- Treat UV/material, modifier, and export settings as handoff data. A successful exporter call proves transport output only; it does not prove retargeting, runtime graph setup, events, root-motion extraction, or performance.

## Export boundary

For GLB/glTF or FBX, record format, axis/unit conversion, applied modifiers, skin/shape-key policy, animation-channel policy, source hash, output hash, and readback result. GLB/FBX can carry geometry, skinning, transforms, and some channels, but native controller graphs, state-machine transitions, project input, event routing, and runtime performance remain target-side concerns. Mark them `NOT_TESTED` unless the target application was actually exercised.

## Acceptance

The modeling handoff passes when the saved asset reopens, named parts and bones are present, rest pose and axes are explicit, required deformation poses have been inspected, evaluated geometry meets the declared use profile, and the requested export has a retained receipt. Report `PASS`, `FAIL`, `UNCERTAIN`, `NOT_APPLICABLE`, or `NOT_TESTED` per check. Do not call the artifact animation-complete when this skill only established animation-ready geometry and rig/export evidence.

Primary references: [Blender armatures](https://docs.blender.org/manual/en/latest/animation/armatures/introduction.html), [Blender Actions](https://docs.blender.org/manual/en/latest/animation/actions.html), [Blender Studio retopology notes](https://studio.blender.org/blog/live-retopology-at-bcon22/), [Khronos glTF animation](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#animations), and [Blender glTF export](https://docs.blender.org/manual/en/latest/addons/import_export/scene_gltf2.html).
