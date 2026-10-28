---
name: blender-engineering-animation
description: "Create, edit, retarget, integrate, and optimize animation for the intended platform. Use for Blender motion, Roblox and game-engine clips, character or object performances, sprites, skeletal 2D, vector and interactive animation, loops, transitions, and motion diagnostics."
license: MIT
metadata:
  author: iamducnhat
  version: "0.1.0"
---

# Blender Engineering Animation

Create a finished, editable animation from a plain-language request. The user
provides intent and judges the final aesthetics. Own technical interpretation,
asset preparation, authoring, inspection, repair, optimization, and delivery.
One request may require many internal tool calls. Preserve the requested scope.

## Start by reading again

At the beginning of every new task, read this entrypoint and
[research-playbook.md](references/research-playbook.md). Then read the craft,
quality, representation, and platform references relevant to the current job.
When resuming after a context gap, reread those references and the current task
contract, accepted checkpoint, and defect ledger before editing. Do not work
from a remembered OSINT summary alone. Record which files and versions informed
the route; a file hash records identity, not proof of comprehension.

Read project instructions and inspect the actual asset, rig, timeline and target
runtime. Do not infer capability from an app icon or a file extension. Prefer a
configured native tool/MCP when it supports the operation; use a background DCC
or another capable route when it does not.

## Load the appropriate references

| Need | Read |
|---|---|
| Pose, acting, timing, contact, mechanics, camera | [motion-craft.md](references/motion-craft.md) |
| Temporal evidence, critique, repair, completion | [quality-and-delivery.md](references/quality-and-delivery.md) |
| Blender authoring, Actions/slots, rigging, bake/export | [blender.md](references/blender.md), [blender-tools.md](references/blender-tools.md) |
| Roblox authoring, rig families, local versus cloud use | [roblox.md](references/roblox.md) |
| Unity, Unreal, Godot, Three.js or web integration | [engines.md](references/engines.md) |
| Frame animation, pixel art, sheets and timing | [sprites.md](references/sprites.md) |
| Spine/DragonBones-style bones, attachments and atlases | [skeletal-2d.md](references/skeletal-2d.md) |
| Rive/RML, Lottie, SVG, Grease Pencil, interactive vector | [vector.md](references/vector.md) |
| Existing clips, motion models, provenance and terms | [motion-sources.md](references/motion-sources.md) |

Load only what the job uses. For an unlisted platform, inspect its current
official authoring/runtime documentation and the target project, then build an
appropriate native route with the same evidence requirements. A generic export
alone does not establish compatibility.

## Interpret the request internally

Create a compact motion brief: subject/actors, action and emotional beats,
style, duration or exposure timing, loop/one-shot behavior, contact surfaces,
root/pivot intent, camera, events, target, and required files. Preserve the user's
actual wording and distinguish explicit requirements from assumptions. Use
[task-contract.example.json](assets/task-contract.example.json) when a structured
run record is useful; the agent fills it, not the user.

Adapt the template to the actual representation and request. Every explicit
deliverable, named target and requested integration is required, including
native playback when the requested result depends on it. An unavailable target
leaves target delivery incomplete; it cannot become an optional criterion.
The example report starts at `NOT_TESTED` and must remain incomplete until real
checks and observations replace it.

Infer missing technical choices from the project and request. Choose coherent,
reversible defaults when needed; do not stop for blockout approval, bone mapping,
solver choices, keyframe placement or tool debugging. Do not require the user to
supply additional views or perform manual cleanup to complete the first result.
If the subject is missing, create or obtain the appropriate editable asset using
available authoring tools. A sibling skill may help when installed but is never
a runtime dependency of this skill.

Keep representation and target separate. Shared timing uses seconds; preserve
source FPS, per-frame durations, native curves, rest pose, units and axes. Root
intent distinguishes in-place, authored displacement and runtime-extracted
movement. Sprite pivots and vector paths are not skeletal bone channels.
For real-world 3D subjects, choose a plausible approximate physical scale and
keep geometry, unit settings, motion distances and export scale consistent.
Label inferred sizes as assumptions; a toy-sized appearance in the preview is
not evidence of a small native asset.

Freeze the requirement contract before production. Keep amendments and their
reasons; never drop a failed user requirement to improve the score. Establish a
finite run budget from the existing task policy, including operation deadlines
and generation costs when applicable. Tool defaults are operational limits,
not evidence of expected animation quality.

## Choose and execute a capable route

Use the best-fitting combination of permitted retrieved motion, original
keyframes, procedural curves, simulation, motion extraction or a configured
motion-generation backend. Prefer coherent, reusable motion when it fits; create
the missing or expressive parts when retrieval does not. Preserve source lineage
through retargeting, retiming, blending and cleanup. Do not assume a GPU, service
account, paid credits, commercial editor or redistribution right exists.

For 3D, prepare and stress-test the necessary rig or articulated parts, then
block readable poses and beats. For 2D, choose frame, cutout/skeletal, vector or
3D-to-sprite rendering according to the desired look and runtime. Keep native or
procedural editable source. An image-to-video result requires a separate editable
motion-extraction route if the user requested an animation asset.

Authoring is the agent's work. With Blender available, write and execute a
task-specific `bpy` script or use capable native tools to create the subject,
articulated hierarchy/rig, materials and motion; save that script with the native
source. The packaged CLI inspects, samples, renders and exports those sources;
it is not a text-to-animation generator. For sprites, author source frames and
timing before packing. For other native editors use their actual supported
authoring API or project format. If no capable authoring route exists, preserve
useful work and report the missing capability rather than treating a preview as
an editable animation.

Refine primary movement and contact, then timing/spacing and transitions, then
secondary motion and presentation. Keep effects and sound synchronized when
relevant; do not expand a narrow animation task into a mandatory VFX/audio project.
Integrate the target's existing controller or state machine rather than creating
a competing runtime system.

## Inspect, repair and optimize

Inspect actual evaluated motion across time: constraints, drivers, NLA/blends,
retargeting, compression and root extraction can change authored keys. Review
an ordered pose sheet, intended-speed playback, and targeted slow-motion
diagnostics. Actually view the resulting evidence. A frame sheet alone does not
establish rhythm, contact or transition quality.

Run role-aware structural checks and a fresh-context visual critique against
the contract. Record defects with object/joint, frame/time, evidence and proposed
repair scope. Preserve the accepted checkpoint, patch a diagnosed cause, then
recheck affected and previously passing requirements. Restore regressions.
Record same-model judgment as `SELF_EVAL_ONLY`; do not call it externally
independent acceptance. Use A/B order swaps when comparisons are close.

Apply contact, loop, collision and smoothness checks only when appropriate.
Skating, flight, squash/stretch, held drawings, mechanical steps and deliberate
snaps are valid styles. Do not enforce a universal jerk score, stationary root,
frame rate or planted-foot condition.

Optimize for the target and use: evaluated deformation, update frequency,
animation layers, curve reduction/baking, draw calls, atlas sampling, memory,
network ownership or lifecycle. Compare against the accepted motion after every
lossy operation. Measure real runtime behavior when claiming performance;
emulation and desktop previews are not mobile hardware evidence.

## Verify and deliver

Save source, reopen from the exact delivery path in a fresh process when the
format permits, render/play that saved result, and validate requested exports
through the receiving runtime when available. Keep native constraints and
procedural data in source; bake a separate export branch. Bundle required
textures, atlases, scripts and caches with portable paths and provenance.

Deliver the editable source and requested native/runtime package, an aesthetic
preview, a small pose sheet, and a concise receipt. Distinguish source, runtime
package, preview, local temporary IDs and published assets. A source `.blend`,
sprite sheet, GLB or valid JSON does not prove target playback.

Use [delivery-report.example.json](assets/delivery-report.example.json) and
`python3 scripts/evidence.py gate --contract CONTRACT.json --report REPORT.json
--out VERDICT.json` for a structural evidence gate. This helper does not watch
animation, prove aesthetic quality or replace native runtime tests.

- `READY_FOR_REVIEW`: required applicable criteria pass with actual evidence;
  the user still decides whether it fits their taste.
- `INCOMPLETE`: a required artifact, quality criterion or verification is missing.
- `BLOCKED`: a necessary capability remains unavailable after capable alternatives.

Required `FAIL`, `UNCERTAIN` and `NOT_TESTED` cannot become a completed-target
claim. Preserve the best artifact and explain the specific remaining limitation.
Optional aesthetic feedback after delivery starts a revision; it is not hidden
technical coaching required to finish the first run.
