# Blender animation data contract

This reference defines what an autonomous animation agent must inspect and
what it may claim after running the animation helper. The user supplies the
creative intent and judges the result visually. The agent owns frame ranges,
Action wiring, constraints, rig checks, preview review, recovery, and delivery.

The implementation uses Blender background processes and Blender's data and
evaluated-depsgraph APIs. It does not depend on a persistent console, a UI
selection, or an interactive connector. A connector can be used by a higher
level controller, but it is not a prerequisite for this route.

## Source animation and evaluated motion are different evidence

The [Blender 5.2 animation introduction](https://docs.blender.org/manual/en/5.2/animation/introduction.html)
describes animation across object properties, vertices, armatures, constraints,
drivers, modifiers, and shape keys. The helper keeps two records separate:

- `inspect` reports source Actions, Action Slots, layers, NLA tracks and strips,
  F-curves, pose markers, constraints, rig rest bones, and source transforms.
- `sample` evaluates the loaded file at requested frames, after setting the
  scene through integer frame plus subframe. It reports evaluated object world
  matrices, dimensions, armature pose-bone world matrices, local quaternion
  values, and root trajectories.

An Action existing in `bpy.data.actions` is not proof that an object is using
the intended slot, NLA strip, or constraint result. Blender 4.4 and later use
layered Actions and Action Slots; the [5.2 Action API](https://docs.blender.org/api/5.2/bpy.types.Action.html)
and [Action Slot API](https://docs.blender.org/api/5.2/bpy.types.ActionSlot.html)
expose those relationships. Feature detection must be performed on an Action
instance. A class-level `hasattr(Action, "slots")` check is not a valid
capability probe.

The helper therefore records both `frame_range` and `fcurves` for each Action.
F-curves include data paths, array indices, unrounded ranges, key counts,
sampled-point counts, validity, interpolation, and a bounded list of key
points. In Blender 5.2, legacy `action.fcurves` is absent on a layered Action;
the implementation walks layer strips and channel bags instead. Older files
can still expose legacy curves, so both paths remain supported.

NLA must be inspected alongside the active Action. The [NLA introduction](https://docs.blender.org/manual/en/5.0/editors/nla/introduction.html)
describes reusable Actions, strips, track precedence, blending, and Action
Tracks. A muted track, a strip outside its current range, an unassigned slot,
or a lower-priority strip can make an apparently valid Action invisible.

## Frame and root-motion semantics

Blender 5.2's `Scene.frame_set()` expects an integer frame plus an optional
subframe. The helper accepts finite float ranges and preserves them in JSON by
using `floor(frame)` plus `frame - floor(frame)`. It does not round Action
ranges or requested sample frames. Each sample includes both the requested
frame and the frame Blender reports after evaluation.

For an armature, the helper reports:

- rest-bone name, parent, local head/tail, length, deform flag, and rest matrix;
- pose-bone local location, scale, rotation mode, and quaternion;
- evaluated pose-bone world matrix and world translation;
- root-bone names and their sampled trajectories.

It also records top-level object roots, including cameras, lights, meshes,
empties, and armatures. This is a diagnostic inventory, not a claim that every
top-level object is intended to move.

`temporal_summary` reports displacement, speed, finite-difference acceleration
and jerk, first-to-last distance, and a heuristic loop candidate. The primary
`max_speed`, `max_acceleration`, and `max_jerk` fields are per-frame scene-unit
metrics using observed frame intervals; when FPS is available, explicit
per-second counterparts and the frame duration are included. These values are
evidence for review, never universal quality gates. A stationary camera or
ground object may legitimately have zero motion; a moving prop may legitimately
have a nonzero result. The helper never replaces an observed value with zero to
make a result look stable. Abrupt-change flags are relative to the sampled
trajectory and depend on the requested step.

There is no universal core-Blender retargeting or root-motion contract. The
[skinning documentation](https://docs.blender.org/manual/en/5.2/animation/armatures/skinning/introduction.html)
points retargeting toward add-ons and importers. A skill must choose a root
object or root bone explicitly, record whether translation lives in that root
Action or in world space, and round-trip the chosen export profile before
claiming compatibility.

Contact detection is intentionally not inferred from movement alone. Use
timeline markers, a declared contact contract, or a target-specific evaluator.
The sample report states `contact_detection` as not inferred when none exists.
Inspect foot or wheel contact at full temporal resolution where contact matters;
coarse samples can hide sliding or a one-frame teleport.

## Constraints, IK, cameras, and native editability

The [constraints introduction](https://docs.blender.org/manual/en/5.2/animation/constraints/introduction.html)
documents ordered constraint stacks, animated influence, and the difference
between a base transform and the evaluated visual transform. The helper reports
object and pose-bone constraints, targets, subtargets, influence, and mute
state. A visual transform can look right while the base transform is unchanged;
the evaluated world record is therefore the evidence used for temporal review.

IK needs a stable target, pole target where appropriate, chain length, rest pose,
and scale. For export, baking the evaluated result converts the constraint
effect into keys; it does not preserve the constraint graph. Preserve the
source rig and make a separate export branch. The official
[NLA bake API](https://docs.blender.org/api/5.0/bpy.ops.nla.html) exposes
visual keying and constraint-clearing options; the helper uses visual keying on
the isolated branch and records whether the bake succeeded.

Camera review must include camera identity, framing, lens, clipping, focus,
depth of field, path orientation, and frame-to-frame subject coverage. A
Follow Path setup can change with curve scale and axis choices. A Camera Solver
can intentionally be converted from a constraint into F-curves; this is a
native-to-baked transition and must be recorded as such.

The editable source is the `.blend` containing Actions, slots, NLA, F-curves,
constraints, rigs, shape keys, node graphs, and simulation settings. A GLB or
FBX is an interchange artifact. The helper copies no source file over the
input, saves a fresh branch, bakes that branch, exports, and imports the target
in a new Blender process for a readback receipt. It explicitly sets
`target_native_editability_claim: false`.

Export scope is explicit. `asset` selects non-review asset objects and any
review parent required by an asset transform, and reports omitted static review
cameras/lights/speakers. It refuses to omit an animated or constrained review
object. `scene` includes all scene objects and therefore remains subject to the
target importer/version's review-light and camera support. The branch resolves
source-relative paths before save, reopens the saved branch, and checks images,
linked libraries, cache files, and exposed simulation cache state again. Strict
dependency completeness blocks export when a required path or cache is missing;
an explicit optional bypass is visible in the receipt and cannot be read as a
complete delivery. `portable_delivery_complete` is a separate claim: any
external image, linked library, cache, point cache, or Geometry Nodes simulation
keeps it false/`NOT_TESTED_EXTERNAL_DEPENDENCIES` until an isolated bundle check
proves the dependency is embedded or shipped. Absolute path resolution proves
the staged branch can reopen in the current environment, not that a recipient
without the author's asset directories can open it. Source `.blend` packaging
remains the orchestrator's responsibility.

## Simulation and cache evidence

The [physics baking manual](https://docs.blender.org/manual/en/5.2/physics/baking.html)
states that playback caches may be in memory, while disk baking requires a
saved blend and a sibling cache directory. The helper reports point-cache
fields where Blender exposes them and marks actual Geometry Nodes Simulation
Input/Output nodes, including nested groups, as requiring a runtime probe. A
plain Geometry Nodes modifier whose group contains no simulation nodes is
inventoried without automatically becoming an unknown cache failure; an
unavailable node group remains a probe requirement. It also checks known
external cache-file paths.

`missing_assets` and `simulation_caches` are separate from geometry and motion
results. A `.blend` that opens but lacks a required simulation cache is not a
complete verified simulation delivery. Preserve the editable node or physics
setup in the source branch and report any cache dependency explicitly.

## Export limits

The [glTF 2.0 exporter documentation](https://docs.blender.org/manual/en/latest/addons/import_export/scene_gltf2.html)
describes Action, Active Action, NLA, and Scene export modes. Actions must be
associated with the chosen mode; glTF supports common object transforms, pose
bones, shape keys, and skinning, but does not carry Blender constraints,
drivers, or physics semantics as native Blender data. Driver-controlled values
may need sampling.

The [FBX exporter documentation](https://docs.blender.org/manual/en/5.0/addons/import_export/scene_fbx.html)
describes sampled/baked animation, bone-axis conversion, Action/AnimStack
differences, and the distinction between current, all, and NLA actions. FBX
constraints are represented by their evaluated keyframe result. Importing an
export back into Blender is evidence about that particular file and version,
not proof of general target compatibility.

The helper's export receipt must therefore be read as:

1. source input hash and missing-asset state;
2. fresh saved branch path and bake status;
3. target file existence, size, and hash;
4. fresh-process readback status, imported object/action inventory, and
   time-varying transform/pose evidence;
5. dependency completeness and any explicit optional bypass;
6. explicit target limitations.

Do not report `VERIFIED` for an export when readback failed, when the branch
bake failed, when required caches/assets are missing, when a requested animated
object is static after readback, or when the animation expectation is empty
without an explicit static-export decision. A successful exporter operator call
alone is insufficient.
