# Temporal quality, repair and delivery

Read this with the research playbook and the actual platform profile. A checker
proves only the property it measures. A renderer or JSON gate cannot certify taste.

## Establish the contract and evidence

Keep user-required semantics, technical use requirements and inferred choices
separate. Freeze criterion IDs and applicability before production. Preserve
amendments; never demote a failed requirement to optional after seeing results.
Specify representation, target, style, duration/exposures, loop and root/pivot
intent, contacts, markers and deliverables. Record the finite operation/run budget.

Collect three distinct kinds of evidence:

1. **Source/evaluated state:** actual channels, rig map, native frame range,
   slots/blends, evaluated transforms, sprite metadata or vector state.
2. **Temporal visual evidence:** ordered key poses, full-speed playback and
   slow-motion diagnostics of suspicious intervals. Record timestamps, source
   and playback rates, capture method, dropped frames and source identity.
3. **Receiving runtime:** import configuration and actual controller/player
   behavior when a target runtime is required. File validity is a separate result.

Keyframe sheets check coverage, not in-betweens. Source keys alone miss NLA,
constraints, simulation, interpolation and engine compression. A dropped-frame
viewport is not the only timing reference; use a deterministic frame sequence
and correctly timed playback. A video that was only generated remains unviewed
until the agent inspects it using available media/browser tools.

## Checks appropriate to the job

| Property | Meaningful check | Important exception |
|---|---|---|
| Semantics | Required beats/parts exist, are visible and occur in order | A named empty or invisible tiny part is not presence proof |
| Numeric validity | Finite channels, transforms, durations and valid hierarchy | Deliberate holds are valid repeated values |
| Rig/retarget | Rest pose, axes, mapping, scale, bone lengths where invariant | Squash/stretch may deliberately animate scale |
| Contact | World-space drift/penetration during declared support/grip | Swing, skating, flight and deliberate overlap differ |
| Root | Compare intended in-place/authored/extracted displacement | Zero displacement is not the default for locomotion |
| Loop | Boundary pose and motion continuity for a declared loop | One-shot motion need not return to its initial pose |
| Timing | Duration, exposures, phase order, speed and event behavior | A held drawing or mechanical snap can have high jerk |
| Sprite | Frame order, anchors, trim offsets, palette, alpha, atlas edges | Full-canvas frames may be larger but intentionally stable |
| Runtime | Native player, blend/controller, events, cancel and cleanup | An export does not include every engine's behavior graph |
| Persistence | Reopen exact saved source, dependencies and export | Byte hashes can change on resave; compare semantic state too |

Do not fabricate a universal numerical threshold. Derive tolerances from units,
frame rate, style, target requirements and the fixture being evaluated. Report
uncertainty instead of silently assuming a surface, movement or feature is correct.

## Critique and localized repair

Use a fresh critique context. First inventory what is actually visible and the
events that occur; then compare the evidence with the contract. Return findings
with criterion ID, frame/time, object/joint, confidence, observed versus inferred
cause and repair scope. Same-model evaluation is `SELF_EVAL_ONLY`; another model
is not automatically ground truth either. For close candidate choices, compare
equivalent framing/playback and swap A/B order.

Before repair save the accepted source, its fingerprint and evidence. Change a
diagnosed region or temporal interval, then reevaluate the target defect and
protected requirements. Commit only justified improvements; restore regressions.
After an asynchronous timeout identify the owned job/output state before retrying.
Do not duplicate edits or render jobs on an unknown state, kill unrelated user
processes, or overwrite the only good file.

When no improvement remains or the finite budget is exhausted, preserve the best
artifact and report the unmet criteria. Do not redefine success as script exit 0.

## Target optimization and preservation

Inspect native costs and preserve an accepted reference version. Reduce curves,
bake constraints, lower deformation detail, throttle distant evaluation, reduce
atlas cost or change runtime layers only where the target benefits. Recompare
contact, timing, roots, events and silhouette after lossy changes. Measure paired
baseline and result in the claimed runtime/device context; no universal FPS or
bone-count guarantee follows from a desktop preview.

Keep native editable source and baked interchange separate. Include textures,
atlases, relative asset paths and required simulation caches. Record external
dependencies and source terms; do not package restricted libraries as public
plugin assets. Reopen from the delivery directory without relying on hidden
author caches. Render the reopened accepted file and link its identity to frames.

Treat absolute path resolution as a local preparation step, not packaging.
When the export helper reports `portable_delivery_complete: false`, complete
the bundle yourself: pack supported image dependencies, copy required libraries,
atlases and caches into the delivery tree, rewrite portable relative paths, and
include hashes. Preserve the original source before this work. Reopen a relocated
copy of the bundle, inspect all required dependency resolutions, and confirm that
each is embedded or inside that copy. Do not rename or hide the user's original
assets merely to run this check. A verified interchange readback can coexist with
an incomplete portable bundle; report these separately.

## Completion semantics

`READY_FOR_REVIEW` requires actual artifacts and evidence for every required
applicable criterion. `NOT_APPLICABLE` needs a reason grounded in the contract.
Missing evidence, `FAIL`, `UNCERTAIN` and `NOT_TESTED` on required criteria mean
`INCOMPLETE`, not a taste question for the novice to debug. A missing runtime may
leave a completed local asset but incomplete target validation; state both.

The evidence helper validates report structure and file integrity. It cannot
watch playback, authenticate hardware, prove research was read, or verify a
claimed observation merely because the report says PASS.

Useful research: [FlowMDM](https://arxiv.org/abs/2402.15509) on transition
diagnostics, [AnimationBench](https://arxiv.org/abs/2604.15299) on stylized motion,
[VBench](https://arxiv.org/abs/2311.17982) on temporal dimensions, and
[MLLM-as-a-Judge](https://arxiv.org/abs/2402.04788) on evaluation limitations.
