---
name: blender-engineering-modeling
description: "Create, inspect, repair, and deliver finished 3D models, scenes, materials, and animation-ready geometry from one novice-language brief, choosing the modeling route from form, style, use, and available runtime."
license: MIT
metadata:
  author: iamducnhat
  version: "0.1.0"
---

# Blender Engineering Modeling

Use this skill when the user wants an agent to turn an ordinary description or reference into a finished, inspectable 3D model, scene, material handoff, animation-ready mesh/rig, or requested 3D export. The user supplies intent and judges the final taste. The agent owns interpretation, route selection, Blender/tool operation, structural checks, visual review, repair, save/reopen, and delivery.

## First action on every job or resume

Before choosing a tool, modifier, backend, or edit, reread this entrypoint, [`references/research-playbook.md`](references/research-playbook.md), and the recipe that matches the current task. If the model must be animation-ready or exported with a rig, also read [`references/animation-contract.md`](references/animation-contract.md). If a previous artifact, receipt, checkpoint, or failure exists, inspect the current evidence before resuming. Do not implement from remembered context alone. On a fresh job, record that there is no prior run evidence.

## User contract

Treat one prompt as one user-facing request with an autonomous internal workflow. Do not make the user choose topology, modifiers, node graphs, providers, cameras, polygon counts, or repair commands. Do not stop for blockout approval. A blockout is an internal planning stage; when the request is for a finished model, continue through detail, material, presentation, and the requested use checks.

When the brief is incomplete, infer a coherent design from the words and references, record assumptions that affect shape or use, and proceed. Ask only when a missing fact makes the requested output impossible or unsafe to interpret. A final user taste judgment is allowed after delivery; it is not a substitute for technical QA and it is not required before the first complete result.

## Representation and route policy

Choose the representation before implementation. Use Blender as the 3D authoring environment when a 3D scene, editable mesh, rig, material, render, or Blender file is requested. When a model must support later animation, keep the handoff explicit: rest pose, bone/part map, root or pivot policy, deformation checks, units/axes, and export target. Read the animation contract before preparing that handoff; this skill does not treat a mesh or export as completed motion.

Detect available capabilities and choose among procedural/parametric construction, authored or imported assets, generated mesh, and a hybrid. A provider prompt, a successful script, or a pretty image is not a finished deliverable. Keep provenance for imported/generated content and preserve a fallback route when the primary route cannot meet the requested use.

Read [`references/routing.md`](references/routing.md) first for classification. Then load only the relevant recipe:

- rotational or profile-driven form: [`references/revolve.md`](references/revolve.md)
- hard-surface product, panels, furniture, or mechanical prop: [`references/hard-surface.md`](references/hard-surface.md)
- organic, character, creature, or likeness: [`references/organic.md`](references/organic.md)
- scene, kit, repeated assembly, or procedural environment: [`references/scenes.md`](references/scenes.md)
- measured, print, fit, or CAD-like requirement: [`references/precision.md`](references/precision.md)
- UV, material, lighting, and render handoff: [`references/materials.md`](references/materials.md)
- structural/visual QA, checkpoint repair, or delivery recovery: [`references/qa-recovery.md`](references/qa-recovery.md)

## Internal execution contract

Create a small task contract before geometry. Preserve the original request, explicit criteria, observed reference facts, use profile, style grammar, assumptions, route, target, checks, deliverables, and resource limits. Label each criterion as user-explicit, reference-observed, use-required, or agent-assumed. Do not silently lower or delete a required criterion after a failure.

For real-world props, choose a plausible approximate physical size before construction and keep scene units, geometry dimensions and export scale consistent. Label inferred dimensions as assumptions. A product preview does not justify accidentally delivering a hand-held object several meters tall. Deliberate miniature, giant or abstract scale follows the brief.

Build in stages, but keep the stages internal:

1. Translate the brief into visible identity, part/scene relationships, proportions, camera/use, and style hierarchy.
2. Create the cheapest useful representation and inspect silhouette, composition, and primary shape. Promote only when it earns the next stage.
3. Build secondary forms and camera-critical detail with the selected recipe. Preserve source parts, parameters, and generated/asset provenance.
4. Add materials, UVs, lighting, rigging, animation-ready geometry, or export data only when the use profile needs them. Do not treat a render-only mesh as rig-ready, print-ready, or game-ready without the corresponding checks.
5. Render clean multi-side evidence and targeted diagnostic views. Run structural checks on evaluated data, not just object names or script output.
6. Repair one diagnosed scope at a time from a checkpoint. Keep criteria already passing protected, rerun affected and downstream checks, and restore when the candidate regresses or the defect is not improved.
7. Save the accepted artifact, open it in a fresh process when possible, rerun the required checks, and deliver the file, previews, provenance/source, and receipt.

Complexity must serve silhouette, shape hierarchy, readability, deformation, camera, and target performance. Do not apply an all-quads rule, a blanket closed-mesh rule, or a polygon count as a universal quality test. Use triangles/ngons, thin shells, curves, instances, modifiers, texture detail, or separate parts when they are appropriate for the role and use.

## Evidence and status

Keep observed facts, self-reports, design inferences, proposed behavior, and tested outcomes separate. Use `PASS`, `FAIL`, `UNCERTAIN`, `NOT_APPLICABLE`, and `NOT_TESTED` for checks. A valid file or export does not prove visual quality, native runtime playback, animation events, root motion, rigging, print fit, or low-end performance. A single hero render does not prove the back, underside, silhouette, or hidden connections.

Do not report `READY_FOR_REVIEW` when an applicable required check is `FAIL`, `UNCERTAIN`, or `NOT_TESTED`. `READY_FOR_REVIEW` means the technical gates and requested artifact evidence are complete; the user may still dislike the aesthetic result. If a required route cannot be completed, preserve the artifact and evidence and report `INCOMPLETE` or `BLOCKED` with the actual cause.

## Local helper boundary

The skill ships a narrow helper at [`scripts/blender_engineering.py`](scripts/blender_engineering.py). Run it from the installed skill directory (or use its absolute path); every command accepts `--blender PATH` and finite `--timeout SECONDS`.

```text
python3 scripts/blender_engineering.py probe [--out RECEIPT]
python3 scripts/blender_engineering.py inspect --blend SOURCE.blend --out RECEIPT
python3 scripts/blender_engineering.py render --blend SOURCE.blend --out-dir EVIDENCE_DIR [--views hero,front,side,back,top] [--resolution N] [--samples N] [--receipt RECEIPT] [--force]
python3 scripts/blender_engineering.py validate --blend SOURCE.blend --contract CONTRACT.json --out REPORT
python3 scripts/blender_engineering.py export --blend SOURCE.blend --format glb|fbx|stl --out ARTIFACT [--receipt RECEIPT] [--force]
```

`probe` records Blender/build and adapter capabilities. `inspect` opens a saved blend in a fresh background process and writes evaluated scene evidence. `render` creates neutral diagnostic views with a temporary camera and floor; use the source scene for the final artistic presentation. `validate` opens the source read-only in a fresh process, preserves its relative dependency context, and checks the source hash before and after. `export` writes the requested GLB, FBX, or STL and performs format/header and non-empty readback. Independently reimport requested exports for geometry or target verification; the modeling exporter alone does not do that. A zero exit code is not a visual-quality verdict; preserve each JSON receipt. If an installed copy is missing the helper, mark helper-dependent coverage `NOT_TESTED` rather than claiming it ran. See [`references/tools.md`](references/tools.md) for the complete lifecycle and receipt semantics.

Use [`assets/task-contract.example.json`](assets/task-contract.example.json) for the user requirements and evidence gate. Adapt its criteria and artifact paths to this job. Every explicitly requested deliverable, export, target and applicable native verification is required. The unfilled report starts at `NOT_TESTED`; never copy it as a completed verdict.

The geometry adapter takes a separate, lower-level schema: start from [`assets/geometry-contract.example.json`](assets/geometry-contract.example.json) and derive part IDs, counts, bounds, units, and applicable contact checks from this task. Pass that geometry contract to `blender_engineering.py validate`; pass the task contract to `evidence.py gate`. Record the adapter result as evidence for the corresponding task criteria. Neither schema translates prose into proof by itself.

After the helper checks, use [`scripts/evidence.py`](scripts/evidence.py) to inventory/hash evidence or run the fail-closed delivery gate:

```text
python3 scripts/evidence.py inventory evidence deliverable
python3 scripts/evidence.py gate --contract CONTRACT.json --report DELIVERY_REPORT.json --out DELIVERY_GATE.json
```

The gate proves file/report structure only; it does not prove visual quality, actual image reading, native playback, or user taste. Use [`assets/delivery-report.example.json`](assets/delivery-report.example.json) as the report shape and keep unsupported or unrun checks explicit.

## Delivery

Deliver the requested finished artifact and clear previews first. Include a concise receipt with runtime/version, route, assumptions, artifact paths or identifiers, checks performed, source/dependency provenance, accepted checkpoint, and unresolved limitations. Use the [`delivery-report.example.json`](assets/delivery-report.example.json) shape when a structured report is useful. Keep diagnostic overlays out of the final beauty evidence. For a rig or 3D export handoff, include the target-specific acceptance result and distinguish transport validity from later native playback verification.
