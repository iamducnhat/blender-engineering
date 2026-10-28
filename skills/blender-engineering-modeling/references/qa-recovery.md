# Structural QA, visual QA, checkpoints, and recovery

Use this reference for every finished artifact. It is the operational bridge between “the script ran” and “the requested result is ready.” Keep structural and visual evidence separate, and preserve negative results rather than converting an unknown check into a pass.

## Preflight and manifest

1. Reread the skill entrypoint, this file, the relevant recipe, animation contract when applicable, and the current receipt/checkpoint. Record runtime/version, target, route, inputs, and whether prior evidence exists.
2. Probe the available helper/runtime before issuing a large build. If the helper is unavailable, use the safest native route and mark helper-dependent coverage `NOT_TESTED`.
3. Write a contract/manifest containing original criteria, use profile, required parts and relations, camera/views, deliverables, dependencies, performance limits, and assumptions. Give every criterion a provenance label.
4. Save a named checkpoint after primary shape, after major secondary structure, and before risky operations such as boolean application, destructive remesh, realization, retopo, or export.

## Two independent evidence tracks

**Structural track.** Inspect evaluated object data, not only object names or generator output. Check finite transforms, object/part presence, dimensions, normals, degenerate/loose geometry, expected attachments, collisions/clearances, modifier/node state, material/UV presence, animation-ready rig/channel data when required, and target-specific export reports. Use role-specific thresholds from the contract; do not fail a render prop with a print-only rule.

When appropriate, synchronize object/edit data, call `Mesh.validate` on a copy or explicitly record any repair it makes, call `Mesh.update`, and rerun downstream checks. A validation function that changes the mesh is itself an evidence event. For GLB/glTF, retain the Khronos validator JSON and distinguish errors, warnings, and hints.

**Visual track.** Render a clean contact sheet with hero plus complementary front, side, back, top, and targeted close-up/underside views. Use clay and neutral-light passes as well as the final material pass when lighting could conceal a defect. Check silhouette, proportion, landmarks, shape hierarchy, part relations, support/contact, detail density, style, camera consistency, and hidden/alternate-view damage. The critic must cite visible evidence and must not receive a persuasive generation log or rubric baked into the image.

Do not trust one scalar aesthetic score. If comparing candidates, swap A/B order and repeat when practical; log disagreement and mark the result `UNCERTAIN`. A clean render cannot prove native playback, a correct rig, print fit, or low-end performance.

## Localized repair loop

1. Name one observed defect and its likely scope. Select the newest checkpoint that still satisfies already-passing criteria.
2. Make the smallest targeted repair. Record before/after measurements, affected parts, parameters, and provenance. Do not silently rewrite the contract to make the repair pass.
3. Rerun the affected structural checks, all downstream checks, and the relevant visual views. Keep the candidate only if the diagnosed defect improves without regressing protected criteria; otherwise restore the checkpoint.
4. Bound attempts and time. If repeated edits do not improve evidence, switch representation/route or report `INCOMPLETE` with the best artifact and actual limitation. Do not loop on a vague beauty prompt.

## Transport and state recovery

- Separate **transport/tool** failures (timeout, bridge, context, process) from **modeling** failures (wrong shape, modifier, topology) and **representation** failures (route cannot provide required rig/UV/precision/runtime semantics).
- On timeout or uncertain command state, query the scene, process, and last receipt before retrying. A duplicate build can destroy a valid checkpoint.
- Use a fresh process/namespace where possible for final verification. Save, close/reopen, inspect again, render again, and only then export. Do not claim a successful reopen if it was not attempted.
- Keep error text, last known state, checkpoint path, and retry decision in the receipt. Never hide a negative result behind a generic “recovered.”

## Shipped helper interface

The skill ships `scripts/blender_engineering.py`. Run it from the installed skill directory or by absolute path, and record the exact command and JSON receipt. Common options are `--blender PATH` and finite `--timeout SECONDS`.

```text
python3 scripts/blender_engineering.py probe [--out RECEIPT]
python3 scripts/blender_engineering.py inspect --blend PATH --out RECEIPT
python3 scripts/blender_engineering.py render --blend PATH --out-dir DIR [--views hero,front,side,back,top] [--resolution N] [--samples N] [--receipt RECEIPT] [--force]
python3 scripts/blender_engineering.py validate --blend PATH --contract CONTRACT --out REPORT
python3 scripts/blender_engineering.py export --blend PATH --format glb|fbx|stl --out PATH [--receipt RECEIPT] [--force]
```

`probe` reports runtime/build capability; `inspect` reads a saved blend in a fresh background process; `render` creates neutral diagnostic views; `validate` checks the source read-only with its original relative dependency context and before/after source hashes; and `export` performs format/header and non-empty readback. Independently import exports for geometry or receiving-runtime proof. See [`references/tools.md`](tools.md) for lifecycle, receipt fields, declared-check aggregation, and unsupported-check semantics. If the shipped helper is missing from an installed copy, mark its coverage `NOT_TESTED` rather than claiming a native operation ran.

After these checks, use [`scripts/evidence.py`](../scripts/evidence.py) with [`assets/task-contract.example.json`](../assets/task-contract.example.json) and [`assets/delivery-report.example.json`](../assets/delivery-report.example.json) to inventory/hash evidence or run the fail-closed structural delivery gate. The evidence gate proves file/report structure only, not visual quality or user taste.

## Final gate and receipt

Use `PASS`, `FAIL`, `UNCERTAIN`, `NOT_APPLICABLE`, and `NOT_TESTED`. `READY_FOR_REVIEW` requires every applicable required gate to be `PASS`; a user may still dislike the aesthetic result. Deliver the accepted `.blend` or target artifact, clean previews, provenance/source files where allowed, and a receipt containing runtime/version, route, assumptions, checkpoints, commands, structural results, visual-result limits, export/readback, dependency state, and unresolved risks.

Primary references: [BlenderWorld](https://arxiv.org/abs/2610.23986), [BlenderGym](https://arxiv.org/abs/2504.01786), [VIGA](https://arxiv.org/abs/2601.11109), [Blender Mesh API](https://docs.blender.org/api/5.2/bpy.types.Mesh.html), [Khronos glTF Validator](https://github.com/KhronosGroup/glTF-Validator), [Khronos glTF Asset Auditor](https://github.com/KhronosGroup/gltf-asset-auditor), and [MLLM-as-a-Judge](https://proceedings.mlr.press/v235/chen24h.html).
