# Skeletal 2D route

Skeletal animation is appropriate when actions share a rig, skins or
attachments are swapped, constraints must be evaluated at runtime, or a
character needs many poses. It is not a universal replacement for a
frame-by-frame sprite. A short one-shot request should choose a rig only when
the prompt or target requires reuse, blending, deformation, or interactive
state.

## Spine

[Spine’s JSON format](https://en.esotericsoftware.com/spine-json-format) defines
bones, slots, skins, attachments, draw order, animations, constraints, and
skeleton metadata. Its export documentation describes JSON/binary skeleton
data, atlas files, and PNG pages; the [runtime documentation](https://us.esotericsoftware.com/spine-runtimes)
loads those pieces together. The source project remains the editable master.

Deliver a Spine package as a versioned set:

```text
character.spine            editable project/source when available
character.json or .skel    runtime skeleton data
character.atlas            region and page metadata
character.png              atlas page(s)
```

The editor and runtime versions must match. JSON being readable does not prove
that a target runtime can load it, and a valid atlas does not prove attachment
order, UVs, mesh weights, IK, or draw order. The helper’s `check-spine`
command only checks supplied paths and records the declared version;
`editor_runtime_version_match` and `target_playback` remain `NOT_TESTED`.

Trimmed atlas meshes need special care. The original [Spine practitioner
report](https://esotericsoftware.com/forum/d/4973-patch-for-trimmed-atlas-meshes-in-c-sharpunity)
describes edge bleeding and the need for padding/tighter meshes plus correct
region and UV handling. Keep source bounds, offsets, padding, and extrusion in
the manifest. Do not rotate or tightly pack animation regions unless the
target importer is known to handle those flags.

## DragonBones

[DragonBones’ official animation documentation](https://dragonbones.github.io/en/animation.html)
describes armatures, bones, slots, skins, meshes/FFD, IK and constraints,
nested animation, and runtime skin/attachment changes. The newer
[LoongBones export documentation](https://loongbones.com/doc/en/editor/export-db-data)
distinguishes armature data, texture data, atlas images, JSON version, and
output scale. Keep the editable project and export the exact runtime package
for the chosen target; do not infer current editor support merely from a
runtime repository.

## Rive as an interactive skeletal/vector route

Rive combines vector/raster art, bones, meshes, constraints, timelines, and
state machines. The current [character-animation documentation](https://rive.app/use-cases/character-animation)
says `.riv` is loaded by a Rive runtime and that feature support varies by
runtime. Rive’s runtimes are documented as MIT open source with no runtime
fees; this does not make every editor feature portable to every runtime.

Use the following artifact labels:

```text
Rive workspace/project or RML folder  canonical editable source when available
.rev                                  current product label: backup export
.riv                                  runtime export
GIF/MP4/PNG/WebM                      rendered preview/delivery
```

The current [Rive pricing page](https://rive.app/pricing) lists `REV (for
backup)` and `RIV (for Runtimes)` separately. Do not claim that a `.rev` is
always a complete editable source or that a `.riv` can be round-tripped into
the editor. Preserve the workspace/project or RML source when available and
check a `.rev` recovery path for the specific editor version.

The current [Rive agents/CLI documentation](https://rive.app/agents) describes
RML as readable, writable, diffable plain text plus assets. It documents
offline build/preview/verification and says publishing/syncing with the Rive
Editor requires sign-in; runtimes refuse unsigned scripts. The CLI’s existence
does not mean that every platform supports every state-machine, script, mesh,
or shader feature. `scripts/sprite_pipeline.py check-rive` reports source,
runtime, backup, and path presence, but always leaves signed export and target
playback as `NOT_TESTED`.
