# Validation and actual coverage

Validation date: 28 October 2026. Tests distinguish package integrity, source
and evaluated scene properties, observed visuals, and native target behavior.
No package validator or self-critique certifies arbitrary aesthetic success.

## Verified environment

- Blender 5.2.0 LTS, build `fbe6228777e7`, Blender Python 3.13.13, macOS.
- Host Python 3.14.3 with Pillow 12.2.0 for local sprite tests.
- Node.js 24.21.0; isolated installer checks use `skills@1.7.4`.
- EEVEE rendering and local ffmpeg/ffprobe are available.

## Reproducible checks

From the public checkout, run:

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/blender-engineering-animation/tests -p 'test_*.py' -v
python3 tools/validate_package.py skills/blender-engineering-modeling
python3 tools/validate_package.py skills/blender-engineering-animation
python3 tools/test_install.py --report install-report.json
python3 tools/package_release.py --output dist/blender-engineering-v0.1.0.zip
```

The authoring checkout keeps `tests`, `docs`, and the skill folders under
`plugin/`; the release is normalized to the paths above. Blender integration
tests skip when no Blender executable is available, with an explicit reason.
The Ubuntu package CI does not establish that Blender ran.

The evidence tests exercise required failures, uncertainty, absent evidence,
invalid/non-finite JSON, hash mismatch, spoofed completeness, and skill path
boundaries. Sprite tests use original synthetic PNGs to check trim offsets,
pivots, durations, loop endpoints, extrusion, atlas rectangles, and timed previews.
They do not establish polished sprite artwork or target-game playback.

The Blender integration tests create real temporary `.blend` files. They check
an unapplied modifier's evaluated geometry, missing dependencies, semantic part
spoofing with an Empty, incorrect units/dimensions, five diagnostic renders,
source preservation, and a GLB imported into a separate Blender process with
finite evaluated geometry bounds. Format signatures alone are insufficient.

## Coverage boundaries

The Blender modeling helper is tested locally. The Cycles fallback, other OSes,
large-scene performance, production character retargeting, simulation caches,
printing and fit are not established by these fixtures. A neutral diagnostic
floor is presentation geometry and is not evidence of source contact.

Animation profile documentation covers Roblox, Unity, Unreal, Godot, Three.js,
sprite workflows, skeletal 2D and vector/interactive tools. Profile coverage
does not mean those applications or receiving runtimes ran. Roblox's Luau
template has a local parse/load check only; Studio playback, publishing,
replication, events and device performance remain `NOT_TESTED`. Rive, Spine,
DragonBones, Aseprite/LibreSprite, Grease Pencil animated SVG and their receiving
players remain `NOT_TESTED` in this release.

Research catalogs are source evidence. Paper timings, external benchmark scores,
practitioner claims, UI clip counts and package tests are separate measurements.

## Recorded local results

The final local suite contains 32 repository tests and 5 sprite tests. All 37
passed on the environment above, with the actual Blender executable present.
Repository coverage includes 13 evidence/path tests, 3 release structure tests,
9 real-Blender modeling tests and 7 animation timing/export/dependency tests.
The release structure suite also extracts a public checkout, rebuilds it, and
compares the complete archive bytes. Both skill entrypoints passed the official
skill-creator validator and the bundled self-containment validator.

The animation fixture has a mesh, two-bone armature, layered Actions and a real
relative image file. Tests confirm source-time preview durations at 30 FPS with
step 2 (0.2 s intended speed, 0.4 s slow), fractional/irregular intervals, fresh
GLB and FBX temporal readback, source preservation, static-export rejection,
missing-dependency failure and explicit optional-dependency reporting. Ordinary
Geometry Nodes and actual simulation-node cache requirements are distinguished.
An externally referenced texture can pass local interchange readback while
`portable_delivery_complete` remains false; the helper does not claim a shipped
recipient bundle from path resolution alone.

The modeling fixture includes an actual relative PNG, linked-library geometry,
an unapplied modifier, a spoofed Empty and far-away presentation helpers. These
test dependency context, evaluated geometry, semantic type/extent checks and
camera fitting against renderable geometry. Camera/light/Empty inspection records
remain available, while their display positions do not inflate asset bounds.

The isolated installer test used `skills@1.7.4`, temporary homes/config/cache,
telemetry disabled and four scenarios: each skill alone, in copy and default-link
modes, for both Codex and Claude Code. It compared every installed resource hash
and checked a relocated standalone skill copy. It did not change the user's
normal installed skills.

## Forward execution cases

Two fresh agent sessions received the skill and one ordinary-language request
each. They created their own source assets, reviewed renders and repaired defects
without user technical coaching. Parent-agent critiques were internal to that
workflow. Every critic used the same model family: these cases are
`SELF_EVAL_ONLY`, not independent human acceptance or a success-rate benchmark.
They do not replace the original 14 unrun development cases in the research plan.

See [the case files and previews](examples/README.md). Each case includes original
procedural source, a native `.blend`, preview evidence and a sanitized integrity
receipt. The lantern case exercises rotational/hard-surface assembly, transparent
materials, multiple views and localized material/scale repair. The drone case
exercises native object animation, cyclic hover/banking, propeller aliasing,
shadow timing and a 6-second rendered sequence.

The drone MP4s were played in Chrome and visually sampled during intended-speed
and slow playback. The receipt lists the observed timestamps; this was not an
exhaustive continuous review of every encoded frame. The pose sheet and evaluated
timeline provide complementary evidence. User taste remains unevaluated.

## Failures retained and limits of the fixes

- An early FBX scene export wrote a file but failed fresh Blender import on
  `CyclesLightSettings.cast_shadow` for a review light. Asset-scoped mesh/rig
  export passed; animated camera/light export is not silently substituted.
- A development preview call failed with a `run_ffmpeg_concat` name error while
  the helper was being revised. Final source-timed video tests execute the actual
  helper and ffprobe, including sampled steps and slow playback.
- Copying only a `.blend` broke relative dependencies. Modeling validation now
  opens the original read-only and verifies before/after hashes. Animation's
  branch is resolved/reopened locally, with portable bundling reported separately.
- Presentation helpers previously inflated modeling render bounds. A real
  far-away-camera/light/Empty regression now checks the fitted geometry bounds.
- Early example reports prefilled `PASS`; all unfilled reports now start at
  `NOT_TESTED`. File gates remain explicitly structural and cannot prove reading,
  image understanding, animation quality or user taste.
- Approximate physical size was initially inconsistent with the visual scale of
  hand-held props. The skills now require coherent inferred units and export
  scale, with measured source dimensions distinguished from assumptions.

Release archive integrity and live GitHub installation are separate distribution
checks. Their machine receipts accompany the release; the GitHub workflow checks
the public package layout and never substitutes for the native local test record.
