# Roblox animation profile

This profile is the Roblox adapter for the representation-neutral animation
contract. It turns motion intent, timing, constraints, markers, loop policy,
and target quality into Roblox-native choices. It does not claim that a valid
Blender export is a native Roblox animation, and it does not grant permission
to publish an asset or modify a place.

Research snapshot: 2026-10-28. The target Studio/engine version is not pinned
and no live Studio execution is included in this profile.

The status words below keep documentation, inference, and execution separate:

- **DOCUMENTED**: stated by the linked Roblox Creator Hub API or workflow
  documentation.
- **PROPOSED**: an adapter policy chosen by this skill.
- **TESTED**: executed in the current Studio/target and inspected. This profile
  contains no current Studio test receipt, so implementation work must not
  promote a proposed route to tested.
- **NOT_TESTED**: the route is documented or plausible but has not run here.
- **UNKNOWN**: the current Studio build, capability context, rig, or asset
  permissions may change the result.

## Choose the native representation from the rig

Roblox has several joint representations. A semantic motion plan should not be
hard-coded to one class:

| Target | What the adapter must inspect | Preferred authoring/playback route | Boundary |
| --- | --- | --- | --- |
| R6 | The six legacy body parts and their joint names | KeyframeSequence/Pose for a local clip, or native Animation Editor/import | R6 has a smaller joint set; an R15 clip is not automatically equivalent |
| Standard or advanced R15 | Humanoid, Animator, current joint instances, and the T-pose/bind pose | Published or imported R15-compatible clip; local KeyframeSequence only when the exact part hierarchy is compatible | Do not assume every R15 rig is still Motor6D-only |
| Custom humanoid | HumanoidRigDescription, standardized joint mapping, T-pose, and any extra joints | Adaptive Animation mapping where supported, otherwise an explicit retarget/import adapter | Mapping is a runtime/rig contract, not proof that an arbitrary clip retargets |
| Mechanical or prop rig | Model hierarchy, Motor6D/constraint names, root, and owner/controller | Explicit local clip or procedural controller | Do not use Humanoid assumptions for a prop |
| Skinned mesh | Bone names, rest hierarchy, skin weights, and MeshPart collision intent | Native bone/CurveAnimation or DCC import route | Bone motion does not change physical collision |
| Upgraded avatar rig | AnimationConstraint presence and avatar feature configuration | Current avatar animation route plus an explicit capability check | Code that searches only for Motor6D can miss an upgraded rig |

Roblox documents R6 as six body parts and R15 as fifteen body parts; custom
retargeting requires a standardized joint mapping and a T-pose baseline. A
`HumanoidRigDescription` can reference `AnimationConstraint`, `Motor6D`, or
`Bone`, so the adapter must inspect the actual instance class before choosing a
writer. `Motor6D.Transform` remains useful for non-avatar mechanical rigs;
avatar rigs using the newer joint representation need the current
`AnimationConstraint` path.

The shared contract uses semantic channels rather than Roblox instance names:

```text
root
pelvis / lower_torso
spine / upper_torso
head
clavicle_l, upper_arm_l, lower_arm_l, hand_l
clavicle_r, upper_arm_r, lower_arm_r, hand_r
upper_leg_l, lower_leg_l, foot_l
upper_leg_r, lower_leg_r, foot_r
optional: fingers, face, weapon, prop, facial controls
```

Each target adapter resolves a channel to `{instance_name, joint_class,
parent_channel, bind_pose, optional}`. For R6/R15 this is commonly a
BasePart/Motor6D-compatible pose name. For a skinned rig it is a Bone path. For
an upgraded avatar it may be an AnimationConstraint path. A missing required
channel is a deterministic mapping error; silently dropping a channel changes
the motion contract.

## Authoring routes

Choose one route after inspecting the rig and the requested delivery:

1. **Programmatic local KeyframeSequence — DOCUMENTED, NOT_TESTED here.**
   Create a `KeyframeSequence`, add `Keyframe` instances at times in seconds,
   build a named `Pose` hierarchy, and add `KeyframeMarker` instances to the
   relevant keyframes. Roblox documents that poses are named for the BaseParts
   they correspond to and that keyframes are interpolated. The supplied
   `assets/roblox_clip_template.luau` implements this narrow route with an
   explicit rig and explicit complete samples. It creates no parent or preview
   target implicitly.

2. **Programmatic CurveAnimation — DOCUMENTED API, NOT_TESTED here.**
   `CurveAnimation` is an `AnimationClip` representation for channel curves.
   Use it when the target is a current curve/bone workflow rather than forcing
   a Bone or AnimationConstraint rig through a legacy part-name pose tree. The
   curve path needs a separate writer and a current Studio capability probe; the
   Luau template intentionally does not pretend to implement it.

3. **Blender/DCC import — DOCUMENTED workflow, NOT_TESTED here.** Roblox Studio
   can import FBX or glTF hierarchies with meshes, rigs, skinning, and animation
   data. Import settings, rig type, creator, permissions, scale, pivot, and
   zero-influence bones are part of the target contract. Import success is only
   transport evidence; inspect the actual rig, play the clip natively, and test
   markers, blending, authority, and cleanup separately.

4. **Animation Editor — DOCUMENTED native authoring, optional.** The editor can
   pose bones or meshes and saves local work under Studio's animation-save
   data. It is useful for inspecting a target rig, but this skill does not use
   “ask a novice to manually key every frame” as a fallback for AI authoring.
   An AI author can generate local clip data through Luau or use the Blender
   import route. Publishing is a separate, explicitly authorized step.

The `KeyframeSequenceProvider:RegisterKeyframeSequence` path is legacy and
deprecated in favor of `AnimationClipProvider` for newer `AnimationClip`
workflows. Keep it only when a known legacy place requires it and record that
choice in the receipt.

## Local registration and cloud publication are different states

`AnimationClipProvider` is a non-creatable, non-replicated service. Its
`RegisterAnimationClip` and `RegisterActiveAnimationClip` methods are documented
with the `Animation` capability and return an engine-provided `ContentId`.
Treat that value as a temporary local preview handle unless the current Studio
run proves a different scope. The value must come from the actual API call;
the adapter must never invent `rbxassetid://...`, hash, or `active://` strings.

The safe local sequence is:

1. Build an unparented clip from an explicit rig and config.
2. In a disposable Studio preview target, call one of the provider registration
   methods only when the caller explicitly enables local registration and marks
   the target disposable (`enabled = true`, `disposable = true`, and an
   explicit `datamodel_type`).
3. Record the returned value, method, `datamodel_type`, Studio version, and
   error text if it fails.
4. Create an `Animation` instance only from that returned value, and load it on
   an explicitly supplied `Animator` if playback is explicitly enabled.
5. Destroy only instances/tracks owned by the preview transaction.

Cloud publication creates a different artifact with creator/permission,
moderation, ownership, and asset-ID consequences. Roblox's animation editor
documentation specifically distinguishes local saved animation data from the
published asset normally referenced by a game. This profile does not publish,
request a paid asset, or claim that a local registration is available to a
client/server runtime or an online place.

## Capability probe before MCP or Studio execution

Roblox Studio MCP documents `execute_luau` with an explicit `datamodel_type` of
`Edit`, `Client`, or `Server`, along with data-model inspection and playtest
tools. That documentation proves the tool surface, not that this session has
the `Animation` capability for a particular API call. The effective capability
and the behavior of a temporary ID are **UNKNOWN** until a current Studio run
records them.

Use this probe plan; do not mutate a user's place implicitly:

1. Inspect Studio state and the intended `studio_id`; stop if the target is not
   the stated disposable preview place.
2. Run a read-only data-model check in each requested context (`Edit`, then
   `Client`/`Server` only if the test needs them). Record whether the context is
   available. Do not infer that Edit success transfers to runtime.
3. Create the clip in memory or in a clearly named, caller-owned temporary
   container. Run `RegisterAnimationClip` or
   `RegisterActiveAnimationClip` inside `pcall`; record success, returned value,
   and exact error. Do not upload.
4. If registration succeeds, load only the returned value on an explicit
   disposable preview `Animator`. Check the expected pose hierarchy and marker
   signals. A marker callback is presentation evidence, not gameplay authority.
5. Stop the track, disconnect callbacks, and destroy only the clip/animation/
   track/container owned by this probe. Leave pre-existing instances unchanged.

The probe must report `PASS`, `FAIL`, `NOT_TESTED`, or `UNKNOWN` per context.
An MCP connection, a version response, a successful script execution, or a
rendered viewport does not prove native playback, retargeting, root motion,
marker delivery, or multiplayer replication.

## Playback, blending, and events

Place an `Animator` under the target `Humanoid` or `AnimationController` and
ensure the animator is in `Workspace` before `LoadAnimation`. The current
documented API is `Animator:LoadAnimation`; direct
`AnimationController:LoadAnimation` is deprecated. Use
`Animator:GetTrackByAnimationId` or an owned track registry to avoid generating
duplicate tracks on repeated calls.

Set the clip/track's `AnimationPriority` deliberately. Roblox evaluates
`Action4`, `Action3`, `Action2`, `Action`, `Movement`, `Idle`, then `Core` from
high to low, per joint, and same-priority tracks blend by weight. A proposed
default is `Action` for a self-contained action and `Movement` for locomotion;
the controller contract can override it. Fade time and weight are part of the
transition, not decorative settings.

Markers carry a name and optional string value and can be observed through
`AnimationTrack:GetMarkerReachedSignal`. Use markers for presentation timing,
such as a footstep, flash, or camera cue. The server/authoritative simulation
owns damage, hit confirmation, inventory, and state transitions. A client
marker or local effect must not become evidence that gameplay happened.

Server/client behavior depends on how the `Animator` was created and where the
track is started. Player-character animation replication and non-player model
animation have different requirements. If a place uses server-authoritative
simulation, bind gameplay animation decisions to its authority contract and
resolve the live track after rollback/replacement rather than caching a track
across frames. Root-motion behavior is deliberately **not claimed** here; check
the current target API/release notes and test the actual rig before promising a
root-motion export or gameplay result.

## Lifecycle, performance, and review

Every created clip, `Animation`, track, marker connection, and temporary
container needs an owner and cleanup path. `AnimationTrack.Ended` occurs after
fade-out and is a useful cleanup point; `Stopped` occurs earlier. Disconnect
marker callbacks on cancellation, death, respawn, stream-out, or replacement.
Do not call `LoadAnimation` repeatedly for the same active asset without a
policy; duplicate tracks are both a correctness and performance risk.

For non-player NPCs, compare server and client animation deliberately because
replication and server CPU cost differ. Inspect `Animator.EvaluationThrottled`
and `PreferLodEnabled` where the current experience uses them, but do not treat
the property values as a universal performance guarantee. Profile baseline and
effect workload at the requested concurrency. Roblox's scene-analysis guidance
warns that scripts retaining animation objects can keep memory alive after a
model is destroyed; inspect references after cleanup.

The minimum useful review records:

- target rig class, exact mapping, bind/T-pose assumption, and route;
- Studio/runtime version and `Edit`/`Client`/`Server` context;
- local build, registration, and playback results separately;
- realtime and slow-motion footage, including loop/transition/cancel cases;
- marker and authority evidence, if gameplay is in scope;
- cleanup counters and memory/frame-time measurements where performance is in
  scope; and
- publication/ownership state, which remains separate from local readiness.

## Primary references

These are the official Roblox pages used for this profile; the current run has
not executed Studio against them.

- [Animation Editor](https://create.roblox.com/docs/animation/editor) — local
  animation saves, rig posing, timeline, priority, and publication boundary.
- [Animation overview](https://create.roblox.com/docs/animation) — animation
  targets, bones, constraints, inverse kinematics, and markers.
- [Rig Builder](https://create.roblox.com/docs/studio/rig-builder) — R6/R15
  rig composition.
- [Adaptive Animation](https://create.roblox.com/docs/characters/adaptive-animation)
  and [`HumanoidRigDescription`](https://create.roblox.com/docs/reference/engine/classes/HumanoidRigDescription)
  — custom-rig mapping and standardized joints.
- [`Motor6D.Transform`](https://create.roblox.com/docs/reference/engine/classes/Motor6D/Transform),
  [`Bone.Transform`](https://create.roblox.com/docs/reference/engine/classes/Bone/Transform),
  and [`AnimationConstraint`](https://create.roblox.com/docs/reference/engine/classes/AnimationConstraint)
  — joint representations and animation offsets.
- [`KeyframeSequence`](https://create.roblox.com/docs/reference/engine/classes/KeyframeSequence),
  [`Keyframe`](https://create.roblox.com/docs/reference/engine/classes/Keyframe),
  [`Pose`](https://create.roblox.com/docs/reference/engine/classes/Pose), and
  [`KeyframeMarker`](https://create.roblox.com/docs/reference/engine/classes/KeyframeMarker)
  — programmatic local clip structure.
- [`CurveAnimation`](https://create.roblox.com/docs/reference/engine/classes/CurveAnimation)
  and [`AnimationClipProvider`](https://create.roblox.com/docs/reference/engine/classes/AnimationClipProvider)
  — newer clip representation and local registration API.
- [`KeyframeSequenceProvider`](https://create.roblox.com/docs/reference/engine/classes/KeyframeSequenceProvider)
  — legacy registration API; check the current deprecation state before using it.
- [`Animator`](https://create.roblox.com/docs/reference/engine/classes/Animator),
  [`AnimationController`](https://create.roblox.com/docs/reference/engine/classes/AnimationController),
  [`AnimationTrack`](https://create.roblox.com/docs/reference/engine/classes/AnimationTrack),
  and [`AnimationPriority`](https://create.roblox.com/docs/reference/engine/enums/AnimationPriority)
  — playback, blending, and lifecycle.
- [Studio MCP](https://create.roblox.com/docs/studio/mcp) — documented MCP
  contexts and `execute_luau`; it does not by itself prove animation capability.
- [Studio importer](https://create.roblox.com/docs/studio/importer) and
  [Roblox performance optimization](https://create.roblox.com/docs/performance-optimization/improve)
  — transport settings and runtime/performance boundaries.
