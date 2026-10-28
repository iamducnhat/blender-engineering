# Cross-engine animation profile

The shared animation plan is intentionally engine-neutral. It describes motion
intent, semantic channels, timing and phase, constraints, markers, loop/cancel
policy, target quality, and an owner for runtime cleanup. Each engine adapter
then chooses its native clip, skeleton, controller, event, root-motion, import,
authority, and publication mechanism. A GLB/FBX file that passes an interchange
validator is transport evidence; it is not proof of native playback or visual
quality in every engine.

Research snapshot: 2026-10-28. Engine versions and project package revisions are
not pinned here; every profile below is documented capability until a target
probe records a tested result.

Status labels are **DOCUMENTED** (official documentation), **PROPOSED** (an
adapter policy), **TESTED** (executed in the current target), **NOT_TESTED**
(documented but not executed here), and **UNKNOWN** (requires a version/project
probe). This file contains no live engine test receipt.

## Shared contract and adapter boundary

| Shared motion core | Engine-specific adapter |
| --- | --- |
| Semantic channels and intent (`root`, `pelvis`, `hand_l`, `weapon`, `impact`) | Skeleton/bone/joint path and retarget mapping |
| Bind/rest pose and constraints | Native rig type, avatar profile, or skeletal asset |
| Interpolation, easing, spacing, and curve intent | Engine curve/tangent, compression, track, or blend implementation |
| Phase times, spacing, loop, cancel, and blend policy | Clip asset class and controller/state-machine graph |
| Marker taxonomy and payload schema | Marker/notify/event API and callback lifecycle |
| Root-motion intent and extraction policy | Engine root-motion mode, character controller, or explicit code |
| Presentation versus authoritative gameplay events | Server/client/replication/prediction model |
| Low/high quality intent and budgets | LOD, evaluation, particle, audio, and streaming controls |
| Owner, cleanup, and review evidence | Engine object lifetime, track disposal, and profiler evidence |

Adapters must fail when a required semantic channel cannot be mapped. They must
not silently claim that an imported clip retargeted, that root motion moved the
character, or that an event affected gameplay.

## Roblox

Roblox has R6, R15, custom humanoid, mechanical Motor6D, skinned Bone, and
AnimationConstraint targets. Use the detailed [Roblox profile](roblox.md) and
the supplied local [Luau template](../assets/roblox_clip_template.luau).

Documented native choices include `KeyframeSequence`/`Keyframe`/`Pose` for an
explicit local clip, `CurveAnimation` for channel curves, Blender FBX/glTF
import, and the Animation Editor. Current playback should use an `Animator`
under a `Humanoid` or `AnimationController`; direct
`AnimationController:LoadAnimation` is deprecated. `AnimationClipProvider` can
register a clip through a capability-gated local API, but the returned value is
not a cloud-published asset ID. MCP's `execute_luau` supports `Edit`, `Client`,
and `Server` datamodel contexts; actual animation capability still requires a
current disposable probe.

## Unity

**DOCUMENTED API surface, NOT_TESTED here.** Unity's native route is an
`Animator` with an `Avatar`, imported `AnimationClip` data, controller layers,
state machines, blend trees, transitions, masks, and optional
`AnimationEvent`s. `Animator.applyRootMotion` and the project's character
controller define whether root motion is applied to the object or consumed by
gameplay code. Retargeting depends on a valid humanoid Avatar or an explicitly
compatible generic rig; identical bone names alone are not proof.

The adapter should import FBX or the project's supported interchange format,
inspect the generated Avatar and clip curves/interpolation, then test
layer/weight blending, events, interruption, and controller authority.
`AnimationClip` is a native
Unity asset after import, while the source file remains provenance. Do not
claim universal GLB behavior: importer version, humanoid mapping, coordinate
conventions, root bone, scale, compression, and material/animation settings
change the result. Check the current Unity version's import and package docs at
implementation time.

## Unreal Engine

**DOCUMENTED API surface, NOT_TESTED here.** Unreal's native route uses a
`USkeletalMesh` and `USkeleton` with `UAnimSequence`, Animation Blueprints,
`AnimMontage`, `AnimNotify`/notify states, Blend Spaces, slots, and transition/
pose graphs. Root motion is an explicit animation and CharacterMovement policy;
whether it is extracted, ignored, or replicated must be verified in the target
Character and network mode. IK Rig and IK Retargeter provide a native mapping
route for compatible skeletons; source/target retarget poses and chains are
part of the contract.

Use FBX or the project's tested importer path, then inspect skeleton hierarchy,
retarget pose, curve interpolation/notify data, montage slots, blend weights,
and authority.
`GASP` means Epic's **Game Animation Sample Project**, an optional sample and
reference project for studying animation systems. `GAS` means the **Gameplay
Ability System**, a separate optional runtime framework for abilities and
interactions. They are different things, and neither is implied by a motion
clip, screenshot, or social-media post. GASP/GAS prediction, ownership,
montage-task, and gameplay-cue claims require official project/engine evidence
and the target version; a clip does not prove either backend. Do not bundle raw
GASP sample content or Gameplay Ability System dependencies/community packs
into this skill. Do not claim glTF is a universal Unreal skeletal-animation
route.

## Godot

**DOCUMENTED API surface, NOT_TESTED here.** Godot's native route is an
`AnimationPlayer` with `AnimationLibrary`/`Animation` resources, optionally fed
into an `AnimationTree` for state machines, blend nodes, and one-shot or blend
transitions. Skeleton3D bone tracks and `BoneAttachment3D` provide the rig
side; method/call tracks and signals can drive presentation callbacks. A
character controller or explicit extraction code owns root movement, and the
exact root-motion helper depends on the target Godot version and node setup.

glTF is a common Godot import route, but importer settings, skeleton profile,
bone rest transforms, naming, track interpolation, compression, and
animation-library setup still
need inspection. Keep imported source and native resource provenance. Test
AnimationTree blending, loop/cancel, method-track cleanup, and controller
authority in the actual project; a successful import is not native playback
evidence.

## Three.js and the web

**DOCUMENTED API surface, NOT_TESTED here.** For a 3D scene, use a tested
`GLTFLoader` route when the asset is glTF, then drive `AnimationClip`,
`KeyframeTrack`, `AnimationMixer`, and `AnimationAction`. Loop mode,
`crossFadeFrom`/`crossFadeTo`, weight, time scale, and action events implement
blending and lifecycle; `KeyframeTrack` interpolation and the imported clip's
sampling remain adapter concerns. Skeleton and bone names remain an adapter
concern too.

The Web Animations API (WAAPI) is a browser animation system for DOM/style
targets; it is not, by itself, a three.js skeletal animation controller. Use
WAAPI for UI or coordinate a 3D controller explicitly. Root motion must update
the character/controller or a scene root in application code; a GLB clip does
not automatically move gameplay. Marker events likewise need an explicit
application event map and cleanup.

## Interchange and evidence rules

Use FBX, glTF/GLB, or another format only when the target importer and use case
support it. Preserve source scene, skeleton map, export settings, units,
forward/up axes, root policy, clip names, markers/notifies, and license
provenance. A validator can prove that a file is structurally valid for the
format. It cannot prove avatar retargeting, controller state transitions,
authority, root motion, marker delivery, visual polish, or low-end performance.

For each adapter, the handoff should state:

```text
target engine/version: documented or tested
source and license/provenance:
semantic map and bind/rest assumption:
native clip/controller asset:
import/retarget result:
loop/interrupt/blend result:
markers/notifies and authority:
root-motion policy and test:
cleanup/performance evidence:
publication/ownership state:
unknowns and next probe:
```

The Roblox adapter is the most constrained by local capability and temporary
registration; see `roblox.md` for the explicit `Edit`/`Client`/`Server` probe.
The shared core can travel between engines, while the native asset/controller,
event authority, root policy, and import/runtime proof cannot be assumed to
travel with it.

## Primary documentation

- [Roblox animation profile](roblox.md) and [Roblox Studio MCP](https://create.roblox.com/docs/studio/mcp)
- [Unity Animator](https://docs.unity3d.com/Manual/AnimationParameters.html),
  [Animation clips](https://docs.unity3d.com/Manual/AnimationClips.html), and
  [root motion](https://docs.unity3d.com/Manual/RootMotion.html)
- [Unreal Animation Blueprints](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-blueprints-in-unreal-engine),
  [IK Rig/Retargeter](https://dev.epicgames.com/documentation/en-us/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine),
  and [root motion](https://dev.epicgames.com/documentation/en-us/unreal-engine/root-motion-in-unreal-engine)
- [Game Animation Sample Project](https://dev.epicgames.com/documentation/en-us/unreal-engine/game-animation-sample-project-in-unreal-engine)
  — optional Epic sample/reference context; no raw GASP content is bundled here.
- [Gameplay Ability System](https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-ability-system-for-unreal-engine)
  — separate optional runtime ability-system context; no dependency is bundled here.
- [Godot AnimationPlayer](https://docs.godotengine.org/en/stable/classes/class_animationplayer.html),
  [AnimationTree](https://docs.godotengine.org/en/stable/classes/class_animationtree.html),
  and [glTF import](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/advanced_import_settings.html)
- [three.js Animation System](https://threejs.org/manual/pages/animation-system.html),
  [AnimationMixer](https://threejs.org/docs/pages/AnimationMixer.html),
  and [GLTFLoader](https://threejs.org/docs/pages/GLTFLoader.html)
- [Web Animations API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API)
  — DOM/web animation context, not a universal 3D skeleton runtime.
