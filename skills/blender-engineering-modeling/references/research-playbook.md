# Research playbook

This reference turns the research into operating decisions. It is not a catalog to recite. Load it at the start of every job and every resume, then load only the recipe and target reference that apply.

## Evidence labels

Keep these categories separate in the task contract and receipt:

- **Observed:** directly visible in a supplied reference, scene, file, render, tool response, or source implementation.
- **Self-reported:** a practitioner, repository, paper, or provider claims a behavior or result. Preserve the claim and its scope; do not promote it to a local test.
- **Inferred:** a reasonable design conclusion derived from observed or self-reported material. Write the reason and confidence.
- **Proposed:** a recipe, threshold, adapter, or policy this skill is choosing to implement.
- **Tested:** the current run actually executed the operation and inspected the resulting artifact/evidence.

An external source that says a mesh is generated, a connector can render, or a method improves a benchmark is not proof that the current machine can run it or that the resulting asset meets this user's brief. Keep `NOT_TESTED` visible.

## First read and current-state discipline

Before any operation, reread the skill entrypoint, this playbook, the relevant modeling recipe, and the current run evidence. On a resume, inspect the saved artifact, manifest, receipt, checkpoint and latest failure instead of trusting a conversational summary. If no artifact exists, record a fresh run. If the current evidence conflicts with the plan, update the plan from evidence and preserve the old contract/receipt.

Probe the available Blender/runtime/tool capabilities before promising a route. Record version, executable, bridge/helper status, render availability, export availability, and whether a target runtime has actually been exercised. A version probe is only a version probe. Do not turn it into a claim that scripts, rendering, generators, GPU, or native playback work.

## Translate one novice request into a contract

Build the contract silently from ordinary language. Ask only for a missing decision that cannot be inferred without risking the requested result. Capture:

```text
request and references
visible identity and must-have features
part/scene graph and support/attachment relationships
style grammar: proportions, shape hierarchy, color, material, detail rhythm
use profile: render, editable scene, animation-ready geometry/rig, 3D export, print, fit
target/runtime and delivery files
assumptions, confidence, and consequences
route and fallback route
structural, visual, temporal, export, and delivery checks
resource/time/iteration stopping rule
```

Mark every criterion as `user_explicit`, `reference_observed`, `use_required`, or `agent_assumed`. Do not let a failed generator silently delete a user criterion. If the interpretation changes, add an amendment and retain the previous criterion and evidence.

## Reference and style reasoning

Read references for design grammar, not only object labels. Extract silhouette, proportions, primary/secondary/tertiary forms, negative space, edge language, material/color hierarchy, surface wear, camera distance, and detail density. Distinguish “visible in the reference” from “plausible on an unseen side.” A single view cannot prove hidden geometry.

If the brief is open, choose a coherent style direction and record it. Keep detail density proportional to the intended camera and use: large forms first, functional/recognition details next, micro-detail last. Use lighting to reveal form, not to conceal a weak silhouette. The user is the final aesthetic judge; the agent must still expose technical defects and uncertainty.

## Route and representation decisions

Choose by form, use, and available capability, not by a favorite provider:

- Axis-symmetric product: profile/revolve plus separate attachments.
- Hard-surface product or panel: part graph, silhouette, controlled bevel/support treatment, normals, and deliberate booleans.
- Organic/character: sculpt, authored/generated/retrieved base, cleanup, and retopology only when deformation/UV/use needs it.
- Scene/kit: named assemblies, reusable source assets, instances/Geometry Nodes, scale and composition checks.
- Precision/print/fit: explicit units, datums, dimensions, tolerances, contacts, and a report.

Use procedural construction when the form is controllable and repeatable. Use a generated or retrieved mesh when it supplies shape information that code cannot plausibly express. Use a hybrid when a generated base needs cleanup, part separation, materials, retopology, or constraints. Preserve the original generated/imported asset and provenance. A provider prompt is not a deliverable.

For animation-ready geometry, record the rest pose, bone/part map, root or pivot intent, deformation test poses, units/axes, and 3D export target. Read `animation-contract.md` for that handoff. A mesh, rig, or valid export is not completed motion or proof of later native playback.

## Internal one-shot loop

The user should experience one request. Internally run bounded stages:

1. **Preflight:** probe capabilities, create the contract, set finite operation/repair/resource limits.
2. **Plan:** choose route, target profile, camera/use, source provenance, and protected criteria.
3. **Useful low-cost representation:** establish silhouette, composition, scale, and main relationships. This is an internal stage, never the final result when a finished asset was requested.
4. **Build:** create named parts/assemblies, then secondary and camera-critical detail. Keep editability where the use requires it.
5. **Review:** render clean hero and complementary views; run structural checks and targeted diagnostic passes.
6. **Repair:** patch one diagnosed scope from an accepted checkpoint, preserve passing criteria, rerun affected downstream checks.
7. **Handoff:** save, fresh-reopen, recheck, export requested formats, hash/read back outputs, and write a receipt.

Rendering before inspection is part of the process. A script exit code or a “done” tool response is not evidence of a correct scene. A clean beauty render is not evidence of hidden connections, topology, UVs, rigging, print fit, or runtime behavior.

## Visual and structural review

Use complementary views: hero, front, side, back, top, underside/section, or a close-up selected by the contract. Add clay, silhouette, wire, UV, material, collision, gap, or rig views only when they answer a known question. Keep final beauty evidence free of prompts, score hints, labels, and repair overlays.

The critic should inventory what is visible before receiving a checklist. Then check criteria with frame/object/region evidence and confidence. Compare before/after with consistent camera, scale, lighting, and exposure. Use A/B order swaps or repeats for close aesthetic choices, but treat visual judgment as a soft signal. Deterministic structure checks remain authoritative.

## Checkpoints and recovery

Checkpoint before a risky route change, generated import, destructive apply, bulk material operation, retopo, or export preparation. Every repair record should state the cause, evidence, scope, protected criteria, intended improvement, and result. Restore when the repair does not improve the target defect or regresses an accepted criterion.

Separate transport/runtime failures from modeling failures: bridge not connected, malformed command, timeout, unsupported format, generator failure, wrong representation, bad route, and actual geometry defect need different responses. Query an uncertain job/artifact before retrying; do not duplicate a render/import/export whose completion state is unknown.

## Research lessons that are safe to carry forward

- [Blender Studio Artist Guide](https://studio.blender.org/tools/artist-guide/asset-creation/modeling): design, blocking, deformation tests, camera-aware detail, cleanup, and handoff belong to one asset workflow.
- [Blender Studio retopology notes](https://studio.blender.org/blog/live-retopology-at-bcon22/): topology serves shape, selection, deformation, and performance; all-quads is not a universal law.
- [Blender Manual Spin](https://docs.blender.org/manual/en/latest/modeling/meshes/tools/spin.html), [Bevel](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/bevel.html), [Subdivision](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/subdivision_surface.html), [Geometry Nodes](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/introduction.html), and [Instances](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/instances.html): choose the operation from the form and preserve controllability.
- [BlenderWorld](https://arxiv.org/abs/2610.23986v1), [BlenderGym](https://arxiv.org/abs/2504.01786), [VIGA](https://arxiv.org/abs/2601.11109), and [3DCodeBench](https://arxiv.org/abs/2606.01057): separate executable/artifact checks from visual and preference judgments; render and repair iteratively.
- [SceneCraft](https://arxiv.org/abs/2403.01248) and [Procedura](https://arxiv.org/abs/2608.26238): use scene/part graphs, constraints, localized residual repairs, and transaction-like checkpoints where applicable.
- [Khronos glTF Validator](https://github.com/KhronosGroup/glTF-Validator): export validity is a hard interchange gate when GLB/glTF is requested, not proof of artistic quality.
- [MLLM-as-a-Judge](https://proceedings.mlr.press/v235/chen24h.html), [FRAME](https://aclanthology.org/2025.emnlp-main.1182/), and [Judging the Judges](https://arxiv.org/abs/2406.07791): clean evaluator images, pairwise/repeated checks, and uncertainty are safer than one confident score.
- [Simon Willison's public Blender artifact](https://github.com/simonw/gpt-6-astra-blender-pelican-bicycle) and [mcp-for-blender](https://github.com/ahujasid/mcp-for-blender): scripts, renders, scene state, and checkpoints are useful infrastructure; self-reported success remains scoped evidence, not a universal guarantee.

These sources support decisions and failure awareness. They do not prove that this skill has achieved a quality threshold until the current run executes and verifies it.
