# Animation CLI operations and review protocol

The executable is `scripts/blender_animation.py`. It uses only Python's
standard library outside Blender. Select Blender in this order:

1. `--blender /absolute/path/to/Blender`;
2. `BLENDER_BIN`;
3. common application and `PATH` locations, including the macOS application
   executable.

Every Blender job runs in background mode with stdin detached, a new process
group, an explicit timeout, and a JSON protocol file. On timeout the helper
terminates only its owned process group. It never kills a Blender process that
the user opened separately. A worker failure, timeout, missing protocol record,
or nonzero export readback remains visible in the receipt.

The global `--pretty` flag comes before the subcommand. All paths are resolved
to absolute paths in the receipt. Examples use the local skill root as
`<skill-root>`; an installed copy must substitute its actual location.

## Commands

Probe the executable and the actual Blender Python API. The probe creates a
temporary Action instance and checks `slots`, `layers`, and legacy `fcurves` on
that instance; it does not use a class-level RNA check.

```sh
python3 <skill-root>/scripts/blender_animation.py --pretty probe \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --out /tmp/animation-probe.json
```

Inspect source animation and current evaluated structure without changing the
input file:

```sh
python3 <skill-root>/scripts/blender_animation.py --pretty inspect \
  --blend /absolute/input.blend \
  --out /tmp/animation-inspect.json
```

`inspect` includes the loaded filepath, source and evaluated scene summaries,
FPS as a float (`fps / fps_base`), unrounded scene and Action ranges, timeline
markers, object and armature state, Action Slots, layered channel bags,
F-curves, NLA strips, constraints, missing image/cache paths, and simulation
cache state. The report is source animation evidence; it is not a visual review.

Sample evaluated motion without mutating the saved file:

```sh
python3 <skill-root>/scripts/blender_animation.py --pretty sample \
  --blend /absolute/input.blend \
  --start 1 --end 120 --step 1 --max-frames 240 \
  --out /tmp/animation-sample.json
```

Use a fractional step when a contact or interpolation issue may fall between
integer frames:

```sh
python3 <skill-root>/scripts/blender_animation.py sample \
  --blend /absolute/input.blend --start 12.0 --end 14.0 --step 0.25 \
  --out /tmp/animation-contact-sample.json
```

`sample` separates `source_animation` from `evaluated_samples`. Each evaluated
sample contains world transforms and dimensions for scene objects, evaluated
pose-bone state for armatures, root trajectories, and the actual frame after
setting. It restores the original scene frame and records `frame_preserved`.
The `temporal_summary` reports motion, approximate speed, acceleration, jerk,
first/last closure distance, and a loop candidate. `max_speed`,
`max_acceleration`, and `max_jerk` use scene units per frame, per frame squared,
and per frame cubed, with the actual observed frame intervals (including an
irregular endpoint). When the scene FPS is known, the receipt also reports
`max_*_per_second` fields and the source frame duration. Those are diagnostics,
not blanket zero-motion or aesthetic pass rules. A loop candidate means only
that the sampled first and last root translations are close; inspect rotation,
intermediate frames, Action cyclic intent, and the actual use case before
calling it a loop.

Render a temporally indexed PNG sequence:

```sh
python3 <skill-root>/scripts/blender_animation.py --pretty preview \
  --blend /absolute/input.blend \
  --out-dir /tmp/animation-frames \
  --out /tmp/animation-preview.json \
  --start 1 --end 120 --step 1 \
  --resolution 640x360 --samples 32
```

The helper records requested and applied resolution, engine, file format,
sample setting when the engine exposes one, per-frame render time, actual PNG
dimensions, file size, and SHA-256. It restores the source scene's frame,
filepath, and resolution settings after rendering. A PNG sequence is evidence
of rendered frames, not a video review.

When `ffmpeg` is already installed, request a source-timed full-speed and/or
slow-motion review artifact:

```sh
python3 <skill-root>/scripts/blender_animation.py preview \
  --blend /absolute/input.blend --out-dir /tmp/animation-frames \
  --start 1 --end 120 --step 1 --resolution 640x360 \
  --video /tmp/animation-fullspeed.mp4 \
  --slow-video /tmp/animation-slow.mp4 \
  --ffmpeg /opt/homebrew/bin/ffmpeg \
  --ffprobe /opt/homebrew/bin/ffprobe \
  --out /tmp/animation-preview.json
```

When `--video-fps` is omitted, the helper derives the nominal full-speed rate
from `scene_fps / sample_step`. It includes the requested end frame even when
the step does not divide the range, records every frame hold, and encodes a
timed sequence so an uneven final interval cannot silently change the motion
rate. The manifest records `source_fps`, `effective_fps`, per-frame durations,
`source_duration_seconds`, and an ffprobe duration when ffprobe is available.
The slow artifact doubles those encoded holds and must be about twice the
full-speed duration. Passing `--video-fps` is an explicit `retimed_override`;
the receipt sets `full_speed_label` to false because that output no longer
preserves source timing. A produced file is still not evidence that anyone
watched it. The parent agent must open the actual video in an available
media/browser or visual-review tool and inspect it; reading the JSON, listing
the PNGs, or generating a contact sheet is not a watched-motion record.

Export only after the source file has passed inspection and temporal review:

```sh
python3 <skill-root>/scripts/blender_animation.py export \
  --blend /absolute/input.blend \
  --format glb --out /absolute/delivery/model.glb \
  --scope asset \
  --receipt /absolute/delivery/model-export.json

python3 <skill-root>/scripts/blender_animation.py export \
  --blend /absolute/input.blend \
  --format fbx --scope asset --out /absolute/delivery/model.fbx \
  --receipt /absolute/delivery/model-fbx-export.json
```

`export` opens the source in an owned Blender process, resolves source-relative
external paths before saving a separate branch, bakes one animated owner at a
time (armature pose and mesh/object owners are not baked together), saves and
reopens that branch, exports the requested target, and starts a fresh Blender
process to import the target. The source hash is checked again. `asset` scope
selects non-review asset objects and required parents, and records omitted
static cameras/lights. If an animated or constrained camera/light/speaker
would be omitted, the command refuses that scope rather than silently dropping
the user's object; use `--scope scene` or a target-specific route. The receipt
distinguishes source-file preservation, dependency completeness, path staging,
branch bake status, target existence, temporal readback, missing assets, and
simulation cache state. Strict dependency completeness is the default;
`--allow-missing-optional` is an explicit caller declaration and produces
`VERIFIED_WITH_OPTIONAL_MISSING` with `complete_delivery: false`. It always sets
`target_native_editability_claim` to `false` because glTF and FBX are
interchange artifacts. A static export requires `--allow-static` and is
reported as `STATIC_READBACK_ALLOWED`; otherwise an empty animation expectation
is a distinct `STATIC_READBACK` failure. `verification_status` is `VERIFIED`
only when the branch, target, dependencies, expected motion, and fresh temporal
readback all pass. `complete_delivery` is a separate portability claim. When
the branch contains an external image, linked library, cache, point cache, or
Geometry Nodes simulation, the receipt reports
`portable_delivery_complete: false` and
`portable_delivery.status: NOT_TESTED_EXTERNAL_DEPENDENCIES` unless a separate
isolated bundle check has proven those dependencies are embedded or shipped.
Absolute path resolution and a successful interchange readback do not prove a
portable recipient bundle; packaging the source `.blend` and its dependencies
remains the orchestrator's responsibility. `--keep-branch` retains the
temporary branch for audit; otherwise it is removed only after readback.

## How the agent must actually review motion

Use the following order for every requested animation. Do not promote a model
from a contact sheet alone.

1. **Source inventory.** Read `inspect` first. Identify the Action, slot and
   target datablock, F-curves and ranges, NLA strips, constraint stack, root
   bone/object, markers, FPS, and cache status. If a rig is expected, verify
   rest-bone hierarchy, deform flags, and an actual pose channel.

2. **Evaluated temporal sample.** Run `sample` across the complete requested
   range. Use step `1` for ordinary contact or foot work. Use a fractional step
   for interpolation, subframe motion, or a suspected one-frame pop. Check
   evaluated world state, not only local controls. Compare root translation and
   quaternion orientation, armature pose, object dimensions, and camera state.

3. **Full-speed review.** Create a source-timed full-speed video. With a
   sampled step, this means the scene FPS divided by the step; the receipt must
   show preserved timestamps and a true `full_speed_label`. Watch the entire
   motion from first to last frame at normal speed. This reveals timing,
   weight, rhythm, anticipation, overshoot, and whether a loop visibly cuts.
   The JSON `max_speed` or `loop_candidate` is not a substitute for watching.

4. **Slow-motion review.** Watch the slow-motion output or step through the
   ordered PNG sequence at roughly half speed. Inspect the frames around
   contacts, direction changes, parent or IK switches, extrema, and any sample
   index in `abrupt_change_sample_indices`. Look for foot or wheel sliding,
   root jumps, quaternion flips, constraint popping, mesh intersections,
   one-frame disappearances, and camera focus/framing changes.

5. **Contact and loop review.** A timeline marker is a review cue, not proof of
   contact. For a declared contact contract, inspect the exact frame and its
   neighbors. For a loop, compare first and last world translation *and*
   orientation, then inspect the transition at the join. A stationary object is
   allowed to be stationary; do not fail it because its diagnostic speed is
   zero. Conversely, do not pass a moving root because a coarse sample happened
   to start and end near the same position.

6. **Export review.** After source approval, inspect the export receipt. A
   successful operator call with a failed branch bake or failed fresh-process
   readback is partial evidence. Reimported Actions or baked keys demonstrate
   what survived this export/version combination, not that Blender constraints,
   Action Slots, drivers, or simulation logic remain editable in the target.

The final user-facing handoff should expose the preview and the `.blend` first,
then the export receipt and known limitations. The user should be able to judge
the animation visually without reading the internal JSON, while the JSON keeps
the technical evidence auditable.

## Tested coverage and known limits

The implementation was smoke-tested on local Blender **5.2.0 LTS**, build
`fbe6228777e7`, using a small keyed cube and two-bone armature fixture in `/tmp`.
The following paths completed successfully:

- API probe, including actual Action instance slot/layer detection;
- inspect with layered Action channel bags, F-curves, markers, rig rest/pose
  state, NLA fields, and missing-cache report;
- integer and fractional evaluated sampling with frame restoration;
- PNG preview with resolution and PNG dimension readback;
- source-timed and two-times-duration ffmpeg videos from a sampled sequence,
  including a 30 FPS, step-2 duration regression checked with ffprobe and an
  irregular endpoint case;
- GLB and FBX export from a proper animated mesh-plus-armature fixture through a
  separate baked branch and fresh-process temporal readback. Both formats
  retained time-varying rig state, and the GLB mesh deformation was evidenced
  through the imported varying mesh child when the importer materialized a
  proxy Empty.

An earlier scene-scope FBX attempt on the review fixture produced an artifact,
but fresh-process FBX readback failed in this Blender 5.2 installation because
the importer reached `CyclesLightSettings.cast_shadow` on a light. The scoped
asset route excludes those static review lights/cameras and passed on the
proper animated fixture; the historical scene-scope failure remains a real
version-specific limitation, not a hidden pass. Animated review lights or
cameras are refused by `asset` scope and must be handled through an explicitly
documented route.

A source-relative texture fixture was also exported after path resolution and
fresh branch reopen; its dependency receipt retained the valid texture. A
missing texture blocked strict export and only proceeded under the explicit
`--allow-missing-optional` policy, which remained visibly incomplete.

Geometry Nodes modifiers are inspected recursively for actual Simulation
Input/Output nodes. A simple non-simulation node group is reported as present
without automatically blocking dependency completeness; simulation nodes or an
unavailable node group remain runtime-probe/cache requirements. External
dependencies still keep `portable_delivery_complete` false until a separate
isolated bundle check proves they were embedded or shipped.

No GUI connector route, Windows/Linux executable, production character rig,
Geometry Nodes simulation bake, physics cache delivery, retargeting add-on, or
large-scene performance profile has been validated by this helper. Those cases
must remain `NOT_TESTED` until a real fixture and a real receipt cover them.
