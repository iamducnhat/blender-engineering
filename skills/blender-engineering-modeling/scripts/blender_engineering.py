#!/usr/bin/env python3
"""Portable Blender Engineering modeling adapter.

The host side uses only Python's standard library.  Blender is launched as an
owned, independent background process and re-enters this file as the payload.
The payload writes a JSON receipt instead of relying on Blender's stdout.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import os
import pathlib
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


TOOL_NAME = "blender-engineering"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"
STATUSES = {"PASS", "FAIL", "NOT_TESTED", "UNCERTAIN"}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _json_safe(value: Any) -> Any:
    """Convert values to strict JSON, replacing non-finite floats with null."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, pathlib.Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _write_json(path: pathlib.Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_json_safe(value), handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _read_json(path: pathlib.Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sha256_file(path: pathlib.Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_blender(explicit: Optional[str]) -> Optional[pathlib.Path]:
    """Resolve a Blender executable without assuming a user's home directory."""
    candidates: List[pathlib.Path] = []
    if explicit:
        candidates.append(pathlib.Path(explicit).expanduser())
    env_binary = os.environ.get("BLENDER_BIN")
    if env_binary:
        candidates.append(pathlib.Path(env_binary).expanduser())
    for name in ("blender", "blender.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(pathlib.Path(found))
    candidates.extend(
        [
            pathlib.Path("/Applications/Blender.app/Contents/MacOS/Blender"),
            pathlib.Path("/Applications/Blender.app/Contents/MacOS/blender"),
            pathlib.Path("/usr/local/bin/blender"),
            pathlib.Path("/opt/homebrew/bin/blender"),
            pathlib.Path("/usr/bin/blender"),
        ]
    )
    program_files = os.environ.get("PROGRAMFILES")
    if program_files:
        candidates.append(pathlib.Path(program_files) / "Blender Foundation" / "Blender" / "blender.exe")
    # A standard macOS installation can have a versioned app name.  This does
    # not inspect a home directory and remains deterministic under /Applications.
    candidates.extend(sorted(pathlib.Path("/Applications").glob("Blender*.app/Contents/MacOS/Blender")))
    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate.absolute()
        if str(resolved) in seen:
            continue
        seen.add(str(resolved))
        if resolved.is_file() and (os.access(resolved, os.X_OK) or os.name == "nt"):
            return resolved
    return None


def _tail(text: Optional[bytes], limit: int = 5000) -> str:
    if not text:
        return ""
    return text.decode("utf-8", errors="replace")[-limit:]


def _terminate_owned(proc: subprocess.Popen[bytes], grace: float = 3.0) -> None:
    """Terminate only the process group created by this adapter."""
    try:
        if os.name != "nt":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait(timeout=grace)
        return
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        if os.name != "nt":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass


def _host_failure(operation: str, reason: str, **extra: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "operation": operation,
        "status": "FAIL",
        "generated_at": _now(),
        "error": {"kind": reason, **extra},
    }
    return result


def _load_contract(value: str) -> Dict[str, Any]:
    if value.lstrip().startswith("{"):
        loaded = json.loads(value)
    else:
        loaded = _read_json(pathlib.Path(value).expanduser().resolve())
    if not isinstance(loaded, dict):
        raise ValueError("contract must be a JSON object")
    return loaded


def _normalise_export_path(path: pathlib.Path, export_format: str) -> pathlib.Path:
    suffix = {"glb": ".glb", "fbx": ".fbx", "stl": ".stl"}[export_format]
    if path.suffix.lower() != suffix:
        if path.suffix:
            raise ValueError(f"output extension must be {suffix} for --format {export_format}")
        path = path.with_suffix(suffix)
    return path


def _run_blender(
    operation: str,
    args: argparse.Namespace,
    request: Dict[str, Any],
    blend_path: Optional[pathlib.Path],
    output_receipt: Optional[pathlib.Path],
) -> Dict[str, Any]:
    binary = _resolve_blender(getattr(args, "blender", None))
    if binary is None:
        result = {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "operation": operation,
            "status": "NOT_TESTED",
            "generated_at": _now(),
            "error": {
                "kind": "BLENDER_NOT_FOUND",
                "message": "No executable was found via --blender, BLENDER_BIN, PATH, or standard installation paths.",
            },
        }
        if output_receipt:
            _write_json(output_receipt, result)
        return result

    temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="blender-engineering-run-"))
    request_file = temp_dir / "request.json"
    result_file = temp_dir / "result.json"
    source_path = blend_path
    try:
        if operation == "validate" and blend_path is not None:
            # Blender resolves `//relative/path` and linked-library paths from
            # the saved blend's own directory.  Opening a bare copy in the
            # request temp directory silently breaks that dependency context.
            # Validation is read-only in this payload, so open the original
            # source in a fresh background process instead.  The host records
            # a before/after SHA-256 and fails closed if anything changes.
            blend_for_process = blend_path
            request["validation_policy"] = {
                "mode": "source_read_only",
                "dependency_context": "original_blend_directory",
                "source_write": "prohibited",
            }
        else:
            blend_for_process = blend_path
        request["source_blend"] = str(source_path) if source_path else None
        request["request_id"] = uuid.uuid4().hex
        _write_json(request_file, request)

        script_path = pathlib.Path(__file__).resolve()
        command = [str(binary), "--background", "--factory-startup"]
        if blend_for_process is not None:
            command.append(str(blend_for_process))
        command.extend(
            [
                "--python",
                str(script_path),
                "--",
                "--blender-payload",
                "--request",
                str(request_file),
                "--result",
                str(result_file),
            ]
        )
        started = time.monotonic()
        proc = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(temp_dir),
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=float(args.timeout))
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            _terminate_owned(proc)
            stdout, stderr = proc.communicate()
            stdout = (exc.stdout or b"") + (stdout or b"")
            stderr = (exc.stderr or b"") + (stderr or b"")
        elapsed = round(time.monotonic() - started, 3)

        execution = {
            "command": command,
            "owned_process": True,
            "exit_code": proc.returncode,
            "elapsed_seconds": elapsed,
            "timeout_seconds": float(args.timeout),
            "timed_out": timed_out,
            "stdout_tail": _tail(stdout),
            "stderr_tail": _tail(stderr),
        }
        if result_file.exists():
            try:
                result = _read_json(result_file)
            except (OSError, ValueError) as exc:
                result = _host_failure(operation, "INVALID_PAYLOAD_RECEIPT", message=str(exc))
        else:
            result = _host_failure(
                operation,
                "PAYLOAD_RECEIPT_MISSING",
                message="Blender exited without writing its JSON receipt.",
            )
        if not isinstance(result, dict):
            result = _host_failure(operation, "INVALID_PAYLOAD_RECEIPT", message="receipt was not an object")
        result["execution"] = execution
        if timed_out:
            result["status"] = "FAIL"
            result["error"] = {"kind": "TIMEOUT", "message": "Owned Blender process exceeded the finite timeout."}
        elif proc.returncode != 0:
            result["status"] = "FAIL"
            result["error"] = {
                "kind": "BLENDER_EXIT_NONZERO",
                "message": "Owned Blender process exited non-zero; payload status was not accepted as success.",
                "payload_status": result.get("status"),
            }
        if operation == "validate" and source_path is not None:
            try:
                source_sha256_after = _sha256_file(source_path)
                source_unchanged = source_sha256_after == request.get("source_sha256")
                validation_policy = dict(request.get("validation_policy") or {})
                validation_policy["source_sha256_before"] = request.get("source_sha256")
                validation_policy["source_sha256_after"] = source_sha256_after
                validation_policy["source_unchanged"] = source_unchanged
                result["validation_policy"] = validation_policy
                if not source_unchanged:
                    result["status"] = "FAIL"
                    result["error"] = {
                        "kind": "SOURCE_CHANGED_DURING_VALIDATION",
                        "message": "The source .blend changed while validation was running.",
                    }
            except OSError as exc:
                result["status"] = "FAIL"
                result["error"] = {
                    "kind": "SOURCE_READBACK_FAILED",
                    "message": str(exc),
                }
        if output_receipt:
            _write_json(output_receipt, result)
        return result
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--blender", help="Blender executable; otherwise BLENDER_BIN, PATH, and standard paths are tried.")
    parser.add_argument("--timeout", type=float, default=180.0, help="Finite owned-process timeout in seconds.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable Blender background inspection, render, validation, and export adapter.")
    parser.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")
    commands = parser.add_subparsers(dest="command", required=True)

    probe = commands.add_parser("probe", help="Probe Blender runtime and available adapter capabilities.")
    _add_common(probe)
    probe.add_argument("--out", type=pathlib.Path, help="Optional JSON receipt path.")

    inspect = commands.add_parser("inspect", help="Inspect source and evaluated scene state without saving it.")
    _add_common(inspect)
    inspect.add_argument("--blend", required=True, type=pathlib.Path)
    inspect.add_argument("--out", required=True, type=pathlib.Path)

    render = commands.add_parser("render", help="Render clean multi-view evidence from a fresh saved blend.")
    _add_common(render)
    render.add_argument("--blend", required=True, type=pathlib.Path)
    render.add_argument("--out-dir", required=True, type=pathlib.Path)
    render.add_argument("--views", default="hero,front,side,back,top")
    render.add_argument("--resolution", type=int, default=512)
    render.add_argument("--samples", type=int, default=64)
    render.add_argument("--receipt", type=pathlib.Path)
    render.add_argument("--force", action="store_true", help="Allow replacing named render files in the output directory.")

    validate = commands.add_parser("validate", help="Validate a source blend read-only against a class-aware JSON contract.")
    _add_common(validate)
    validate.add_argument("--blend", required=True, type=pathlib.Path)
    validate.add_argument("--contract", required=True, help="Contract JSON path or inline JSON object.")
    validate.add_argument("--out", required=True, type=pathlib.Path)

    export = commands.add_parser("export", help="Export the saved source blend to GLB, FBX, or STL.")
    _add_common(export)
    export.add_argument("--blend", required=True, type=pathlib.Path)
    export.add_argument("--format", required=True, choices=("glb", "fbx", "stl"))
    export.add_argument("--out", required=True, type=pathlib.Path)
    export.add_argument("--receipt", type=pathlib.Path)
    export.add_argument("--force", action="store_true", help="Allow replacing an existing export artifact.")
    return parser


def _absolute_file(path: pathlib.Path, label: str) -> pathlib.Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    return resolved


def _host_main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    operation = args.command
    receipt: Optional[pathlib.Path] = None
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    try:
        if operation == "probe":
            receipt = args.out.expanduser().resolve() if args.out else None
            result = _run_blender(operation, args, {"operation": operation}, None, receipt)
        else:
            blend = _absolute_file(args.blend, "blend")
            source_sha = _sha256_file(blend)
            if operation == "inspect":
                receipt = args.out.expanduser().resolve()
                request = {"operation": operation, "source_sha256": source_sha}
            elif operation == "validate":
                receipt = args.out.expanduser().resolve()
                contract = _load_contract(args.contract)
                request = {"operation": operation, "source_sha256": source_sha, "contract": contract}
            elif operation == "render":
                if args.resolution <= 0 or args.samples <= 0:
                    parser.error("--resolution and --samples must be positive")
                out_dir = args.out_dir.expanduser().resolve()
                out_dir.mkdir(parents=True, exist_ok=True)
                receipt = (args.receipt.expanduser().resolve() if args.receipt else out_dir / "receipt.json")
                views = [v.strip().lower() for v in args.views.split(",") if v.strip()]
                allowed = {"hero", "front", "side", "back", "top"}
                unknown = sorted(set(views) - allowed)
                if not views or unknown:
                    parser.error(f"--views must use hero,front,side,back,top; unknown={unknown}")
                request = {
                    "operation": operation,
                    "source_sha256": source_sha,
                    "out_dir": str(out_dir),
                    "views": views,
                    "resolution": args.resolution,
                    "samples": args.samples,
                    "force": bool(args.force),
                }
            elif operation == "export":
                out = _normalise_export_path(args.out.expanduser().resolve(), args.format)
                if out == blend:
                    raise ValueError("export output must not overwrite the source blend")
                out.parent.mkdir(parents=True, exist_ok=True)
                if out.exists() and not args.force:
                    raise FileExistsError(f"export output exists; use --force to replace: {out}")
                receipt = args.receipt.expanduser().resolve() if args.receipt else pathlib.Path(str(out) + ".receipt.json")
                request = {
                    "operation": operation,
                    "source_sha256": source_sha,
                    "format": args.format,
                    "out": str(out),
                    "force": bool(args.force),
                }
            else:
                raise ValueError(f"unsupported operation {operation}")
            result = _run_blender(operation, args, request, blend, receipt)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = _host_failure(operation, "HOST_INPUT_ERROR", message=str(exc))
        if receipt:
            _write_json(receipt, result)

    print(json.dumps(_json_safe(result), indent=2, sort_keys=True, allow_nan=False))
    status = result.get("status")
    return 0 if status == "PASS" else 2 if status == "NOT_TESTED" else 1


# ---------------------------------------------------------------------------
# Blender payload.  This section is imported only inside a Blender process.


def _payload_args() -> argparse.Namespace:
    marker = sys.argv.index("--") if "--" in sys.argv else 0
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--blender-payload", action="store_true")
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    return parser.parse_args(sys.argv[marker + 1 :])


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _vec(values: Iterable[Any]) -> List[Optional[float]]:
    return [float(v) if _finite(v) else None for v in values]


def _matrix(matrix: Any) -> List[List[Optional[float]]]:
    return [[float(v) if _finite(v) else None for v in row] for row in matrix]


def _bounds(points: Iterable[Any]) -> Optional[Dict[str, Any]]:
    points = list(points)
    if not points:
        return None
    values = [[float(p[i]) for i in range(3)] for p in points]
    finite = all(_finite(value) for point in values for value in point)
    if not finite:
        return {"min": _vec((0.0, 0.0, 0.0)), "max": _vec((0.0, 0.0, 0.0)), "finite": False}
    minimum = [min(point[i] for point in values) for i in range(3)]
    maximum = [max(point[i] for point in values) for i in range(3)]
    return {
        "min": minimum,
        "max": maximum,
        "dimensions": [maximum[i] - minimum[i] for i in range(3)],
        "finite": True,
    }


def _material_paths(material: Any, bpy: Any) -> List[Dict[str, Any]]:
    paths: List[Dict[str, Any]] = []
    node_tree = getattr(material, "node_tree", None)
    if not node_tree:
        return paths
    for node in node_tree.nodes:
        if getattr(node, "type", "") != "TEX_IMAGE" or not getattr(node, "image", None):
            continue
        image = node.image
        raw = str(getattr(image, "filepath", "") or "")
        if not raw:
            continue
        try:
            absolute = bpy.path.abspath(raw)
        except Exception:
            absolute = raw
        packed = bool(getattr(image, "packed_file", None))
        paths.append({"image": image.name, "path": absolute, "packed": packed, "exists": packed or os.path.exists(absolute)})
    return paths


def _external_files(bpy: Any) -> Dict[str, Any]:
    entries: Dict[str, Dict[str, Any]] = {}
    for image in bpy.data.images:
        raw = str(getattr(image, "filepath", "") or "")
        if not raw:
            continue
        try:
            path = bpy.path.abspath(raw)
        except Exception:
            path = raw
        packed = bool(getattr(image, "packed_file", None))
        entries[path] = {"path": path, "kind": "image", "packed": packed, "exists": packed or os.path.exists(path)}
    for library in bpy.data.libraries:
        raw = str(getattr(library, "filepath", "") or "")
        if not raw:
            continue
        try:
            path = bpy.path.abspath(raw)
        except Exception:
            path = raw
        entries[path] = {"path": path, "kind": "library", "packed": False, "exists": os.path.exists(path)}
    values = [entries[key] for key in sorted(entries)]
    return {"files": values, "missing": [item["path"] for item in values if not item["exists"] and not item["packed"]]}


def _source_mesh_stats(obj: Any) -> Dict[str, Any]:
    data = getattr(obj, "data", None)
    if data is None:
        return {"available": False}
    result: Dict[str, Any] = {"available": True, "data_name": getattr(data, "name", None)}
    for attribute, key in (("vertices", "vertices"), ("edges", "edges"), ("polygons", "polygons"), ("loops", "loops")):
        collection = getattr(data, attribute, None)
        if collection is not None:
            result[key] = len(collection)
    if hasattr(data, "splines"):
        result["splines"] = len(data.splines)
    return result


def _evaluated_geometry(obj: Any, depsgraph: Any, bpy: Any, Vector: Any) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], int]:
    """Return evaluated stats, world bounds, and a non-finite count."""
    evaluated = obj.evaluated_get(depsgraph)
    nonfinite = 0
    meshable_types = {"MESH", "CURVE", "SURFACE", "FONT", "META"}
    if obj.type in meshable_types:
        mesh = None
        try:
            mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
            world_points = []
            for vertex in mesh.vertices:
                if not all(_finite(component) for component in vertex.co):
                    nonfinite += 1
                point = evaluated.matrix_world @ Vector(vertex.co)
                if not all(_finite(component) for component in point):
                    nonfinite += 1
                world_points.append(point)
            stats = {
                "available": True,
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
                "loops": len(mesh.loops),
                "data_name": getattr(mesh, "name", None),
                "bounds_method": "evaluated_mesh_vertices",
                "bounds_exact": True,
                "source_object_type": obj.type,
            }
            return stats, _bounds(world_points), nonfinite
        except Exception as exc:
            mesh_error = str(exc)
        finally:
            if mesh is not None:
                try:
                    evaluated.to_mesh_clear()
                except Exception:
                    pass
    else:
        mesh_error = None
    try:
        corners = [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
        for point in corners:
            if not all(_finite(component) for component in point):
                nonfinite += 1
        stats = {
            "available": True,
            "type": obj.type,
            "bounds_method": "evaluated_bound_box",
            "bounds_exact": False,
        }
        if mesh_error:
            stats["mesh_conversion_error"] = mesh_error
        return stats, _bounds(corners), nonfinite
    except Exception as exc:
        details = {"available": False, "error": str(exc), "bounds_method": "unavailable", "bounds_exact": False}
        if mesh_error:
            details["mesh_conversion_error"] = mesh_error
        return details, None, nonfinite + 1


def _renderable_for_bounds(obj: Any, evaluated_stats: Dict[str, Any], world_bounds: Optional[Dict[str, Any]]) -> bool:
    """Whether this record contributes to fitted scene geometry bounds.

    Object records remain complete for inspection and contract matching.  The
    aggregate fit bounds deliberately exclude presentation helpers whose
    transforms are not asset geometry.  Meshes retain their evaluated output,
    including modifier/geometry-node results; collection/other instancers are
    included only when Blender exposes finite non-zero evaluated bounds.
    """

    object_type = str(getattr(obj, "type", ""))
    if object_type in {"CAMERA", "LIGHT", "SPEAKER"}:
        return False
    if object_type == "EMPTY":
        instance_type = str(getattr(obj, "instance_type", "NONE"))
        if instance_type == "NONE":
            return False
        if not world_bounds or not world_bounds.get("finite"):
            return False
        dimensions = world_bounds.get("dimensions") or []
        # A collection/object instance is included only when the evaluated
        # bound is non-zero.  If Blender does not expose instance bounds here,
        # the manifest keeps the record and reports that fit bounds were not
        # proven from this Empty rather than using its display helper bounds.
        return any(_finite(value) and float(value) > 0.0 for value in dimensions)
    if object_type == "MESH":
        return bool(evaluated_stats.get("available") and int(evaluated_stats.get("vertices", 0)) > 0)
    if not world_bounds or not world_bounds.get("finite"):
        return False
    dimensions = world_bounds.get("dimensions") or []
    return any(_finite(value) and float(value) > 0.0 for value in dimensions)


def _object_record(obj: Any, depsgraph: Any, bpy: Any, Vector: Any) -> Dict[str, Any]:
    world_matrix = _matrix(obj.matrix_world)
    transform_values = [component for row in world_matrix for component in row]
    nonfinite = sum(1 for component in transform_values if component is None)
    evaluated_stats, world_bounds, geometry_nonfinite = _evaluated_geometry(obj, depsgraph, bpy, Vector)
    nonfinite += geometry_nonfinite
    renderable_for_bounds = _renderable_for_bounds(obj, evaluated_stats, world_bounds)
    dimensions = list(obj.dimensions) if hasattr(obj, "dimensions") else []
    if any(not _finite(value) for value in dimensions):
        nonfinite += 1
    materials = []
    for slot in getattr(obj, "material_slots", []):
        material = slot.material
        if material is not None:
            materials.append({"name": material.name, "external_files": _material_paths(material, bpy)})
    custom_part = None
    for key in ("_be_part_id", "part_id", "semantic_part"):
        if key in obj:
            custom_part = str(obj[key])
            break
    return {
        "name": obj.name,
        "type": obj.type,
        "data_name": getattr(getattr(obj, "data", None), "name", None),
        "parent": obj.parent.name if obj.parent else None,
        "part_id": custom_part,
        "collection_names": sorted(collection.name for collection in obj.users_collection),
        "hide_render": bool(obj.hide_render),
        "hide_viewport": bool(obj.hide_viewport),
        "world_matrix": world_matrix,
        "world_dimensions": _vec(dimensions),
        "world_bounds": world_bounds,
        "renderable_for_bounds": renderable_for_bounds,
        "source_stats": _source_mesh_stats(obj),
        "evaluated_stats": evaluated_stats,
        "materials": materials,
        "nonfinite_count": nonfinite,
    }


def _scene_units(scene: Any) -> Dict[str, Any]:
    units = getattr(scene, "unit_settings", None)
    if units is None:
        return {"system": "NONE", "scale_length": 1.0, "length_unit": "NONE"}
    return {
        "system": str(getattr(units, "system", "NONE")),
        "scale_length": float(getattr(units, "scale_length", 1.0)),
        "length_unit": str(getattr(units, "length_unit", "NONE")),
        "rotation_unit": str(getattr(units, "system_rotation", "AUTO")),
    }


def _aggregate_bounds(records: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    points = []
    for record in records:
        if not record.get("renderable_for_bounds", True):
            continue
        bounds = record.get("world_bounds")
        if bounds and bounds.get("finite"):
            points.extend([bounds["min"], bounds["max"]])
    return _bounds(points)


def _stable_fingerprint(scene: Any, records: List[Dict[str, Any]], units: Dict[str, Any]) -> str:
    stable_objects = []
    for record in records:
        stable_objects.append(
            {
                "name": record["name"],
                "type": record["type"],
                "data_name": record["data_name"],
                "parent": record["parent"],
                "part_id": record["part_id"],
                "collection_names": record["collection_names"],
                "hide_render": record["hide_render"],
                "world_matrix": record["world_matrix"],
                "world_dimensions": record["world_dimensions"],
                "world_bounds": record["world_bounds"],
                "renderable_for_bounds": record["renderable_for_bounds"],
                "source_stats": record["source_stats"],
                "evaluated_stats": record["evaluated_stats"],
                "materials": record["materials"],
            }
        )
    payload = {
        "fingerprint_schema": "scene-fingerprint-v1",
        "units": units,
        "evaluation_frame": int(scene.frame_current),
        "camera_name": scene.camera.name if scene.camera else None,
        "collections": sorted(collection.name for collection in scene.collection.children),
        "objects": sorted(stable_objects, key=lambda item: (item["name"], item["type"])),
    }
    encoded = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _inspect_scene(bpy: Any, Vector: Any) -> Dict[str, Any]:
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    records = [_object_record(obj, depsgraph, bpy, Vector) for obj in sorted(scene.objects, key=lambda item: item.name)]
    units = _scene_units(scene)
    external = _external_files(bpy)
    nonfinite = sum(int(record["nonfinite_count"]) for record in records)
    manifest = {
        "filepath": os.path.abspath(bpy.data.filepath) if bpy.data.filepath else None,
        "is_saved": bool(bpy.data.filepath),
        "is_dirty": bool(getattr(bpy.data, "is_dirty", False)),
        "evaluation_frame": int(scene.frame_current),
        "units": units,
        "camera": scene.camera.name if scene.camera else None,
        "collections": sorted(collection.name for collection in scene.collection.children),
        "objects": records,
        "scene_bounds": _aggregate_bounds(records),
        "bounds_policy": {
            "aggregation": "evaluated_renderable_geometry_only",
            "excluded_helper_types": ["CAMERA", "LIGHT", "SPEAKER", "EMPTY_without_evaluated_instance_bounds"],
            "object_records_preserved": True,
        },
        "external_files": external,
        "finite_world_geometry": {"status": "PASS" if nonfinite == 0 else "FAIL", "nonfinite_count": nonfinite},
        "stable_fingerprint": _stable_fingerprint(scene, records, units),
    }
    return manifest


def _base_report(request: Dict[str, Any], bpy: Any) -> Dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "operation": request.get("operation"),
        "status": "PASS",
        "generated_at": _now(),
        "request_id": request.get("request_id"),
        "source_blend": request.get("source_blend"),
        "opened_blend": os.path.abspath(bpy.data.filepath) if bpy.data.filepath else None,
        "source_sha256": request.get("source_sha256"),
        "blender": {
            "version": bpy.app.version_string,
            "version_tuple": list(bpy.app.version),
            "build_hash": _text(bpy.app.build_hash),
            "binary_path": bpy.app.binary_path,
        },
        "warnings": [],
    }
    if request.get("validation_policy") is not None:
        report["validation_policy"] = request["validation_policy"]
    return report


def _probe(bpy: Any, request: Dict[str, Any]) -> Dict[str, Any]:
    report = _base_report(request, bpy)
    scene = bpy.context.scene
    original_engine = scene.render.engine
    engine_results = {}
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            scene.render.engine = candidate
            engine_results[candidate] = True
        except Exception as exc:
            engine_results[candidate] = False
    try:
        scene.render.engine = original_engine
    except Exception:
        pass
    action_type = getattr(bpy.types, "Action", None)
    report["capabilities"] = {
        "background": True,
        "factory_startup": True,
        "evaluated_depsgraph": hasattr(bpy.context, "evaluated_depsgraph_get"),
        "render_engines_tested": engine_results,
        "exporters": {
            "gltf": hasattr(bpy.ops.export_scene, "gltf"),
            "fbx": hasattr(bpy.ops.export_scene, "fbx"),
            "stl_new": hasattr(bpy.ops.wm, "stl_export"),
            "stl_legacy": hasattr(bpy.ops.export_mesh, "stl"),
        },
        "action_slots_type_attribute": bool(action_type and hasattr(action_type, "slots")),
        "action_slots_note": "RNA type-level probe only; inspect Action instances before making feature claims.",
    }
    report["scene_defaults"] = {"object_count": len(scene.objects), "render_engine_restored": scene.render.engine}
    return report


def _inspect_operation(bpy: Any, Vector: Any, request: Dict[str, Any]) -> Dict[str, Any]:
    report = _base_report(request, bpy)
    report["inspection"] = _inspect_scene(bpy, Vector)
    report["status"] = "PASS"
    return report


def _check(status: str, message: str, **evidence: Any) -> Dict[str, Any]:
    return {"status": status, "message": message, "evidence": evidence}


def _status_from_checks(checks: Dict[str, Dict[str, Any]]) -> str:
    statuses = [item.get("status") for item in checks.values()]
    if "FAIL" in statuses:
        return "FAIL"
    if "NOT_TESTED" in statuses:
        return "NOT_TESTED"
    if "UNCERTAIN" in statuses:
        return "UNCERTAIN"
    return "PASS"


def _match_record(record: Dict[str, Any], spec: Dict[str, Any]) -> bool:
    name = str(spec.get("name", ""))
    pattern = spec.get("pattern")
    part_id = spec.get("part_id") or spec.get("semantic_part")
    if part_id is not None and record.get("part_id") != str(part_id):
        return False
    if name:
        if any(char in name for char in "*?["):
            if not fnmatch.fnmatchcase(record["name"], name):
                return False
        elif record["name"] != name and record.get("part_id") != name:
            return False
    if pattern:
        import re

        if not re.search(str(pattern), record["name"]):
            return False
    collection = spec.get("collection")
    if collection and collection not in record.get("collection_names", []):
        return False
    return True


def _extent_satisfies(extent: Optional[List[Any]], minimum: Any = None, maximum: Any = None) -> bool:
    if not extent or any(value is None for value in extent):
        return False
    values = [float(value) for value in extent]
    if minimum is not None:
        mins = [float(minimum)] * 3 if not isinstance(minimum, (list, tuple)) else [float(v) for v in minimum]
        if any(values[i] < mins[i] for i in range(3)):
            return False
    if maximum is not None:
        maxs = [float(maximum)] * 3 if not isinstance(maximum, (list, tuple)) else [float(v) for v in maximum]
        if any(values[i] > maxs[i] for i in range(3)):
            return False
    return True


def _validate_contract(manifest: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    checks: Dict[str, Dict[str, Any]] = {}
    declared_check_names = {"contract_loaded", "finite_world_geometry", "missing_external_files"}
    checks["contract_loaded"] = _check("PASS", "Contract JSON object loaded.", asset_class=contract.get("asset_class", "generic"))
    finite = manifest["finite_world_geometry"]
    checks["finite_world_geometry"] = _check(
        finite["status"],
        "All inspected world transforms and evaluated mesh coordinates are finite.",
        nonfinite_count=finite.get("nonfinite_count", 0),
    )

    required_declared = "required_parts" in contract or bool(contract.get("counts"))
    if required_declared:
        declared_check_names.add("required_parts")
    required = contract.get("required_parts", [])
    if isinstance(required, dict):
        required = [{"name": name, "count": count} for name, count in required.items()]
    if not isinstance(required, list):
        checks["required_parts"] = _check("FAIL", "required_parts must be a list or object mapping names to counts.")
        required = []
    records = manifest["objects"]
    required_specs: List[Dict[str, Any]] = []
    for item in required:
        required_specs.append({"name": item} if isinstance(item, str) else dict(item))
    for name, count in (contract.get("counts") or {}).items():
        required_specs.append({"name": name, "count": count})
    if not required_specs:
        checks["required_parts"] = _check("NOT_TESTED", "No required part or count was declared; presence cannot be proven.")
    else:
        part_results = []
        for spec in required_specs:
            matches = [record for record in records if _match_record(record, spec)]
            expected_count = int(spec.get("count", 1))
            item_status = "PASS" if len(matches) == expected_count else "FAIL"
            details: Dict[str, Any] = {
                "spec": spec,
                "expected_count": expected_count,
                "actual_count": len(matches),
                "matched": [{"name": record["name"], "type": record["type"], "extent": record.get("world_bounds", {}).get("dimensions") if record.get("world_bounds") else None} for record in matches],
            }
            expected_type = spec.get("type")
            if expected_type:
                expected_type = str(expected_type).upper()
                if any(record["type"] != expected_type for record in matches):
                    item_status = "FAIL"
                    details["type_error"] = expected_type
            minimum = spec.get("min_extent", spec.get("min_dimension"))
            maximum = spec.get("max_extent", spec.get("max_dimension"))
            if (minimum is not None or maximum is not None) and any(
                not _extent_satisfies(record.get("world_bounds", {}).get("dimensions") if record.get("world_bounds") else None, minimum, maximum)
                for record in matches
            ):
                item_status = "FAIL"
                details["extent_error"] = {"minimum": minimum, "maximum": maximum}
            if spec.get("floor_contact") is True:
                details["floor_contact_requested"] = True
            part_results.append(_check(item_status, "Required part count/type/extent proof.", **details))
        checks["required_parts"] = _check(
            "FAIL" if any(item["status"] == "FAIL" for item in part_results) else "PASS",
            "All declared required part proofs evaluated.",
            parts=part_results,
        )

    units_spec = contract.get("units")
    if units_spec:
        declared_check_names.add("units")
        actual_units = manifest["units"]
        unit_status = "PASS"
        differences = {}
        for key in ("system", "length_unit"):
            if key in units_spec and str(units_spec[key]).upper() != str(actual_units.get(key)).upper():
                unit_status = "FAIL"
                differences[key] = {"expected": units_spec[key], "actual": actual_units.get(key)}
        if "scale_length" in units_spec and abs(float(units_spec["scale_length"]) - float(actual_units["scale_length"])) > float(units_spec.get("tolerance", 1e-6)):
            unit_status = "FAIL"
            differences["scale_length"] = {"expected": units_spec["scale_length"], "actual": actual_units["scale_length"]}
        checks["units"] = _check(unit_status, "Declared unit contract compared with scene units.", actual=actual_units, differences=differences)
    else:
        checks["units"] = _check("NOT_TESTED", "No units contract was declared.", actual=manifest["units"])

    dimensions_spec = contract.get("dimensions")
    if dimensions_spec:
        declared_check_names.add("dimensions")
        actual = manifest.get("scene_bounds")
        dimension_status = "PASS"
        differences = {}
        actual_dimensions = actual.get("dimensions") if actual else None
        if actual_dimensions is None:
            dimension_status = "FAIL"
        else:
            tolerance = float(dimensions_spec.get("tolerance", 1e-4))
            if dimensions_spec.get("target") is not None:
                target = [float(value) for value in dimensions_spec["target"]]
                if any(abs(actual_dimensions[i] - target[i]) > tolerance for i in range(3)):
                    dimension_status = "FAIL"
                    differences["target"] = {"expected": target, "actual": actual_dimensions}
            if dimensions_spec.get("min") is not None and any(actual_dimensions[i] < float(dimensions_spec["min"][i]) for i in range(3)):
                dimension_status = "FAIL"
                differences["min"] = {"expected": dimensions_spec["min"], "actual": actual_dimensions}
            if dimensions_spec.get("max") is not None and any(actual_dimensions[i] > float(dimensions_spec["max"][i]) for i in range(3)):
                dimension_status = "FAIL"
                differences["max"] = {"expected": dimensions_spec["max"], "actual": actual_dimensions}
        checks["dimensions"] = _check(dimension_status, "Scene world dimensions compared with declared contract.", actual=actual_dimensions, differences=differences)
    else:
        checks["dimensions"] = _check("NOT_TESTED", "No dimensions contract was declared.", actual=manifest.get("scene_bounds"))

    missing = manifest["external_files"]["missing"]
    if missing and not contract.get("allow_missing_files", False):
        checks["missing_external_files"] = _check("FAIL", "External image/library paths are missing.", missing=missing)
    else:
        checks["missing_external_files"] = _check("PASS", "No disallowed external paths are missing.", missing=missing, allowed=bool(contract.get("allow_missing_files", False)))

    floor_spec = contract.get("floor")
    floor_parts = []
    for spec in required_specs:
        if spec.get("floor_contact") is True:
            floor_parts.append(spec)
    if floor_spec or floor_parts:
        declared_check_names.add("floor_contact")
    if floor_spec:
        floor_z = float(floor_spec.get("z", 0.0))
        tolerance = float(floor_spec.get("tolerance", 1e-4))
        if floor_spec.get("parts"):
            floor_parts = [{"name": item} if isinstance(item, str) else dict(item) for item in floor_spec["parts"]]
        if not floor_parts:
            checks["floor_contact"] = _check("NOT_TESTED", "Floor was declared without part selectors; no contact proof was attempted.", floor_z=floor_z)
        else:
            contact_results = []
            for spec in floor_parts:
                matches = [record for record in records if _match_record(record, spec)]
                if not matches:
                    contact_results.append(_check("FAIL", "Floor/contact selector matched no object.", spec=spec))
                for record in matches:
                    bounds = record.get("world_bounds")
                    min_z = bounds["min"][2] if bounds and bounds.get("finite") else None
                    if min_z is None:
                        status = "FAIL"
                    elif floor_spec.get("mode", "touch") == "above":
                        status = "PASS" if min_z >= floor_z - tolerance else "FAIL"
                    else:
                        status = "PASS" if abs(min_z - floor_z) <= tolerance else "FAIL"
                    contact_results.append(_check(status, "Explicit floor/contact check using evaluated world bounds.", object=record["name"], min_z=min_z, floor_z=floor_z, tolerance=tolerance))
            checks["floor_contact"] = _check(
                "FAIL" if any(item["status"] == "FAIL" for item in contact_results) else "PASS",
                "Explicit floor/contact checks completed.",
                results=contact_results,
            )
    else:
        checks["floor_contact"] = _check("NOT_TESTED", "No explicit floor/contact contract was declared.")

    unsupported = []
    for key in ("watertight", "self_intersection", "no_intersection", "clearance", "rig", "uv", "native_engine"):
        if contract.get(key) or key in (contract.get("required_checks") or []):
            unsupported.append(key)
    if unsupported:
        declared_check_names.add("unsupported_requested_checks")
        checks["unsupported_requested_checks"] = _check(
            "NOT_TESTED",
            "The requested mechanism is not implemented by this focused adapter; it was not promoted to PASS.",
            checks=unsupported,
        )

    untested_coverage = sorted(
        name for name, item in checks.items() if item.get("status") == "NOT_TESTED"
    )
    declared_checks = {name: checks[name] for name in declared_check_names if name in checks}
    return {
        "checks": checks,
        "status": _status_from_checks(declared_checks),
        "contract": contract,
        "declared_check_names": sorted(declared_checks),
        "untested_coverage": untested_coverage,
    }


def _read_png_size(path: str) -> Optional[List[int]]:
    try:
        with open(path, "rb") as handle:
            header = handle.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return list(struct.unpack(">II", header[16:24]))
    except (OSError, struct.error):
        return None


def _render_operation(bpy: Any, Vector: Any, request: Dict[str, Any]) -> Dict[str, Any]:
    report = _base_report(request, bpy)
    manifest = _inspect_scene(bpy, Vector)
    source_fingerprint = manifest["stable_fingerprint"]
    bounds = manifest.get("scene_bounds")
    if not bounds or not bounds.get("finite"):
        report["status"] = "NOT_TESTED"
        report["error"] = {"kind": "NO_RENDERABLE_GEOMETRY", "message": "No finite evaluated scene bounds were available for a fitted camera."}
        return report

    import mathutils

    out_dir = pathlib.Path(request["out_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    center = Vector([(bounds["min"][i] + bounds["max"][i]) * 0.5 for i in range(3)])
    dimensions = Vector(bounds["dimensions"])
    radius = max(float(max(dimensions)), 0.001) * 0.5
    old_camera = bpy.context.scene.camera
    old_world = bpy.context.scene.world
    scene = bpy.context.scene
    temp_objects = []
    temp_meshes = []
    temp_materials = []
    temp_lights = []
    temp_cameras = []
    try:
        world = bpy.data.worlds.new("BE_RenderWorld")
        temp_materials.append(world)
        world.use_nodes = True
        background = world.node_tree.nodes.get("Background")
        if background:
            background.inputs["Color"].default_value = (0.035, 0.045, 0.06, 1.0)
            background.inputs["Strength"].default_value = 0.35
        scene.world = world

        camera_data = bpy.data.cameras.new("BE_RenderCamera")
        camera = bpy.data.objects.new("BE_RenderCamera", camera_data)
        scene.collection.objects.link(camera)
        temp_objects.append(camera)
        temp_cameras.append(camera_data)
        camera_data.lens = 52.0
        camera_data.sensor_width = 36.0
        scene.camera = camera

        # A temporary neutral floor makes contact and lower silhouettes readable;
        # it is never saved back into the user's blend.
        floor_z = float(bounds["min"][2])
        half = max(float(max(dimensions)) * 2.5, 1.0)
        floor_mesh = bpy.data.meshes.new("BE_RenderFloorMesh")
        temp_meshes.append(floor_mesh)
        floor_mesh.from_pydata(
            [(-half, -half, floor_z), (half, -half, floor_z), (half, half, floor_z), (-half, half, floor_z)],
            [],
            [(0, 1, 2, 3)],
        )
        floor_mesh.update()
        floor = bpy.data.objects.new("BE_RenderFloor", floor_mesh)
        scene.collection.objects.link(floor)
        temp_objects.append(floor)
        floor_material = bpy.data.materials.new("BE_RenderFloorMaterial")
        temp_materials.append(floor_material)
        floor_material.diffuse_color = (0.12, 0.13, 0.15, 1.0)
        floor.data.materials.append(floor_material)

        for name, location, energy, size in (
            ("BE_Key", (center.x + radius * 2.2, center.y - radius * 2.5, center.z + radius * 3.0), 950.0, radius * 2.0),
            ("BE_Fill", (center.x - radius * 2.0, center.y - radius * 1.0, center.z + radius * 1.2), 550.0, radius * 2.5),
            ("BE_Rim", (center.x, center.y + radius * 2.5, center.z + radius * 2.2), 800.0, radius * 1.5),
        ):
            light_data = bpy.data.lights.new(name, type="AREA")
            light_data.energy = energy
            light_data.shape = "DISK"
            light_data.size = max(size, 0.1)
            light = bpy.data.objects.new(name, light_data)
            scene.collection.objects.link(light)
            light.location = location
            light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
            temp_objects.append(light)
            temp_lights.append(light_data)

        engine_used = None
        for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = candidate
                engine_used = candidate
                break
            except Exception:
                continue
        if engine_used is None:
            try:
                scene.render.engine = "CYCLES"
                scene.cycles.device = "CPU"
                engine_used = "CYCLES"
            except Exception as exc:
                report["status"] = "NOT_TESTED"
                report["error"] = {"kind": "NO_RENDER_ENGINE", "message": str(exc)}
                return report
        samples_configured = False
        samples_applied: Optional[int] = None
        if engine_used == "CYCLES":
            scene.cycles.device = "CPU"
            scene.cycles.samples = int(request["samples"])
            samples_applied = int(scene.cycles.samples)
            samples_configured = samples_applied == int(request["samples"])
        elif hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = int(request["samples"])
            samples_applied = int(scene.eevee.taa_render_samples)
            samples_configured = samples_applied == int(request["samples"])
        scene.render.resolution_x = int(request["resolution"])
        scene.render.resolution_y = int(request["resolution"])
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.film_transparent = False
        scene.render.use_file_extension = True
        scene.render.filepath = ""
        views = request["views"]
        view_directions = {
            "hero": Vector((1.0, -1.0, 0.72)),
            "front": Vector((0.0, -1.0, 0.12)),
            "side": Vector((1.0, 0.0, 0.12)),
            "back": Vector((0.0, 1.0, 0.12)),
            "top": Vector((0.0, 0.0, 1.0)),
        }
        view_records = []
        fov = 2.0 * math.atan(float(camera_data.sensor_width) / (2.0 * float(camera_data.lens)))
        distance = max(radius / max(math.tan(fov * 0.5), 0.01) * 1.35, radius * 2.0)
        for view in views:
            target = out_dir / f"{view}.png"
            if target.exists() and not request.get("force"):
                view_records.append({"view": view, "status": "FAIL", "error": {"kind": "OUTPUT_EXISTS", "path": str(target)}})
                continue
            direction = view_directions[view].normalized()
            camera.location = center + direction * distance
            camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
            scene.render.filepath = str(target)
            started = time.monotonic()
            try:
                bpy.ops.render.render(write_still=True)
                exists = target.is_file()
                size = target.stat().st_size if exists else 0
                dimensions_png = _read_png_size(str(target)) if exists else None
                record = {
                    "view": view,
                    "status": "PASS" if exists and size > 0 and dimensions_png and samples_configured else "NOT_TESTED" if exists and size > 0 and dimensions_png else "FAIL",
                    "path": str(target),
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest() if exists else None,
                    "bytes": size,
                    "png_dimensions": dimensions_png,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "source_scene_fingerprint": source_fingerprint,
                    "actual_settings": {
                        "engine": scene.render.engine,
                        "resolution": [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage],
                        "samples_requested": int(request["samples"]),
                        "samples_applied": samples_applied,
                        "samples_configured": samples_configured,
                        "samples_status": "PASS" if samples_configured else "NOT_TESTED",
                        "device": getattr(getattr(scene, "cycles", None), "device", None) if scene.render.engine == "CYCLES" else "GPU_OR_DEFAULT",
                        "frame": int(scene.frame_current),
                        "camera": camera.name,
                        "camera_location": _vec(camera.location),
                        "camera_target": _vec(center),
                        "view_transform": str(scene.view_settings.view_transform),
                    },
                }
            except Exception as exc:
                record = {"view": view, "status": "FAIL", "path": str(target), "error": {"kind": "RENDER_ERROR", "message": str(exc)}}
            view_records.append(record)
        report["render"] = {
            # This pass is deliberately neutral and diagnostic: it provides
            # repeatable structural/camera evidence, not the asset's final
            # artistic presentation or a user taste verdict.
            "render_role": "neutral_diagnostic",
            "artistic_beauty_render": False,
            "fresh_saved_blend": True,
            "source_scene_fingerprint": source_fingerprint,
            "source_sha256": request.get("source_sha256"),
            "camera_rig": {"name": camera.name, "fit_center": _vec(center), "fit_radius": radius, "floor_z": floor_z},
            "views": view_records,
        }
        report["status"] = _status_from_checks({record["view"]: {"status": record["status"]} for record in view_records})
        return report
    finally:
        scene.camera = old_camera
        scene.world = old_world
        for obj in reversed(temp_objects):
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:
                pass
        for mesh in temp_meshes:
            try:
                bpy.data.meshes.remove(mesh)
            except Exception:
                pass
        for material in temp_materials:
            try:
                if hasattr(material, "users") and material.users == 0:
                    if hasattr(bpy.data.worlds, "remove") and material in bpy.data.worlds:
                        bpy.data.worlds.remove(material)
            except Exception:
                pass
        for data in temp_lights:
            try:
                bpy.data.lights.remove(data)
            except Exception:
                pass
        for data in temp_cameras:
            try:
                bpy.data.cameras.remove(data)
            except Exception:
                pass


def _format_readback(path: pathlib.Path, export_format: str) -> Dict[str, Any]:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            header = handle.read(256)
    except OSError as exc:
        return {"status": "FAIL", "message": str(exc)}
    if size <= 0:
        return {"status": "FAIL", "message": "export file is empty", "bytes": size}
    if export_format == "glb":
        valid = header[:4] == b"glTF"
    elif export_format == "fbx":
        valid = header.startswith(b"Kaydara FBX Binary") or header.lstrip().startswith(b"; FBX")
    else:
        ascii_stl = header.lstrip().startswith(b"solid") and b"facet" in header
        binary_stl = False
        if size >= 84 and len(header) >= 84:
            triangle_count = struct.unpack("<I", header[80:84])[0]
            binary_stl = triangle_count > 0 and 84 + 50 * triangle_count <= size
        valid = ascii_stl or binary_stl
    return {
        "status": "PASS" if valid else "NOT_TESTED",
        "message": "Header/format readback only; native-engine playback was not tested.",
        "bytes": size,
        "header_signature_observed": bool(valid),
    }


def _export_operation(bpy: Any, Vector: Any, request: Dict[str, Any]) -> Dict[str, Any]:
    report = _base_report(request, bpy)
    manifest = _inspect_scene(bpy, Vector)
    output = pathlib.Path(request["out"]).resolve()
    export_format = request["format"]
    if output.exists() and not request.get("force"):
        report["status"] = "FAIL"
        report["error"] = {"kind": "OUTPUT_EXISTS", "path": str(output)}
        return report
    try:
        if export_format == "glb":
            if not hasattr(bpy.ops.export_scene, "gltf"):
                raise NotImplementedError("glTF exporter operator is unavailable")
            bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB", use_selection=False)
        elif export_format == "fbx":
            if not hasattr(bpy.ops.export_scene, "fbx"):
                raise NotImplementedError("FBX exporter operator is unavailable")
            bpy.ops.export_scene.fbx(filepath=str(output), use_selection=False, apply_unit_scale=True)
        elif export_format == "stl":
            if hasattr(bpy.ops.wm, "stl_export"):
                bpy.ops.wm.stl_export(filepath=str(output), export_selected_objects=False)
            elif hasattr(bpy.ops.export_mesh, "stl"):
                bpy.ops.export_mesh.stl(filepath=str(output), use_selection=False)
            else:
                raise NotImplementedError("STL exporter operator is unavailable")
        else:
            raise NotImplementedError(f"unsupported export format: {export_format}")
    except NotImplementedError as exc:
        report["status"] = "NOT_TESTED"
        report["error"] = {"kind": "EXPORTER_UNAVAILABLE", "message": str(exc)}
        return report
    except Exception as exc:
        report["status"] = "FAIL"
        report["error"] = {"kind": "EXPORT_ERROR", "message": str(exc), "traceback": traceback.format_exc(limit=8)}
        return report
    readback = _format_readback(output, export_format)
    report["export"] = {
        "source_saved_blend": bpy.data.filepath,
        "source_sha256": request.get("source_sha256"),
        "source_scene_fingerprint": manifest["stable_fingerprint"],
        "result_path": str(output),
        "result_type": "file",
        "format": export_format,
        "readback": readback,
        "native_engine_verified": False,
        "native_engine_note": "The adapter inspected bytes/header only; native Blender/Roblox/other-engine playback was not verified.",
    }
    report["status"] = readback["status"]
    return report


def _payload_main() -> None:
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore

    args = _payload_args()
    request_path = pathlib.Path(args.request)
    result_path = pathlib.Path(args.result)
    try:
        request = _read_json(request_path)
        operation = request.get("operation")
        if operation == "probe":
            result = _probe(bpy, request)
        elif operation == "inspect":
            result = _inspect_operation(bpy, Vector, request)
        elif operation == "validate":
            report = _inspect_operation(bpy, Vector, request)
            validation = _validate_contract(report["inspection"], request.get("contract") or {})
            report["validation"] = validation
            report["status"] = validation["status"]
            result = report
        elif operation == "render":
            result = _render_operation(bpy, Vector, request)
        elif operation == "export":
            result = _export_operation(bpy, Vector, request)
        else:
            result = _host_failure(str(operation), "UNKNOWN_OPERATION", message=f"unsupported payload operation: {operation}")
    except Exception as exc:
        result = _host_failure(request.get("operation", "unknown") if isinstance(locals().get("request"), dict) else "unknown", "PAYLOAD_EXCEPTION", message=str(exc), traceback=traceback.format_exc(limit=20))
    _write_json(result_path, result)


if __name__ == "__main__":
    if "--blender-payload" in sys.argv:
        _payload_main()
    else:
        raise SystemExit(_host_main())
