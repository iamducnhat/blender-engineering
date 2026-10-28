# Research ledger for Blender Engineering

Cutoff: 2026-10-28 (Asia/Ho_Chi_Minh). This file is the compact map from the read OSINT to skill behavior. The source catalogs hold the evidence detail:

- [`research/animation.md`](research/animation.md) and [`research/animation-sources.json`](research/animation-sources.json) contain the 91-entry animation/craft/platform/rights/paper catalog.
- [`research/modeling.md`](research/modeling.md) and [`research/modeling-sources.json`](research/modeling-sources.json) preserve all 98 source records from the seven-ledger snapshot with original IDs, titles, URLs, read depths, findings, and limitations; `M01`–`M14` are the modeling-specific subset.
- The sanitized [modeling coverage snapshot](research/modeling-coverage.json) preserves the original aggregate counts and deduplication boundaries. The local investigation and raw captures are excluded from the public package.

## Coverage and evidence status

The 2026-10-27 OSINT snapshot contains **98 source records, 94 unique primary URLs, and 18 hosts** across seven ledgers. The 94 URL figure is a deduplication snapshot; it is not a claim that 94 independent experiments were run. The source records preserve distinct evidence scopes even when URLs overlap.

| Ledger | Count in snapshot | What it contributes | Boundary to preserve |
| --- | ---: | --- | --- |
| Agentic (`A`) | 15 | staged Blender agents, scene graphs, generator/verifier loops, executable code, candidate selection | Paper and benchmark results are external evidence, not this plugin's benchmark. |
| Control (`C`) | 16 | official/community MCP topology, main-thread/deferred execution, observation surfaces, failure issues | Connector availability, latency, and runtime behavior remain machine- and version-dependent. |
| Generative (`G`) | 16 | generation routes and model/provider constraints | Use only for route context; no paid generation or provider claim is implied. |
| Modeling (`M`) | 14 | Blender Manual/Studio construction, topology, UVs, geometry nodes, precision, handoff | `M11` is a course index/chapter list; lesson videos were not downloaded or watched. `M12` is a course index/description; lessons were not watched. |
| Practitioner (`P`) | 20 | firsthand novice/pro workflows, failures, bridge problems, self-critique conflicts, public artifact | Anecdotes are valuable failure/experience evidence, not representative success rates. |
| QA (`Q`) | 14 | visual/structural/export validators and judge reliability | `Q08` and `Q09` are abstract/metadata only; no full paper was read in the snapshot. |
| Harness (`R`) | 3 | long-running state, routing, evaluator/optimizer, repeated evaluation | General agent guidance is an inference for Blender until forward tests run. |

The snapshot's read-depth distribution is also part of the evidence: `full` 7, `full_page_or_source` 26, `deep` 15, `anecdotal` 17, `documented_partial` 6, `abstract` 3, `abstract_sections` 4, `sections` 4, `relevant_sections` 3, `artifact_or_repository` 3, `course_index_only` 2, `attempted` 1, and `mixed_source_depths` 3. A catalog entry must retain its actual depth; a title or search snippet is not a full read.

There is no forward benchmark, generated Blender artifact, native Unreal/Unity/Roblox/Rive playback run, or SVG 5.2 runtime test in this research pass. A Blender version probe is only a version probe.

The animation catalog contains **91 records**: 45 reused records (`AN01`–`AN45`), 31 craft/platform/rights/supplied-context records (`AN46`–`AN76`), and 15 focused motion-research/evaluation records (`AN77`–`AN91`). The last group represents 15 distinct primary-paper identities, marked by `study_key`; 13 are the requested motion-generation/retargeting papers and two are the temporal/video-evaluation references already used by the animation playbook. Catalog records and independent studies are different counts. The paper records are abstract-depth evidence unless their entry says otherwise, and none makes a local backend or runtime claim.

## Evidence-to-behavior matrix

The last column describes the limits of the research pass itself. Subsequent
implementation, local Blender runs and forward execution examples are recorded
separately in [VALIDATION.md](VALIDATION.md); source evidence is not a runtime receipt.

| Evidence | Operational behavior required by the skill | What remains unverified |
| --- | --- | --- |
| `P01`, `P02`, `P11`, `P15`, `R01` | Treat one prompt as an autonomous internal run: plain-language intake, hidden technical decomposition, internal blockout/selection, repair, and final delivery. Do not require an intermediate blockout approval. | The novice-facing implementation and its success rate. |
| `P04`, `P08`, `P20`, `P22`, `C02`, `C05`, `C07`, `C11` | Preflight process/add-on/port/tool list and latency; choose direct idempotent scripts for deep loops; use connector calls for compact observation/edits; keep checkpoints and classify transport versus geometry failure. | Current connector install, latency, native Blender bridge behavior, and helper availability. |
| `M01`–`M14`, `P13`, `P16`–`P19` | Route by form and use: profile/revolve, hard surface, organic/retopo, scene/instances, precision/print, or imported/generated hybrid. Preserve source meshes, parameters, and camera/use-specific checks. | General quality or success rate on unseen prompts; the research pass did not generate an artifact. |
| `A01`–`A15`, `Q01`–`Q05` | Separate executable/artifact gates from visual judging; use scene/part graphs, named constraints, stage budgets, active viewpoints, best-of-N or pairwise selection where it pays for itself, and finite repair limits. | External benchmark scores do not transfer to this plugin without a forward evaluation. |
| `P09`, `P15`, `Q06`–`Q09`, `R02`–`R03` | Keep generator and critic evidence separate; use clean multi-view renders, deterministic scene queries, pairwise/repeated judging, order swaps, and `UNCERTAIN` when visual judgments conflict. | A reliable aesthetic oracle for arbitrary assets. |
| `AN46`–`AN48`, `AN51` | Internal critic checks pose/silhouette/staging, timing/spacing, weight, anticipation, follow-through, overlap, easing, loop seam, and audience readability; apply the principle only when the material/style supports it. | Studio lessons and Blender animation runtime were not comprehensively watched/tested. |
| `AN49`–`AN50`, `AN60`–`AN63` | Choose native representation for SVG/Grease Pencil, CSS/Web Animations, or Rive; preserve timeline/source/runtime artifacts and label browser/Rive playback separately. | SVG 5.2 runtime, browser playback, Rive CLI/Editor/runtime. |
| `AN52`–`AN59` | Make rest pose, skeleton mapping, root motion, contact windows, IK chains, clip ranges, masking, and target runtime explicit. Retarget first, then repair contacts and target-specific acting. | Unreal, Unity, and Roblox native checks. |
| `AN64`–`AN75` | Use a hybrid motion policy: approved/CC0 retrieval where it improves quality, custom generation for gaps, transparent provenance, no raw-library redistribution, and no AI training/evaluation use where terms prohibit it. Keep MIT plugin code/docs separate from third-party assets. | A production legal review and every future asset's exact license/version. |
| `AN76` | Treat the supplied Facebook post as an unproven retrieval/retargeting hypothesis. Record that its full caption, four comments, two images, and 13.64 s/62.30 s samples were inspected; treat `1137` as UI self-report only. | Website identity, source clip IDs, backend, licenses, raw skeleton/files, and attribution to a specific tool or creator. |
| `AN77`–`AN82` | Treat MDM/MotionGPT as conditioning and representation cues; use MoMask for localized temporal-editing ideas; compile OmniControl/ProjFlow-style spatial constraints explicitly; inspect FlowMDM-style transition boundaries with intended-speed and diagnostic playback. | No motion-generation backend, checkpoint, sampler, or Blender export was run; paper metrics do not certify this plugin's clips. |
| `AN83`–`AN87` | Classify physics-sensitive actions, two-actor coordination, ordered interaction beats, semantic retargeting, and structure-preserving edits before authoring. Check contacts, partner relations, rest pose, topology, and target-native playback as separate gates. | The papers are human-motion/physics research evidence; no simulator, retargeter, code, dataset, or engine runtime was exercised here. |
| `AN88`–`AN89` | Use inspectable intermediate records: an asset-semantic map plus a coordinated motion plan with parts, axes, temporal chunks, dependencies, and physical assumptions before curves or runtime code. Keep the final user review at the finished-output stage. | MotionAnimator and AgentDreamer are recent paper claims; Unity/MPM implementation, Blender integration, and local aesthetic success remain unverified. |
| `AN90`–`AN91` | Borrow dimensioned temporal/style diagnostics from VBench and AnimationBench for clean previews: identity/semantic consistency, flicker/stability, motion rationality, camera continuity, and context-appropriate animation principles. Keep these as internal diagnostic prompts. | No benchmark package, generated videos, VLM judge, or human-preference protocol was run; these dimensions do not validate curves, deformation, export, rights, or runtime. |

## Behavior that follows from the OSINT

The evidence supports an orchestration contract rather than a magic prompt. The skill should hide Blender vocabulary from the novice while retaining a visible receipt. It should create a task contract, choose a route, preserve a named scene/rig manifest, render before accepting, run structural and target-specific checks, repair from checkpoints, save/reopen/export, and report limitations. The user's role is to judge the complete aesthetic result; technical QA remains the agent's responsibility.

For animation, the semantic core is target-neutral: action intent, key poses, timing, spacing, contacts, root policy, constraints, camera, loop, and provenance. The semantic map and motion plan should be inspectable before target-native curves or code are emitted. The native representation is chosen after target classification. A source clip, editable action, exported clip, and rendered video are separate evidence surfaces. A polished video does not prove mesh topology, rig correctness, source provenance, or native playback.

For modeling, the companion guide highlights the 14 original `M01`–`M14` records and the route/recipe/gate guidance derived from them. Its companion JSON retains all 98 records, including title/URL/read-depth/current-limitation data for the other ledgers; the aggregate is not silently reduced to the 14 modeling records. The deduplicated 94 URL / 18 host values remain a snapshot, not a claim that all records were read at full depth.

## Skill references and helper boundary

The following paths are relevant to implementation:

| Path | Status and use |
| --- | --- |
| [`skills/blender-engineering-modeling/SKILL.md`](../skills/blender-engineering-modeling/SKILL.md) | Present modeling entrypoint; defines the one-prompt contract, route policy, evidence labels, delivery, and helper boundary. |
| [`skills/blender-engineering-modeling/references/research-playbook.md`](../skills/blender-engineering-modeling/references/research-playbook.md) | Present operational playbook; reread at job start/resume. It defines `Observed`, `Self-reported`, `Inferred`, `Proposed`, `Tested`, finite stages, checkpoints, and `PASS`/`FAIL`/`UNCERTAIN`/`NOT_APPLICABLE`/`NOT_TESTED`. |
| [`skills/blender-engineering-animation/SKILL.md`](../skills/blender-engineering-animation/SKILL.md) | Present animation entrypoint; owns one-prompt interpretation, native representation choice, motion craft, repair, provenance, and delivery boundaries. Its presence is not a runtime test result. |
| [`skills/blender-engineering-animation/references/research-playbook.md`](../skills/blender-engineering-animation/references/research-playbook.md) | Present animation research-to-behavior playbook; it preserves the paper, craft, platform, and rights boundaries used by the animation guide. |
| [`skills/blender-engineering-animation/references/motion-craft.md`](../skills/blender-engineering-animation/references/motion-craft.md) | Present craft reference for pose, silhouette, staging, timing, contact, arcs, overlap, and medium-specific interpretation. |
| [`skills/blender-engineering-animation/references/quality-and-delivery.md`](../skills/blender-engineering-animation/references/quality-and-delivery.md) | Present temporal QA/delivery reference; it requires evaluated motion, playback evidence, localized repair, persistence, and explicit `NOT_TESTED` boundaries. |
| [`skills/blender-engineering-animation/scripts/blender_animation.py`](../skills/blender-engineering-animation/scripts/blender_animation.py) | Packaged animation helper present in the skill; this research pass did not execute it or claim a native runtime result. |
| [`skills/blender-engineering-animation/scripts/evidence.py`](../skills/blender-engineering-animation/scripts/evidence.py) | Packaged animation evidence helper present in the skill; structural helper presence is not proof that a report or runtime gate passed. |
| [`skills/blender-engineering-animation/scripts/sprite_pipeline.py`](../skills/blender-engineering-animation/scripts/sprite_pipeline.py) | Packaged sprite helper present in the skill; no sprite or browser runtime was exercised in this pass. |
| [`docs/VALIDATION.md`](VALIDATION.md) | Root-owned validation record for a later implementation/runtime pass; this research file does not mark any runtime gate as passed. |

The installed animation skill must work when installed alone. It may refer to these principles, but it must not depend on the research workspace, private Facebook captures, account/session data, downloaded third-party assets, or unavailable sibling files. The implementation files are present; runtime coverage still belongs in the root-owned validation record.

## Reread record for this documentation pass

Before writing these documents, I reread the project and evidence needed for the scope:

- `AGENTS.md`, `README.md`, `skills/blender-engineering-animation/SKILL.md`, `skills/blender-engineering-modeling/SKILL.md`, and `skills/blender-engineering-modeling/references/research-playbook.md`;
- `skills/blender-engineering-animation/references/research-playbook.md`, `motion-craft.md`, `quality-and-delivery.md`, and `motion-sources.md`, plus the current animation catalog and implementation helpers;
- `research/2026-10-27-one-prompt-3d/OSINT_REPORT.md`, `source-coverage.json`, `SOURCE_CATALOG.md`, `modeling_knowledge.md`, `practitioner_experience.md`, `artifact_case_study.md`, and the seven source ledgers;
- the animation craft handoff covering pose, silhouette, staging, timing, spacing, weight, contact, arcs, overlap, anticipation, follow-through, locomotion, emotion, mechanical/object/camera motion, 2D adaptation, and common AI animation failures;
- the bounded rights handoff for Adobe Mixamo, Epic GASP/Fab, Quaternius, Kenney, and CC0;
- the primary-paper abstract pages for `AN77`–`AN91`, including MDM, MotionGPT, MoMask, OmniControl, ProjFlow, FlowMDM, PhysDiff, InterGen, Text2Interact, SATA, Unified Conditional Flow, MotionAnimator v1, AgentDreamer v1, VBench, and AnimationBench;
- the supplied Facebook observation boundary: full caption/comments/media review summarized as `AN76`, with no raw post/session material copied into release docs.

No browser session, Facebook authentication bypass, asset download, Blender execution, native engine run, installed configuration, GitHub mutation, or paid generation call was used for this documentation update.
