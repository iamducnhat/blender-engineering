# Blender Engineering modeling adapter

`scripts/blender_engineering.py` is a portable command-line boundary between
the skill orchestrator and Blender. It does not generate a model from prose.
It discovers and launches Blender, opens a saved `.blend` in a fresh background
process, inspects evaluated scene data, renders neutral diagnostic evidence,
validates a machine-readable contract, and exports a requested file format.

The host side uses Python's standard library only. Blender's `bpy` API is
loaded only inside the owned Blender child process. No add-on, MCP server,
Python package, user home path, API key, or external service is required.

## Executable resolution and lifecycle

Resolution is attempted in this order:

1. `--blender PATH`.
2. `BLENDER_BIN`.
3. `blender` or `blender.exe` on `PATH`.
4. Standard installation paths such as `/Applications/Blender.app/Contents/MacOS/Blender`, `/usr/local/bin/blender`, `/opt/homebrew/bin/blender`, `/usr/bin/blender`, and the standard Windows `PROGRAMFILES` location.

Every operation launches an independent process with:

```text
blender --background --factory-startup [saved.blend] --python blender_engineering.py -- ...
```

The process receives detached stdin, has a finite `--timeout` (180 seconds by
default), and is placed in an owned process group. On timeout the adapter
terminates only that process group, collects a bounded stdout/stderr tail, and
returns `FAIL` with `error.kind = TIMEOUT`. It never kills an already-running
Blender process owned by the user.

The Blender payload writes a JSON receipt to a temporary path. The host reads
that receipt, adds process identity and timing, writes the requested public
receipt, and removes temporary request/result files. A subprocess exit code of
zero is not sufficient for a `PASS`: the payload status and readback gates must
also pass.

## Commands

Run these examples from the installed skill root. The helper path is
`scripts/blender_engineering.py`; from another working directory, use an
absolute path to that helper. Paths in receipts are absolute.

```bash
cd /absolute/path/to/blender-engineering-modeling
python3 scripts/blender_engineering.py \
  probe --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --out /tmp/blender-probe.json
```

`probe` reports the Blender version, build hash, tested background/render
capabilities, exporter operator presence, evaluated-depsgraph availability,
and the type-level `bpy.types.Action.slots` probe. A false type-level slots
value is recorded as an RNA surface observation only; it is not interpreted as
proof that an Action instance lacks the feature.

```bash
python3 scripts/blender_engineering.py \
  inspect --blend /absolute/input/source.blend --out /absolute/inspect.json
```

`inspect` opens the saved source in a fresh process and does not save it. The
receipt contains source and evaluated mesh statistics, finite world transforms
and coordinates, evaluated world bounds/dimensions, units, material slots,
image/library paths, missing external files, scene extents, and a stable
semantic fingerprint. Aggregate `scene_bounds` and render fitting use
evaluated renderable geometry. Mesh, curve, surface, font, and metaball
objects use evaluated `to_mesh()` vertices when Blender exposes them;
`evaluated_stats.bounds_method` records this as `evaluated_mesh_vertices` with
`bounds_exact: true`. A non-mesh bound-box fallback is labeled
`evaluated_bound_box` with `bounds_exact: false`. Camera, light, speaker, and
empty display helpers are excluded unless Blender exposes finite non-zero
evaluated instance bounds. Their object records remain available for type and
semantic contract checks. Selection, active object, workspaces, UI views, and
timestamps are excluded from the stable fingerprint. The exact source bytes
are represented separately by `source_sha256`.

```bash
python3 scripts/blender_engineering.py \
  render --blend /absolute/input/source.blend \
  --out-dir /absolute/task/render-review \
  --views hero,front,side,back,top \
  --resolution 512 --samples 64
```

`render` opens the saved source afresh, creates a temporary camera, neutral
floor, world, and lights in memory, fits the camera to evaluated scene bounds,
and renders a neutral diagnostic PNG pass. This pass supports structural,
camera, framing, and coverage review; it is not the source asset's final
artistic beauty render and is not a user taste verdict. It never saves those
temporary objects into the input `.blend`. The default receipt is
`<out-dir>/receipt.json`; use `--receipt` to choose another path. Existing
named images are protected unless `--force` is supplied.

The temporary floor is placed at the aggregate evaluated minimum Z only to
make silhouettes readable. It can visually mask a floating model, so it is not
support-plane or contact proof. Declare an explicit `floor` contract to test
the source geometry's evaluated bounds against a specified plane.

The render engine preference is EEVEE, followed by the version-compatible
legacy EEVEE identifier, then CPU Cycles. Each image record includes the view,
absolute path, PNG dimensions, byte count, SHA-256, source fingerprint, actual
camera transform, frame, resolution, render engine, requested/applied samples,
and sample-configuration status. A missing setting is `NOT_TESTED`, never an
implicit `PASS`.

```bash
python3 scripts/blender_engineering.py \
  validate --blend /absolute/input/source.blend \
  --contract /absolute/task/contract.json \
  --out /absolute/task/validation.json
```

`validate` opens the source `.blend` read-only in a fresh background process.
This preserves Blender's original dependency context for `//relative` images
and linked libraries without writing a copy beside the source or silently
breaking those paths. The payload performs no save operation; the host records
the source SHA-256 before and after the run and fails closed if the source
changes. The receipt includes `validation_policy` with the dependency context,
source before/after hashes, and `source_unchanged`.

```bash
python3 scripts/blender_engineering.py \
  export --blend /absolute/input/source.blend \
  --format glb --out /absolute/task/model.glb
```

The supported values are `glb`, `fbx`, and `stl`. The source is opened fresh
and is never saved by the export operation. The default receipt is a sidecar
at `<artifact>.<extension>.receipt.json`; use `--receipt` to override it.
Existing artifacts require `--force`. The adapter performs format/header and
non-empty-file readback where practical. It records
`native_engine_verified: false`: a valid GLB/FBX/STL file is not evidence of
native Blender, Roblox, game-engine, or printer playback.

## JSON contract

The contract is a JSON object. All fields are optional, but an omitted check is
reported as `NOT_TESTED`; the adapter does not convert missing evidence into a
pass. A compact hard-surface example is:

```json
{
  "asset_class": "hard_surface",
  "required_parts": [
    {"part_id": "body", "count": 1, "type": "MESH", "min_extent": 0.5},
    {"part_id": "wheel", "count": 2, "type": "MESH", "min_extent": 0.1}
  ],
  "units": {"system": "METRIC", "scale_length": 1.0},
  "dimensions": {"target": [2.0, 1.4, 1.0], "tolerance": 0.01},
  "floor": {
    "z": 0.0,
    "parts": ["Body", "WheelA", "WheelB"],
    "mode": "touch",
    "tolerance": 0.001
  },
  "allow_missing_files": false
}
```

Part matching supports exact object names, wildcard names, regular-expression
`pattern`, custom properties `part_id`, `_be_part_id`, or `semantic_part`, and
collection filters. A matched part must have the expected type, expected count,
and any declared evaluated world extent. Each proof records the object name,
type, extent, and expected values. Semantic part count is not silently equated
with mesh object count when a custom part identifier is available.

`units` compares `system`, `scale_length`, and optionally `length_unit`.
`dimensions` compares evaluated aggregate scene extents using `target`, `min`,
or `max` and an explicit tolerance. `floor` performs only the declared
evaluated world-bound contact test. It does not claim exact mesh intersection.
The adapter deliberately does not implement watertightness, exact
self-intersection, arbitrary clearance, rig validity, UV validity, or native
engine playback. If a contract requests one of those checks with
`watertight`, `self_intersection`, `no_intersection`, `clearance`, `rig`, `uv`,
or `native_engine`, the corresponding result is `NOT_TESTED`.

Missing image and linked-library paths are a hard failure unless
`allow_missing_files` is true. This does not pack assets or repair external
paths. Repair belongs to the orchestrator and must be followed by a fresh
inspect/validate run.

## Receipt semantics

Every receipt has `schema_version`, `tool`, `tool_version`, `operation`,
`request_id`, `generated_at`, Blender version/build data, `source_blend`,
`opened_blend`, and, when applicable, `source_sha256` and
`source_scene_fingerprint`.

`status` means:

- `PASS`: the requested adapter operation completed and all checks included in
  that operation passed.
- `FAIL`: runtime, file, contract, render, export, or declared hard check
  failed.
- `NOT_TESTED`: the requested mechanism was unavailable, not declared, or
  could not be verified. It is never promoted to `PASS`.
- `UNCERTAIN`: an explicit check could not support a deterministic verdict.

For `inspect`, `PASS` means the manifest was produced; it is not an aesthetic
or quality verdict. For `render`, `PASS` requires every requested view to have
decoded PNG dimensions, non-zero bytes, a hash, and configured requested sample
settings. For `validate`, the aggregate status is derived from mandatory
finite-geometry and external-file checks plus checks actually declared in the
contract. Omitted units, dimensions, floor/contact, and required-part checks
remain `NOT_TESTED` in `untested_coverage` and do not block an otherwise
applicable validation. An explicitly requested unsupported check remains
`NOT_TESTED` and does block the aggregate verdict. `declared_check_names`
records the gate inputs. For `export`, `PASS` means the exporter wrote a
non-empty file whose format signature was observed, not that another
application accepted it.

CLI exit codes are `0` for `PASS`, `1` for `FAIL` or `UNCERTAIN`, and `2` for
`NOT_TESTED`. This makes an unverified capability visible to shell orchestration
without pretending it is a hard failure.

## Tested local coverage

The adapter was smoke-tested on **Blender 5.2.0 LTS** using a temporary
`/tmp/be_fixture.blend` containing a body, two wheel parts, metric units, a
deliberately missing image path, and finite evaluated meshes. The tested
operations were:

- `probe`: `PASS`, background/factory startup and exporter capabilities reported.
- `inspect`: `PASS`, source/evaluated statistics, external missing-file report,
  finite checks, stable fingerprint returned, and a beveled CURVE fixture
  matched an independent fresh-Blender evaluated-mesh vertex-bound readback.
- `validate`: `PASS` for a complete contract; `FAIL` for a disallowed missing
  file; unsupported requested checks remained `NOT_TESTED`. A separate fixture
  with a real `//textures/relative.png` and `//libraries/linked_part.blend`
  validated `PASS` with the source opened read-only, equal direct/validated
  geometry fingerprints, and an unchanged source SHA-256. Omitted contract
  checks remained visible in `untested_coverage` without forcing `NOT_TESTED`.
- `render`: `PASS` for hero/front/side/back/top PNGs, with dimensions and hashes;
  temporary camera/floor/lights were not saved to the source. The CPU Cycles
  fallback branch is implemented but was not exercised on this machine because
  EEVEE was available.
- `export`: `PASS` for GLB, FBX, and STL header/non-empty readback; native
  playback remained explicitly unverified.
- finite-timeout path: a 0.001-second probe terminated the owned child and
  returned `FAIL` with `error.kind = TIMEOUT`.

These are local smoke tests, not a claim of universal Blender-version,
platform, renderer, exporter, rig, printer, or game-engine support. The
orchestrator should preserve the receipts, source hash, scene fingerprint, and
output hashes as the evidence for each run.
