# Animation engineering for a one-prompt skill

Research cutoff: 2026-10-28. This guide turns the reviewed Blender, studio, engine, web, rights, paper, and practitioner evidence in [`animation-sources.json`](animation-sources.json) into operating decisions. The animation entrypoint and packaged helpers are present; this guide does not claim that the routes below have been exercised in Blender or a native target runtime.

The user gives one ordinary-language request and judges the finished result. The agent owns interpretation, representation, source selection, rigging, retargeting, timing, staging, inspection, repair, export, and the delivery receipt. A blockout is an internal planning stage. The user is not required to approve it before the agent continues. A final aesthetic response may improve a later revision, but it is optional after the first complete delivery.

## What the request must become

Translate the novice request into a compact motion contract before touching a tool. Keep the user's words and the agent's assumptions separate. The contract should contain:

- **Subject and action:** who or what moves, the verb of the movement, the intended emotional or mechanical read, and the event that starts and ends it.
- **Target and use:** Blender scene, editable action, rendered shot, GLB/glTF, FBX, Unreal, Unity, Roblox, SVG/Grease Pencil, CSS/Web Animations, Rive, sprite sheet, or video. The target determines the native representation and the checks.
- **Timing:** frame rate or browser timebase, duration, loop policy, holds, accents, anticipation, contact frames, and whether speed may be retimed.
- **Spatial constraints:** root motion or in-place motion, planted feet or hands, object attachments, camera path, ground/contact surface, collision/support, and screen-space composition.
- **Style grammar:** realistic, stylized, low-poly, snappy 2D, mechanical, weighty, floaty, restrained, or exaggerated. Describe the visible read rather than naming an implementation feature.
- **Source and rights policy:** custom generation, an existing licensed clip, a CC0 library, or a hybrid. Preserve the source clip, license, version, retarget settings, and any baked derivative.
- **Acceptance evidence:** a clean hero/shot preview, temporal contact and loop checks, complementary views, structure/export checks, and the limitations that remain `NOT_TESTED`.

Do not make the user choose a skeleton mapping, easing curve, engine plug-in, Blender operator, or polygon/keyframe budget. If a missing choice changes the route materially, ask one short plain-language question. Otherwise choose a conservative route, record the assumption, and continue.

## Representation and provenance

Animation is not one file type. Keep the semantic motion plan separate from the native target artifact.

| Target | Native source to preserve | What an export or render proves | Required boundary |
| --- | --- | --- | --- |
| Blender | `.blend`, named armature, Actions/NLA, constraints, drivers, source script | File/scene transport and any checks actually run | A valid `.blend` or still render does not prove deformation, playback, or aesthetic quality. |
| GLB/glTF | Action/armature source plus exported `.glb` and validator report | Interchange syntax, buffers, animation channels, and extension validity | Khronos validation does not prove good contacts, silhouette, or native playback in the target application (AN39–AN41). |
| FBX | Source scene plus FBX take/range, skeleton, root policy, and axis/scale record | File was written/read by the exporter if that was tested | The target engine must still be opened and previewed. Do not call a render-only FBX “rig-ready.” |
| Unreal | Skeletal Mesh, IK Rig, IK Retargeter, Animation Sequence, Pose Search database, or GASP project asset | Unreal asset import or project state only when actually checked | GASP is an Unreal project/asset route. Do not assume cross-platform or AI rights from a polished sample (AN53–AN55, AN68–AN71). |
| Unity | Model/Avatar, Animation Clips, Animator Controller, Avatar Mask, root-motion setting | Imported clip metadata and any Editor preview actually inspected | Humanoid mapping, T-pose, clip range, root motion, and discarded-channel warnings need a native Unity check (AN56–AN59). |
| Roblox | KeyframeSequence/published animation, rig, priority, markers, and `IKControl` overlay | Published asset or Studio preview only when actually run | Roblox uses a 30 fps seconds:frames timeline and an intended `AssemblyRootPart`; native playback remains unverified until Studio is exercised (AN51–AN52). |
| SVG / Grease Pencil | SVG path/timeline or Grease Pencil keyframes | A documented conversion or export operation | Blender 5.2 documentation describes path-only curve import and Grease Pencil frame export, but this workspace has not run SVG 5.2 or browser playback. Keep that status `NOT_TESTED` (AN49–AN50). |
| CSS / Web Animations | HTML/CSS/JS keyframes, offsets, duration, iterations, reduced-motion policy | Browser parser/runtime result when tested | Do not infer browser support from a Blender render. Open the generated artifact in the intended browser (AN60–AN61). |
| Rive | `.rml` text, `.rev` editor project, `.riv` runtime file, scripts/assets | Rive verification/headless render or native runtime result | `.rml`, `.rev`, and `.riv` are different artifacts. A generated `.riv` is not proof that a `.rev` editor project or target runtime is intact (AN62–AN63). |
| Video / image sequence | Source scene and action plus encoded frames | The encoded frames and timing | A beautiful video may be a post-render or image-model result; it does not prove mesh topology, rig state, or a native clip. |

Every source or derivative gets a small provenance record: `source_id`, original URL or local asset identifier, creator/license, version/date, original skeleton/rest pose, retarget map, scale/axis, root policy, edits, bake/export settings, and the artifact hash. MIT-licensed plugin code and docs are one dependency boundary. Mixamo, GASP/Fab, Quaternius, Kenney, or any other motion/mesh asset keeps its own license and may not silently become part of the plugin's code or bundled library.

## Motion craft rules

These are context-dependent decisions for the internal critic. They are not a demand that every shot contain every principle.

### Pose, silhouette, staging, and emotion

1. Read the action from a thumbnail. At the key poses, check line of action, weight distribution, facing, negative space, and the silhouette of hands, feet, props, and face. A detailed mesh cannot rescue a pose that reads as a flat shape.
2. Stage the action so the important event is visible from the camera: separate overlapping limbs, keep the contact or object interaction in view, control the background contrast, and avoid camera motion that hides the change being judged. Disney's public animation overview explicitly pairs timing with clear staging and appeal (AN46).
3. Build an emotional arc from visible intent: preparation, decision, action, reaction, and settle. A neutral body can perform a mechanical action; a human or creature needs a readable center of attention, gaze, shoulder/hip relationship, and secondary response.
4. Use anticipation before a large or surprising action when it improves readability. Do not insert a theatrical wind-up into a subtle blink, a heavy machine's constant drive, or an already compressed game reaction. The counterexample is useful: anticipation is a tool for audience prediction, not a mandatory key on every motion.
5. Use follow-through and overlap where parts have different inertia: hair, cloth, ears, a loose strap, a hand-held object, or a secondary prop. Turn it down for rigid, bolted mechanisms. A mechanical arm that lags like cloth violates the object's material read.

### Timing, spacing, weight, contact, and arcs

1. Treat timing as event placement and spacing as the distance traveled between events. Start with clear extremes and contact/hold frames; then tune the in-betweens. A uniform linear curve often reads as stiff or robotic. Roblox documents this directly by contrasting linear easing with cubic easing and by exposing constant, elastic, and bounce choices (AN51).
2. Make weight visible through acceleration, deceleration, compression, recoil, and recovery. A heavy object should not reverse direction at the same speed as a light hand gesture. Preserve momentum through the center of mass and let the support surface answer the force.
3. Mark contacts explicitly. A planted foot, hand on a door, wheel on a floor, or tool against a part needs a time window and a spatial tolerance. Lock or constrain it only for that window; release it for a passing limb or airborne step. Over-locking produces a skating or rubber-limb failure.
4. Inspect arcs for limbs, heads, cameras, and thrown objects. Use a clean arc for a pendulum-like limb or camera pan; choose a deliberately straight or piecewise path for a piston, rail, drawer, or laser. An arc is not automatically more natural.
5. For locomotion, separate root displacement from local gait. Decide whether the clip is in-place, root-driven, or controller-driven; compare stride length, foot plant, pelvis height, and turn radius; then verify the loop seam. Unity's docs show why root motion is a playback policy, while Unreal's retargeting docs distinguish root, pelvis, IK, and weapon translation behavior (AN55–AN59).
6. For a loop, duplicate or match the first and last pose according to the target. Roblox explicitly notes that a loop does not interpolate final to first and recommends duplicating the first keys at the end (AN51). In Blender, inspect both the curve and the rendered seam; a numerically identical pose can still produce a lighting or camera discontinuity.

### Object, mechanical, camera, and secondary motion

- **Mechanical:** define pivots, axis limits, gear or linkage relationships, contact surfaces, and the force that starts/stops the part. Use constant or stepped interpolation when the design is indexed; use ease only when the mechanism actually accelerates.
- **Held objects:** parent or constrain the prop during the contact interval, but check grip, wrist orientation, hand IK, and release. Retargeting can preserve body motion while leaving a prop misaligned; Unreal documents hand IK chains as a way to keep a prop in the hand (AN55).
- **Camera:** choose a readable lens, height, and screen direction before polishing motion. A camera move can create an appealing render while hiding foot slide or collapsing the subject's silhouette. Review a locked-camera pass and a motion pass separately.
- **Secondary action:** add a small gaze, shoulder, tail, cloth, light, or environmental response only after the primary action reads. Secondary motion should clarify intent or material, not compete with the event.
- **2D/vector:** use holds, clear pose changes, deliberate spacing, silhouette/line-of-action, and fewer but meaningful keys. SVG and Web Animations operate on attributes/styles and browser timelines rather than bones; do not export a 3D rig and assume it is a vector animation (AN49–AN61).

### Adaptation versus literal transfer

An existing clip is a starting signal, not a finished answer. Before retargeting, inspect rest pose, bone names/chains, scale, forward/up axes, root convention, contact surfaces, and the target's proportions. Unreal's IK Retargeter supports differing bone counts, names, orientations, and explicit retarget poses, but this flexibility does not remove the need to inspect the result (AN53). Unity likewise says a successful automatic Avatar match still requires pose and mapping review (AN56).

After transfer, repair the target-specific features: foot and hand contacts, pelvis height, stride, prop grip, camera-facing silhouette, and personality. Preserve the unmodified source and label the repaired/baked result. If a clip is only good for locomotion but the brief requires an expressive performance, combine it with authored upper-body, face, or camera motion instead of pretending retargeting solved the whole shot.

## Source policy and rights

The supplied Facebook material is useful as a hypothesis about retrieval and retargeting, not as proof of a particular website or creator workflow. The caption speculates that an unnamed site may aggregate Mixamo or Unreal GASP clips onto one skeleton; four comments, two images, and two video samples (13.64 s and 62.30 s) were inspected. The visible `1137` count is a self-reported UI number, not a payload or catalog measurement. No direct source clip, API trace, license, skeleton, `.blend`, or `.fbx` was supplied. The catalog intentionally omits raw post text, screenshots, session data, and an author identity dossier (AN76).

Use a hybrid policy selected by the target and quality:

1. Prefer a custom or procedural clip when the action is unique, expressive, mechanical, or not covered by a licensed library.
2. Prefer a CC0 or otherwise approved library clip when it gives a better base for ordinary locomotion or reusable gestures. Quaternius publishes a CC0 Universal Animation Library with retargetable humanoid clips; Kenney publishes CC0 animated characters, but neither page proves this workspace's runtime compatibility (AN72–AN74).
3. Mixamo can be used for an embedded personal/commercial project under the current Adobe FAQ, subject to the binding terms. Adobe's Additional Terms prohibit using Mixamo content, output, or derived information to create, train, test, or improve ML/AI systems. Do not make it a training/evaluation corpus or redistribute raw library files (AN64–AN67).
4. Treat GASP/Fab as an Unreal-targeted source until the exact asset license says otherwise. Epic's docs and listing describe a large UE animation set, but the listing showed `Allows usage with AI: No` and did not expose a complete specific license field in the inspected view. Do not infer Blender/Unity/FBX redistribution or AI rights (AN68–AN71).
5. Record the provenance decision even for CC0. CC0 permits broad copyright use but does not waive patent, trademark, privacy, or publicity rights and does not verify underlying ownership (AN75).

## Internal one-shot pipeline

The user sees one request. The following stages remain internal unless a failure or missing input makes continuation unsafe.

1. **Preflight and contract.** Detect the available Blender/connector/target runtime, record version and latency, choose the target representation, and create a bounded run ledger. A connector can be unavailable even when Blender is installed; keep bridge, Blender, script, and artifact failures separate (AN16–AN25, AN28–AN33).
2. **Route and source.** Classify the motion as locomotion, acting, mechanical/object, camera, 2D/vector, or interactive/runtime. Choose custom, retrieved, or hybrid motion and write the rights/provenance entry before using an external clip.
3. **Rest-pose and rig check.** Inspect armature hierarchy, root, axes, scale, bind/rest pose, chains, constraints, and intended contacts. Build a mapping table. If a source/target pose differs, create an explicit retarget pose; do not let the engine silently compensate.
4. **Internal block and pose selection.** Create a cheap blocking pass with the camera and ground/prop context. Inspect thumbnail silhouettes and key poses internally, compare candidate source clips or generated variants, and select/repair without waiting for user approval. Protect the best checkpoint.
5. **Timing and spacing pass.** Place extremes, contacts, holds, anticipation, accents, and settle. Replace uniform linear interpolation where the material or style needs acceleration, and retain it where a rigid/indexed mechanism calls for constant motion.
6. **Contact and overlap pass.** Repair foot/hand/prop contacts with constraints or IK only in their declared windows. Add overlap, follow-through, secondary action, facial/gaze response, or mechanical recoil according to the brief. Inspect arcs and center-of-mass behavior.
7. **Staging and camera pass.** Lock a readable camera, subject scale, negative space, lighting, and background. Render the action without diagnostic labels. Keep an alternate view or diagnostic view to expose slide, clipping, collisions, and hidden rig failures.
8. **Structural and temporal checks.** Inspect saved data, not only the tool response: armature and action existence, frame range, keys/curves, NaN/Inf values, root policy, loop seam, contact distances, constraints, object attachments, and export channels. Use target validators where available.
9. **Critic and repair loop.** Run an independent prompt-free visual critic against the contract, then a deterministic checker. Use pairwise/repeated comparisons for candidates, randomize A/B order when comparing renders, and abstain on conflicting judgments. Repair one diagnosed scope from a checkpoint and rerun downstream checks (AN01–AN03, AN35–AN45).
10. **Save, reopen, export, and receipt.** Save the source scene and script, reopen when possible, rerun the required checks, write the requested export, read it back with the target validator, and produce a render/contact sheet plus plain-language receipt. Report native runtime as `NOT_TESTED` unless it was actually exercised.

The internal loop has finite operation, render, repair, time, and source-search budgets. An agent claim that it is “done” is not an outcome. The saved artifact, rendered evidence, checks, and receipt are the outcome (AN42–AN45).

## Failure and recovery matrix

| Observed symptom | Likely class | Recovery owned by the agent |
| --- | --- | --- |
| Motion looks robotic or weightless | Timing/spacing/easing or missing contacts | Compare extremes and contact windows, change spacing/holds/acceleration, then re-render. Do not fix it by adding random keyframes (AN46, AN51, AN53). |
| Feet slide or hands miss a prop | Root/rest-pose/IK/retarget mismatch | Inspect root policy, retarget pose, target proportions, and contact anchors. Use IK only during declared contact windows; rerun the temporal check (AN52–AN59). |
| Loop pops | First/last pose, root displacement, camera/light discontinuity | Match the seam, duplicate target-required keys, decide in-place versus root-driven motion, and inspect the first/last rendered frames (AN51, AN57). |
| Clip looks plausible on one character but deforms another | Bone-chain, scale, rest pose, or translation policy | Repair mapping/retarget pose, preserve source, and compare silhouette/contact views. Do not hide the failure with a beauty camera (AN53–AN58). |
| Render is attractive but animation/artifact is wrong | Render-only or post-render evidence | Inspect saved actions/armature/export channels and open the target runtime. Keep the render as visual evidence only. |
| Critic approves visibly bad geometry or disagrees across passes | Judge bias/self-evaluation | Use clean renders, independent criteria, deterministic scene queries, A/B order swaps, and `UNCERTAIN` when repeats conflict (AN28–AN33, AN35–AN39, AN43–AN45). |
| Bridge stalls, duplicate servers, malformed JSON, or context grows | Transport/control failure | Stop geometry retries; run handshake/process/port/tool-list preflight, query job state, recover from checkpoint, and classify timeout versus Blender or artifact failure (AN16–AN25, AN33). |
| Source clip cannot be shipped | Rights/provenance failure | Remove the asset from the bundle, retain only permitted project/render use, choose a CC0/custom fallback, and write the restriction in the receipt (AN64–AN76). |
| SVG/Rive/engine file parses but target does not play | Representation/runtime boundary | Keep source and exported artifact, run the target parser/player, report the exact untested surface, and do not call transport validity native playback (AN49–AN63). |

## Acceptance vocabulary

Every check returns one of these states:

- `PASS`: the stated check ran and its evidence satisfies the contract.
- `FAIL`: the check ran and found a defect that blocks the requested route.
- `UNCERTAIN`: evidence is conflicting, insufficient, or judge-dependent; do not silently promote it to pass.
- `NOT_APPLICABLE`: the contract excludes the check.
- `NOT_TESTED`: the route or runtime was not exercised. This is the correct status for Blender 5.2 SVG runtime, Unreal/Unity/Roblox/Rive native playback, and any target not opened in the current run.

At minimum, the receipt should contain:

```text
target / representation / runtime version
motion contract and assumptions
source clip, license, version, rest pose, retarget map, and provenance
frame rate / duration / loop / root-motion policy
camera and staging used for visual evidence
checks: status, evidence path, and affected object/region
repairs: cause, checkpoint, protected criteria, result
artifact paths and hashes
native runtime status
unresolved limitations and optional user aesthetic feedback
```

Do not use a generic “animation quality” number as a substitute for evidence. Aesthetic preference is soft and belongs to the final user judgment; contact, file, export, and runtime claims require the corresponding observed artifact or test.

## Source and implementation boundaries

The catalog contains 91 reviewed entries. Reused records preserve their original IDs through `source_refs`, exact titles/URLs, and original read-depth limitations. The official craft/platform/rights records are `AN46`–`AN76`; focused motion-research/evaluation records are `AN77`–`AN91`. The latter are 15 catalog records for 15 distinct primary-paper identities, all marked `abstract` depth in the JSON unless separately stated. In particular:

- `AN49`–`AN50` are Blender 5.2 documentation evidence, not SVG runtime tests.
- `AN62`–`AN63` distinguish RML text, `.rev` editor projects, and `.riv` runtime files.
- `AN76` retains only a sanitized, supplied-context observation; it is not proof of Mixamo/GASP usage or an author dossier.
- `AN77`–`AN91` preserve research cues for conditioned motion, local temporal editing, spatial constraints, transitions, physical plausibility, interaction, topology-aware retargeting, semantic part planning, physics-grounded motion, and temporal/style evaluation. Their paper metrics remain self-reported external evidence; they are not local backend or runtime tests.
- Historical paper metrics and practitioner self-reports explain design choices but are not measurements of this plugin's latency, cost, or quality.
- A retrieved clip, a native editable action, and a rendered video are separate evidence surfaces.

The animation implementation is [`skills/blender-engineering-animation/SKILL.md`](../../skills/blender-engineering-animation/SKILL.md), with the operational references [`research-playbook.md`](../../skills/blender-engineering-animation/references/research-playbook.md), [`motion-craft.md`](../../skills/blender-engineering-animation/references/motion-craft.md), [`quality-and-delivery.md`](../../skills/blender-engineering-animation/references/quality-and-delivery.md), and [`motion-sources.md`](../../skills/blender-engineering-animation/references/motion-sources.md). Its packaged helpers are [`blender_animation.py`](../../skills/blender-engineering-animation/scripts/blender_animation.py), [`evidence.py`](../../skills/blender-engineering-animation/scripts/evidence.py), and [`sprite_pipeline.py`](../../skills/blender-engineering-animation/scripts/sprite_pipeline.py). This research pass did not execute those helpers, Blender, or a native engine; record any future runtime gates in [`../VALIDATION.md`](../VALIDATION.md) before claiming them tested.
