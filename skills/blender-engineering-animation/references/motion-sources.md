# Motion-source and reference policy

This file governs where motion ideas, clips, rigs, sounds, and physical
references come from. It keeps provenance and permissions visible while the
shared animation core remains reusable across Blender, Roblox, Unity, Unreal,
Godot, and web adapters.

Policy snapshot: 2026-10-28. Licenses, terms, importer behavior, and account
permissions can change; verify them again at the time an external source is
actually used.

The agent owns technical interpretation, mapping, cleanup, and evidence. The
novice user supplies intent and judges the final aesthetic. A source link or a
thumbnail does not prove that its motion was viewed, heard, or legally usable.

## Source order

1. **User-supplied material first — OBSERVED when actually inspected.** Use the
   user's own reference video, pose board, rig, clip, or design brief when it
   answers the target question. Record the exact file/page, segment, frame or
   timestamp, what was seen/heard, and what was adapted. Keep original files
   outside the skill package unless the user explicitly permits an example.
2. **Owned or explicitly licensed material — PROPOSED default fallback.** Prefer
   assets the user owns or has permission to modify. Keep a copy of the license
   or source receipt with the task, not in a generic installed skill. CC0 or
   similarly clear sources such as [Quaternius](https://quaternius.com/) can be
   appropriate for a prototype or reference when the specific pack and current
   license are verified. “Free download” is not a license conclusion.
3. **External library/reference import — permission-gated.** Mixamo can be a
   useful motion reference or import source when the user has the applicable
   Adobe/Mixamo rights. Check the current source terms at the time of use,
   record the clip/source and export settings, and do not bundle raw Mixamo
   clips, meshes, or textures into this skill.
4. **Engine-native examples and official docs — DOCUMENTED reference.** Use
   official Roblox, Unity, Unreal, Godot, or three.js documentation to bind a
   motion principle to an API. A documentation example is not evidence that the
   current project, version, rig, or account can run it.
5. **Papers and research projects — PRINCIPLE ONLY unless bound explicitly.** A
   paper may support a motion, perception, interpolation, retargeting, or
   evaluation principle. It does not prove a production backend, engine API,
   license, asset availability, or current runtime behavior. Link an actual
   implementation/source when claiming that a principle is implemented.

## Provenance ledger

Every adopted source gets a row like this in the task receipt:

| Field | Required content |
| --- | --- |
| `source` | Stable URL or user-file identifier and title |
| `rights` | User-owned, license name/link, CC0, permission receipt, or `unknown` |
| `what_was_inspected` | Image, video segment, audio, paper, code, API, or importer; include timestamp/version when applicable |
| `review_state` | `discovered`, `image_reviewed`, `motion_reviewed`, `audio_reviewed`, `code_reviewed`, or `not_accessible` |
| `observation` | Concrete silhouette, timing, contact, weight, material, rhythm, or implementation fact |
| `adaptation` | What is re-authored or parameterized, and which signature sequence is intentionally avoided |
| `target` | Blender, Roblox, Unity, Unreal, Godot, web, or reference-only |
| `evidence` | `DOCUMENTED`, `OBSERVED`, `SELF_REPORTED`, `PROPOSED`, `TESTED`, `NOT_TESTED`, or `UNKNOWN` |

Do not label a thumbnail `motion_reviewed`. Do not infer a rig map from a
render. Do not infer an audio event from silent footage. If a source could not
be opened, keep it as `not_accessible` and find a different source for the
decision.

## Mixamo and other external libraries

Mixamo may be used as an external reference or an explicitly permitted import;
it is not a raw clip library for this skill. Record account/permission scope,
source clip, target rig, FBX export options, axis/scale settings, and cleanup
performed. The official Mixamo FAQ describes project use, while the published
Mixamo Additional Terms include a restriction on using Mixamo service/content,
data, output, or derived information to create, train, test, or improve AI/ML
systems. That PDF is dated 2021, so treat the restriction as a hard workflow
boundary until the current terms are checked again; do not make a current legal
claim from the old document alone. Never claim that a Mixamo clip is
universally redistributable, royalty-free for every use, or automatically
retargeted. The exact source clip, account permission, and asset license for
any outside post remain **UNKNOWN** until supplied and verified.

Disambiguate `GASP` and `GAS` in the receipt. `GASP` means Epic's **Game
Animation Sample Project**, an optional animation sample/reference project.
`GAS` means the **Gameplay Ability System**, a separate optional runtime
ability system. A clip, screenshot, or social-media post does not prove use of
either. If an earlier interpretation describes a Facebook example as
“Mixamo + GASP,” preserve it as an unverified hypothesis: the exact Mixamo
clip, GASP asset/project, author account, and redistribution rights have not
been established. Do not bundle raw GASP sample content or Gameplay Ability
System dependencies. AI-assisted authorship or use of Claude does not by itself
transfer, clear, or replace the source asset's license. The specific model
provider/account terms, prompts, inputs, and output-rights record for an
outside creator are also **UNKNOWN** from a public post alone.

## Research-to-motion procedure

For a novice-language request, the agent chooses a small source board and
continues through authoring without requiring the user to select topology,
interpolation, or an engine representation. The review order is:

1. Write the visible moment in one sentence: action, force, focal point, and
   intended feeling.
2. Select one or two sources that answer that moment. Inspect the real image or
   temporal segment, not just search metadata.
3. Extract observations: anticipation, contact, peak, settle, weight transfer,
   line of action, silhouette, overlap, camera read, and any event timing.
4. Convert them into original intent/timing/constraint data. Preserve the
   principle, re-author the poses, spacing, names, and secondary details so the
   result is not a copied signature sequence.
5. Bind each semantic channel to the target rig and native runtime. For Roblox,
   choose R6/R15/custom/Bone/constraint route before writing a clip; for other
   engines, use their native controller and event contract.
6. Review realtime and slow motion, then check loop, interruption, markers,
   authority, cleanup, and target-device budget where the task requires them.

Use physical references when they clarify mass, friction, drag, recoil, impact,
or sound. A research paper can justify a spacing or interpolation hypothesis;
the current engine test must still establish whether the chosen API behaves as
expected.

## Hybrid source examples

The following are selection patterns, not claims that a specific creator uses
them:

| Need | Reasonable source mix | Boundary |
| --- | --- | --- |
| Stylized character action | User reference + owned/CC0 base rig + original timing pass | Do not copy a recognizable signature sequence or bundle an unlicensed clip |
| Roblox NPC prototype | User brief + official Roblox rig/API docs + owned/CC0 mesh | Import, retarget, marker, authority, and low-end tests remain separate |
| Unreal ability | User timing reference + official Epic animation docs + project-owned assets | GASP is an optional sample/reference project and GAS is a separate optional runtime system; neither can be inferred from visual style |
| Material/impact study | Real footage or licensed reference + physical explanation/paper | A paper supports a principle, not a final engine implementation |
| Web/three.js preview | User source + owned glTF/GLB + three.js API docs | GLB transport does not prove mixer, root, marker, or controller behavior |

## Rights and delivery boundary

The final receipt should preserve source URLs and licenses without embedding
private account/session information. The skill ships original prose, the
original Luau template, and references; it does not ship user captures, raw
Mixamo/Creator Store/Quaternius libraries, copyrighted sound packs, private
model weights, or unverified research assets. If redistribution is unclear,
deliver a source/recipe/provenance record and ask the owner to supply the
permitted asset in their own project.

## Primary references

- [Quaternius](https://quaternius.com/) — potential CC0 source; verify the
  specific pack and current license before use.
- [Adobe Mixamo](https://www.mixamo.com/) and the [official Mixamo FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)
  — external source/permission context; the exact asset license still needs a
  source-specific check.
- [Mixamo Additional Terms](https://wwwimages2.adobe.com/content/dam/cc/en/legal/servicetou/Mixamo-Addl-Terms-en_US-20210623.pdf)
  — the dated AI/ML restriction that must be checked against current terms
  before using Mixamo-derived data in any AI workflow.
- [Game Animation Sample Project](https://dev.epicgames.com/documentation/en-us/unreal-engine/game-animation-sample-project-in-unreal-engine)
  — official GASP sample/reference context; no raw sample content is bundled.
- [Roblox animation documentation](https://create.roblox.com/docs/animation) —
  target-specific rig, bone, constraint, and marker concepts.
- [Roblox importer](https://create.roblox.com/docs/studio/importer) — FBX/glTF
  import and permission settings.
- [Gameplay Ability System](https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-ability-system-for-unreal-engine)
  — official GAS runtime context; not a dependency of this skill.
- [Khronos glTF specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
  — interchange structure, not proof of target-engine behavior.
- [Blender manual: animation](https://docs.blender.org/manual/en/latest/animation/index.html)
  — Blender source-authoring context, not a target runtime guarantee.
