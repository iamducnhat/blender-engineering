#!/usr/bin/env python3
"""Portable Blender animation inspection, sampling, preview, and export CLI.

The command line process owns the Blender child process and never relies on a
persistent Blender console or UI context.  Blender is invoked in background
mode with this same file as a small worker script.  The worker returns one
JSON protocol line; all other Blender stdout/stderr is captured by the parent.

This is deliberately a reporting and delivery helper.  It does not claim that
an exported glTF/FBX file preserves Blender's native rig, constraints, drivers,
or simulation semantics.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
import platform
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "blender-engineering-animation/0.1"
WORKER_MARKER = "--blender-animation-worker"
WORKER_SENTINEL = "__BLENDER_ENGINEERING_ANIMATION_JSON__"
DEFAULT_TIMEOUT = 180.0
DEFAULT_MAX_FRAMES = 240


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_path(value: str | os.PathLike[str]) -> Path:
    return Path(os.path.expanduser(os.fspath(value))).resolve()


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def file_record(path: Path) -> dict[str, Any]:
    record: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if path.exists():
        try:
            record["size_bytes"] = path.stat().st_size
        except OSError:
            record["size_bytes"] = None
        record["sha256"] = sha256_file(path)
    else:
        record["size_bytes"] = None
        record["sha256"] = None
    return record


def write_json_atomic(path: Path, payload: Mapping[str, Any], pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    text = json.dumps(payload, indent=2 if pretty else None, sort_keys=True, ensure_ascii=False)
    temporary.write_text(text + "\n", encoding="utf-8")
    os.replace(temporary, path)


def resolve_executable(explicit: str | None) -> Path | None:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    environment_value = os.environ.get("BLENDER_BIN")
    if environment_value:
        candidates.append(environment_value)
    candidates.extend(
        [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "/Applications/Blender.app/Contents/MacOS/blender",
            "/usr/local/bin/blender",
            "/opt/homebrew/bin/blender",
            "/usr/bin/blender",
        ]
    )
    path_candidate = shutil.which("blender")
    if path_candidate:
        candidates.append(path_candidate)
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        expanded = Path(os.path.expanduser(candidate))
        if expanded.exists() and os.access(expanded, os.X_OK):
            return expanded.resolve()
        resolved = shutil.which(candidate)
        if resolved:
            return Path(resolved).resolve()
    return None


def terminate_owned_process(process: subprocess.Popen[str], grace: float = 2.0) -> None:
    """Terminate only the process group created by this CLI."""

    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()
    except (OSError, ProcessLookupError):
        pass
    try:
        process.wait(timeout=grace)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            process.kill()
    except (OSError, ProcessLookupError):
        pass
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass


def parse_worker_line(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        if line.startswith(WORKER_SENTINEL):
            try:
                value = json.loads(line[len(WORKER_SENTINEL) :])
            except json.JSONDecodeError:
                return None
            return value if isinstance(value, dict) else None
    return None


def run_blender(
    blender: Path,
    payload: Mapping[str, Any],
    timeout: float,
) -> dict[str, Any]:
    protocol_dir = Path(tempfile.mkdtemp(prefix="blender-animation-protocol-"))
    protocol_path = protocol_dir / "worker-result.json"
    worker_payload = dict(payload)
    worker_payload["protocol_path"] = str(protocol_path)
    command = [
        str(blender),
        "--background",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        WORKER_MARKER,
        json.dumps(worker_payload, separators=(",", ":"), ensure_ascii=False),
    ]
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=(os.name == "posix"),
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=max(0.1, timeout))
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        terminate_owned_process(process)
        trailing_out, trailing_err = process.communicate()
        stdout = (stdout or "") + (trailing_out or "")
        stderr = (stderr or "") + (trailing_err or "")
    elapsed = time.monotonic() - started
    worker: dict[str, Any] | None = None
    if protocol_path.is_file():
        try:
            decoded = json.loads(protocol_path.read_text(encoding="utf-8"))
            if isinstance(decoded, dict):
                worker = decoded
        except (OSError, json.JSONDecodeError):
            worker = None
    if worker is None:
        worker = parse_worker_line(stdout)
    process_record = {
        "returncode": process.returncode,
        "elapsed_seconds": elapsed,
        "timed_out": timed_out,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-8000:],
    }
    if timed_out:
        shutil.rmtree(protocol_dir, ignore_errors=True)
        return {
            "ok": False,
            "error_kind": "timeout",
            "error": f"Blender worker exceeded {timeout:.3f}s and was terminated",
            "process": process_record,
        }
    if worker is None:
        shutil.rmtree(protocol_dir, ignore_errors=True)
        return {
            "ok": False,
            "error_kind": "worker_protocol",
            "error": "Blender exited without a valid JSON worker record",
            "process": process_record,
        }
    worker["process"] = process_record
    shutil.rmtree(protocol_dir, ignore_errors=True)
    if process.returncode not in (0, None) and worker.get("ok"):
        worker["ok"] = False
        worker["error_kind"] = "blender_process_exit"
        worker["error"] = f"Blender exited with status {process.returncode}"
    return worker


def parse_resolution(value: str) -> tuple[int, int]:
    text = str(value).lower().strip()
    if "x" in text:
        left, right = text.split("x", 1)
        width, height = int(left), int(right)
    else:
        width = height = int(text)
    if width < 1 or height < 1 or width > 16384 or height > 16384:
        raise ValueError("resolution must be between 1 and 16384 pixels per side")
    return width, height


def ensure_blend(path_value: str) -> Path:
    path = safe_path(path_value)
    if not path.is_file():
        raise FileNotFoundError(f"Blend file does not exist: {path}")
    return path


def portable_delivery_assessment(
    missing_assets: Mapping[str, Any] | None,
    simulation_caches: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Report whether target portability was actually proven.

    Interchange readback and dependency completeness are separate from bundle
    portability. Resolving an absolute path lets Blender reopen the staged
    branch, but it does not prove that a recipient without the author's asset
    directories can open the exported target. This conservative assessment
    therefore leaves portability unproven whenever an external dependency or
    cache is present; packaging the source .blend remains an orchestrator
    responsibility.
    """

    if not isinstance(missing_assets, Mapping) or not isinstance(simulation_caches, Mapping):
        return {
            "portable_delivery_complete": False,
            "status": "NOT_TESTED_NO_DEPENDENCY_RECEIPT",
            "external_dependencies": [],
            "portable_scope": "target interchange artifact only; source .blend packaging is not performed here",
        }
    external: list[dict[str, Any]] = []
    for record in missing_assets.get("checked", []):
        if not isinstance(record, Mapping):
            continue
        filepath = str(record.get("filepath", "") or "")
        if not filepath or bool(record.get("packed", False)):
            continue
        external.append(
            {
                "kind": str(record.get("kind", "image")),
                "datablock": record.get("datablock"),
                "filepath": filepath,
                "exists": record.get("exists"),
                "reason": "external dependency embedding or isolated recipient bundle was not independently verified",
            }
        )
    # Blender point caches and Geometry Nodes simulations can depend on cache
    # state that is not represented by one portable target-file path. Preserve
    # the evidence and keep the final-bundle claim conservative.
    for entry in simulation_caches.get("point_caches", []):
        if isinstance(entry, Mapping):
            external.append(
                {
                    "kind": "point_cache",
                    "object": entry.get("object"),
                    "modifier": entry.get("modifier"),
                    "reason": "point-cache portability was not independently bundled and read back",
                }
            )
    for entry in simulation_caches.get("geometry_nodes", []):
        if isinstance(entry, Mapping):
            external.append(
                {
                    "kind": "geometry_nodes_simulation",
                    "object": entry.get("object"),
                    "modifier": entry.get("modifier"),
                    "reason": "Geometry Nodes simulation portability requires a target-specific cache/runtime probe",
                }
            )
    return {
        "portable_delivery_complete": not external,
        "status": "VERIFIED_NO_EXTERNAL_DEPENDENCIES" if not external else "NOT_TESTED_EXTERNAL_DEPENDENCIES",
        "external_dependencies": external,
        "portable_scope": "target interchange artifact only; source .blend packaging is not performed here",
    }


def frame_values(start: float, end: float, step: float, maximum: int) -> list[float]:
    if not all(math.isfinite(float(v)) for v in (start, end, step)):
        raise ValueError("start, end, and step must be finite")
    if step <= 0:
        raise ValueError("step must be greater than zero")
    if end < start:
        raise ValueError("end must be greater than or equal to start")
    values: list[float] = []
    current = float(start)
    # A small relative tolerance protects a mathematically exact end frame
    # from binary floating point drift while preserving unrounded values.
    epsilon = max(1e-9, abs(end) * 1e-12)
    while current <= end + epsilon:
        values.append(current)
        if len(values) > maximum:
            raise ValueError(f"frame count exceeds max_frames={maximum}")
        current += step
    if values and values[-1] > end and values[-1] - end <= epsilon:
        values[-1] = float(end)
    elif values and values[-1] < end - epsilon:
        # Include the requested endpoint even when step does not divide the
        # range.  Preview/export timing must then represent the shorter final
        # interval explicitly rather than pretending the samples are uniform.
        values.append(float(end))
        if len(values) > maximum:
            raise ValueError(f"frame count exceeds max_frames={maximum}")
    return values


def png_size(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def resolve_ffmpeg(explicit: str | None) -> Path | None:
    if explicit:
        candidate = Path(os.path.expanduser(explicit))
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    environment_value = os.environ.get("FFMPEG_BIN")
    if environment_value:
        found = shutil.which(environment_value)
        if found:
            return Path(found).resolve()
    found = shutil.which("ffmpeg")
    return Path(found).resolve() if found else None


def resolve_ffprobe(explicit: str | None) -> Path | None:
    """Resolve ffprobe independently so duration evidence is explicit."""

    if explicit:
        candidate = Path(os.path.expanduser(explicit))
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    environment_value = os.environ.get("FFPROBE_BIN")
    if environment_value:
        found = shutil.which(environment_value)
        if found:
            return Path(found).resolve()
    found = shutil.which("ffprobe")
    return Path(found).resolve() if found else None


def run_ffmpeg(
    ffmpeg: Path,
    frames_dir: Path,
    pattern: str,
    output: Path,
    fps: float,
    slow: bool,
    timeout: float,
) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    filters = "setpts=2.0*PTS" if slow else "null"
    command = [
        str(ffmpeg),
        "-y",
        "-framerate",
        str(max(0.001, fps)),
        "-i",
        str(frames_dir / pattern),
        "-vf",
        filters,
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output),
    ]
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=(os.name == "posix"),
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=max(0.1, timeout))
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate_owned_process(process)
        stdout, stderr = process.communicate()
    return {
        "ok": process.returncode == 0 and not timed_out and output.is_file(),
        "path": str(output),
        "exists": output.is_file(),
        "slow_motion": slow,
        "slow_motion_factor": 2.0 if slow else 1.0,
        "fps": fps,
        "timing_mode": "retimed_override",
        "full_speed_label": False,
        "command": command,
        "elapsed_seconds": time.monotonic() - started,
        "timed_out": timed_out,
        "returncode": process.returncode,
        "stderr_tail": (stderr or "")[-4000:],
        "stdout_tail": (stdout or "")[-1000:],
    }


def _timed_sequence_timebase(durations: Sequence[float]) -> tuple[int, list[int]]:
    """Choose an integer timebase that represents durations without drift."""

    fractions = [Fraction(float(value)).limit_denominator(100000) for value in durations]
    denominator = 1
    for value in fractions:
        denominator = math.lcm(denominator, value.denominator)
        if denominator > 100000:
            denominator = 1000
            break
    ticks = [max(1, int(round(float(value) * denominator))) for value in durations]
    # A long preview should not expand into millions of image references just
    # to obtain a very fine timebase. The fallback is still bounded to 1 ms.
    if sum(ticks) > 200000:
        denominator = 1000
        ticks = [max(1, int(round(float(value) * denominator))) for value in durations]
    return denominator, ticks


def run_ffmpeg_timed_sequence(
    ffmpeg: Path,
    frame_paths: Sequence[Path],
    durations: Sequence[float],
    output: Path,
    slow: bool,
    timeout: float,
    timing_mode: str = "source_preserving_timed_sequence",
) -> dict[str, Any]:
    """Encode a source-timed sequence without losing an irregular endpoint.

    The concat demuxer in current ffmpeg builds quantizes its implicit input
    timebase (often to 1/25), which can turn 1/30 or fractional Blender frame
    intervals into measurable drift. This helper repeats symlinked PNG entries
    at an integer timebase derived from the requested durations. The resulting
    CFR sequence has the same frame holds and remains inspectable by ffprobe.
    """

    if not frame_paths or len(frame_paths) != len(durations):
        return {
            "ok": False,
            "error_kind": "invalid_timing_manifest",
            "path": str(output),
            "exists": False,
        }
    if any((not path.is_file()) for path in frame_paths):
        return {
            "ok": False,
            "error_kind": "render_frames_missing",
            "path": str(output),
            "exists": False,
        }
    if any((not math.isfinite(float(value)) or float(value) <= 0.0) for value in durations):
        return {
            "ok": False,
            "error_kind": "invalid_frame_duration",
            "path": str(output),
            "exists": False,
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    sequence_dir = Path(tempfile.mkdtemp(prefix="blender-animation-timed-"))
    try:
        encoded_durations = [float(value) * (2.0 if slow else 1.0) for value in durations]
        timebase, ticks = _timed_sequence_timebase(encoded_durations)
        entry_index = 1
        for path, count in zip(frame_paths, ticks):
            for _ in range(count):
                entry = sequence_dir / f"frame_{entry_index:08d}.png"
                try:
                    os.symlink(path.resolve(), entry)
                except OSError:
                    # Symlinks can be disabled on Windows or restricted in a
                    # sandbox. Prefer a hardlink, then fall back to a copy;
                    # the timing receipt remains the same and no external
                    # files are modified.
                    try:
                        os.link(path.resolve(), entry)
                    except OSError:
                        shutil.copy2(path, entry)
                entry_index += 1
        command = [
            str(ffmpeg),
            "-y",
            "-framerate",
            str(timebase),
            "-i",
            str(sequence_dir / "frame_%08d.png"),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ]
        started = time.monotonic()
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=(os.name == "posix"),
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=max(0.1, timeout))
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_owned_process(process)
            stdout, stderr = process.communicate()
        return {
            "ok": process.returncode == 0 and not timed_out and output.is_file(),
            "path": str(output),
            "exists": output.is_file(),
            "slow_motion": slow,
            "slow_motion_factor": 2.0 if slow else 1.0,
            "timing_mode": timing_mode,
            "timebase": timebase,
            "encoded_frame_count": int(sum(ticks)),
            "frame_durations_seconds": [float(value) for value in durations],
            "source_duration_seconds": float(sum(float(value) for value in durations)),
            "encoded_frame_durations_seconds": encoded_durations,
            "encoded_duration_seconds": float(sum(encoded_durations)),
            "command": command,
            "elapsed_seconds": time.monotonic() - started,
            "timed_out": timed_out,
            "returncode": process.returncode,
            "stderr_tail": (stderr or "")[-4000:],
            "stdout_tail": (stdout or "")[-1000:],
        }
    finally:
        shutil.rmtree(sequence_dir, ignore_errors=True)


def probe_media_duration(ffprobe: Path | None, media: Path, timeout: float) -> dict[str, Any]:
    """Read container duration as evidence without making ffprobe mandatory."""

    if ffprobe is None:
        return {"status": "NOT_TESTED", "reason": "ffprobe_not_found"}
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(media),
    ]
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=(os.name == "posix"),
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=max(0.1, timeout))
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate_owned_process(process)
        stdout, stderr = process.communicate()
    try:
        decoded = json.loads(stdout or "{}")
        duration = float(decoded.get("format", {}).get("duration"))
    except (TypeError, ValueError, json.JSONDecodeError, AttributeError):
        duration = None
    return {
        "status": "VERIFIED" if process.returncode == 0 and not timed_out and duration is not None else "FAILED",
        "duration_seconds": duration,
        "command": command,
        "elapsed_seconds": time.monotonic() - started,
        "timed_out": timed_out,
        "returncode": process.returncode,
        "stderr_tail": (stderr or "")[-2000:],
    }


def source_preserving_durations(frame_values: Sequence[float], source_fps: float) -> list[float]:
    """Return frame holds in seconds, including a final source-frame hold."""

    if not frame_values:
        return []
    if not math.isfinite(float(source_fps)) or float(source_fps) <= 0.0:
        raise ValueError("source FPS must be finite and greater than zero")
    values = [float(value) for value in frame_values]
    deltas = [right - left for left, right in zip(values, values[1:])]
    positive = [delta for delta in deltas if delta > 0.0 and math.isfinite(delta)]
    final_delta = positive[-1] if positive else 1.0
    durations = [(delta if delta > 0.0 else final_delta) / float(source_fps) for delta in deltas]
    durations.append(final_delta / float(source_fps))
    return durations


def standard_receipt(
    command: str,
    blender: Path | None,
    worker: Mapping[str, Any],
    started_at: str,
) -> dict[str, Any]:
    result = dict(worker)
    process = result.pop("process", None)
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "started_at": started_at,
        "finished_at": utc_now(),
        "ok": bool(result.pop("ok", False)),
        "runtime": {
            "blender": str(blender) if blender else None,
            "platform": platform.platform(),
        },
        "process": process,
    }
    receipt.update(result)
    return receipt


def emit_receipt(receipt: Mapping[str, Any], output: Path | None, pretty: bool) -> int:
    if output is not None:
        write_json_atomic(output, receipt, pretty=pretty)
    print(json.dumps(receipt, indent=2 if pretty else None, sort_keys=True, ensure_ascii=False))
    return 0 if receipt.get("ok") else 1


# ---------------------------------------------------------------------------
# Blender worker.  This code is imported only inside Blender's Python process.
# It intentionally uses bpy data/evaluation APIs instead of UI operators for
# inspection.  Operators are confined to rendering, save, import, and export.
# ---------------------------------------------------------------------------


def _worker_json(value: Any) -> Any:
    """Convert common Blender RNA values to JSON-compatible values."""

    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(k): _worker_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_worker_json(v) for v in value]
    try:
        return [_worker_json(v) for v in value]
    except TypeError:
        return str(value)


def _worker_vec(value: Any, size: int | None = None) -> list[float] | None:
    try:
        result = [float(x) for x in value]
    except (TypeError, ValueError):
        return None
    if size is not None:
        result = result[:size]
    return [x if math.isfinite(x) else None for x in result]


def _worker_matrix(value: Any) -> list[list[float]] | None:
    try:
        return [_worker_vec(row, 4) or [] for row in value]
    except TypeError:
        return None


def _worker_matrix_record(matrix: Any) -> dict[str, Any]:
    try:
        translation = _worker_vec(matrix.translation, 3)
    except AttributeError:
        translation = None
    try:
        quaternion = _worker_vec(matrix.to_quaternion(), 4)
    except AttributeError:
        quaternion = None
    try:
        scale = _worker_vec(matrix.to_scale(), 3)
    except AttributeError:
        scale = None
    return {
        "matrix_world": _worker_matrix(matrix),
        "translation": translation,
        "quaternion": quaternion,
        "scale": scale,
    }


def _worker_set_frame(scene: Any, frame: float) -> None:
    """Set an exact fractional frame through Blender's integer+subframe API."""

    integer_frame = math.floor(float(frame))
    subframe = float(frame) - float(integer_frame)
    scene.frame_set(int(integer_frame), subframe=subframe)


def _worker_path_exists(filepath: str, blend_filepath: str) -> bool | None:
    if not filepath:
        return None
    try:
        path = filepath
        if path.startswith("//"):
            import bpy  # type: ignore

            # bpy.path.abspath's optional start is a directory, while
            # bpy.data.filepath is the .blend file itself.
            base = str(Path(blend_filepath).parent) if blend_filepath else None
            path = bpy.path.abspath(path, start=base) if base else bpy.path.abspath(path)
        return __import__("pathlib").Path(path).exists()
    except Exception:
        return None


def _worker_missing_assets() -> dict[str, Any]:
    import bpy  # type: ignore

    blend_filepath = str(getattr(bpy.data, "filepath", ""))
    missing: list[dict[str, Any]] = []
    checked: list[dict[str, Any]] = []
    for image in bpy.data.images:
        filepath = str(getattr(image, "filepath", "") or "")
        if not filepath:
            continue
        packed = getattr(image, "packed_file", None) is not None
        # A packed image is part of the .blend payload; its stale source path
        # must not be treated as a missing delivery dependency.
        exists = True if packed else _worker_path_exists(filepath, blend_filepath)
        record = {"datablock": image.name, "filepath": filepath, "exists": exists, "packed": packed}
        checked.append(record)
        if exists is False and not packed:
            missing.append(record)
    for cache in getattr(bpy.data, "cache_files", []):
        filepath = str(getattr(cache, "filepath", "") or "")
        if not filepath:
            continue
        exists = _worker_path_exists(filepath, blend_filepath)
        record = {"datablock": cache.name, "filepath": filepath, "exists": exists, "kind": "cache_file"}
        checked.append(record)
        if exists is False:
            missing.append(record)
    for library in getattr(bpy.data, "libraries", []):
        filepath = str(getattr(library, "filepath", "") or "")
        if not filepath:
            continue
        exists = _worker_path_exists(filepath, blend_filepath)
        record = {"datablock": library.name, "filepath": filepath, "exists": exists, "kind": "library"}
        checked.append(record)
        if exists is False:
            missing.append(record)
    return {"checked": checked, "missing": missing, "missing_count": len(missing)}


def _worker_geometry_node_simulation_nodes(
    node_tree: Any,
    group_path: str = "",
    visited: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Find actual Simulation Input/Output nodes, including nested groups."""

    if node_tree is None:
        return []
    if visited is None:
        visited = set()
    tree_id = id(node_tree)
    if tree_id in visited:
        return []
    visited.add(tree_id)
    records: list[dict[str, Any]] = []
    nodes = getattr(node_tree, "nodes", None)
    if nodes is None:
        return records
    for node in nodes:
        bl_idname = str(getattr(node, "bl_idname", "") or "")
        node_type = str(getattr(node, "type", "") or "")
        normalized = "".join(character for character in f"{bl_idname} {node_type}".upper() if character.isalnum())
        is_simulation = "SIMULATION" in normalized and (
            "INPUT" in normalized or "OUTPUT" in normalized
        )
        node_name = str(getattr(node, "name", "") or "")
        if is_simulation:
            records.append(
                {
                    "group": group_path or str(getattr(node_tree, "name", "") or "<node_tree>"),
                    "node": node_name,
                    "bl_idname": bl_idname,
                    "type": node_type,
                    "status": "geometry_nodes_simulation_requires_runtime_probe",
                }
            )
        child_tree = getattr(node, "node_tree", None)
        if child_tree is not None:
            child_path = f"{group_path}/{node_name}" if group_path else node_name
            records.extend(_worker_geometry_node_simulation_nodes(child_tree, child_path, visited))
    return records


def _worker_simulation_caches() -> dict[str, Any]:
    import bpy  # type: ignore

    entries: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    geometry_nodes_present: list[dict[str, Any]] = []
    missing_paths: list[dict[str, Any]] = []
    for obj in bpy.data.objects:
        for modifier in getattr(obj, "modifiers", []):
            point_cache = getattr(modifier, "point_cache", None)
            if point_cache is not None:
                entry: dict[str, Any] = {
                    "object": obj.name,
                    "modifier": modifier.name,
                    "type": modifier.type,
                    "is_baked": bool(getattr(point_cache, "is_baked", False)),
                    "is_outdated": bool(getattr(point_cache, "is_outdated", False)),
                    "frame_start": getattr(point_cache, "frame_start", None),
                    "frame_end": getattr(point_cache, "frame_end", None),
                    "status": "baked" if getattr(point_cache, "is_baked", False) else "runtime_or_unbaked",
                }
                entries.append(entry)
            if modifier.type == "NODES":
                node_group = getattr(modifier, "node_group", None)
                if node_group is None:
                    simulation_nodes: list[dict[str, Any]] = []
                    inspection_status = "node_group_unavailable_requires_runtime_probe"
                    unknown.append(
                        {
                            "object": obj.name,
                            "modifier": modifier.name,
                            "type": modifier.type,
                            "status": inspection_status,
                        }
                    )
                else:
                    simulation_nodes = _worker_geometry_node_simulation_nodes(node_group)
                    inspection_status = "simulation_nodes_detected" if simulation_nodes else "no_simulation_nodes_detected"
                    if simulation_nodes:
                        unknown.append(
                            {
                                "object": obj.name,
                                "modifier": modifier.name,
                                "type": modifier.type,
                                "status": "geometry_nodes_cache_requires_runtime_probe",
                                "simulation_nodes": simulation_nodes,
                            }
                        )
                geometry_nodes_present.append(
                    {
                        "object": obj.name,
                        "modifier": modifier.name,
                        "type": modifier.type,
                        "node_group": str(getattr(node_group, "name", "")) if node_group else None,
                        "inspection_status": inspection_status,
                        "simulation_nodes": simulation_nodes,
                    }
                )
    for cache in getattr(bpy.data, "cache_files", []):
        filepath = str(getattr(cache, "filepath", "") or "")
        if filepath and _worker_path_exists(filepath, str(getattr(bpy.data, "filepath", ""))) is False:
            missing_paths.append({"datablock": cache.name, "filepath": filepath})
    if missing_paths:
        status = "missing"
    elif unknown:
        status = "unknown_runtime_state"
    elif entries:
        status = "present_or_unbaked"
    elif geometry_nodes_present:
        status = "geometry_nodes_without_simulation"
    else:
        status = "none_detected"
    return {
        "status": status,
        "point_caches": entries,
        "geometry_nodes": unknown,
        "geometry_nodes_present": geometry_nodes_present,
        "missing_external_paths": missing_paths,
    }


def _worker_dependency_completeness(
    missing_assets: Mapping[str, Any],
    simulation_caches: Mapping[str, Any],
    policy: str,
) -> dict[str, Any]:
    """Turn dependency probes into an explicit export gate."""

    missing = list(missing_assets.get("missing", []))
    cache_issues: list[dict[str, Any]] = []
    cache_status = str(simulation_caches.get("status", "none_detected"))
    if cache_status in {"missing", "unknown_runtime_state"}:
        cache_issues.extend(list(simulation_caches.get("missing_external_paths", [])))
        cache_issues.extend(list(simulation_caches.get("geometry_nodes", [])))
        if not cache_issues:
            cache_issues.append({"status": cache_status})
    for entry in simulation_caches.get("point_caches", []):
        if not bool(entry.get("is_baked", False)) or bool(entry.get("is_outdated", False)):
            cache_issues.append(
                {
                    "object": entry.get("object"),
                    "modifier": entry.get("modifier"),
                    "status": entry.get("status"),
                    "is_baked": entry.get("is_baked"),
                    "is_outdated": entry.get("is_outdated"),
                }
            )
    reasons: list[str] = []
    if missing:
        reasons.append("missing_external_assets_or_libraries")
    if cache_issues:
        reasons.append("missing_or_unbaked_simulation_cache")
    complete = not reasons
    bypassed = bool(reasons) and policy == "explicit_optional_bypass"
    return {
        "status": "complete" if complete else ("explicit_optional_bypass" if bypassed else "incomplete"),
        "policy": policy,
        "missing_assets": missing,
        "cache_issues": cache_issues,
        "reasons": reasons,
        "complete": complete,
        "bypassed_as_optional": bypassed,
        "interpretation": (
            "No missing dependencies detected"
            if complete
            else "The caller explicitly declared all missing dependencies optional; this remains visible and is not a native completeness claim"
            if bypassed
            else "Required dependency completeness was not established"
        ),
    }


def _worker_make_paths_absolute() -> dict[str, Any]:
    """Resolve // paths while the source filepath is still the source file."""

    import bpy  # type: ignore

    operator = getattr(getattr(bpy.ops, "file", None), "make_paths_absolute", None)
    if operator is None:
        return {"status": "UNAVAILABLE", "operator": "file.make_paths_absolute"}
    try:
        result = operator()
        return {"status": "APPLIED", "operator_result": list(result) if result else []}
    except Exception as exc:  # pragma: no cover - depends on Blender context
        return {"status": "FAILED", "error": str(exc)}


def _worker_action_curves(action: Any) -> list[dict[str, Any]]:
    """Read both legacy and Blender 4.4+ layered Action channel bags."""

    curves: list[dict[str, Any]] = []
    seen: set[int] = set()

    def add_curve(curve: Any, slot_name: str | None = None) -> None:
        identifier = id(curve)
        if identifier in seen:
            return
        seen.add(identifier)
        try:
            start, end = curve.range()
        except Exception:
            start, end = None, None
        keys: list[dict[str, Any]] = []
        for point in list(getattr(curve, "keyframe_points", []))[:256]:
            try:
                keys.append(
                    {
                        "frame": float(point.co[0]),
                        "value": float(point.co[1]),
                        "interpolation": str(getattr(point, "interpolation", "")),
                    }
                )
            except (TypeError, ValueError, IndexError):
                continue
        curves.append(
            {
                "data_path": str(getattr(curve, "data_path", "")),
                "array_index": int(getattr(curve, "array_index", 0)),
                "frame_range": [start, end],
                "keyframe_count": len(getattr(curve, "keyframe_points", [])),
                "sampled_point_count": len(getattr(curve, "sampled_points", [])),
                "is_valid": bool(getattr(curve, "is_valid", True)),
                "is_empty": bool(getattr(curve, "is_empty", False)),
                "mute": bool(getattr(curve, "mute", False)),
                "extrapolation": str(getattr(curve, "extrapolation", "")),
                "group": str(getattr(getattr(curve, "group", None), "name", "")),
                "slot": slot_name,
                "keys": keys,
            }
        )

    legacy_curves = getattr(action, "fcurves", None)
    if legacy_curves is not None:
        for curve in legacy_curves:
            add_curve(curve)
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            for channelbag in getattr(strip, "channelbags", []):
                slot = getattr(channelbag, "slot", None)
                slot_name = str(
                    getattr(slot, "name_display", None)
                    or getattr(slot, "identifier", None)
                    or getattr(slot, "name", "")
                )
                for curve in getattr(channelbag, "fcurves", []):
                    add_curve(curve, slot_name)
    return curves


def _worker_action_record(action: Any) -> dict[str, Any]:
    slots: list[dict[str, Any]] = []
    for slot in getattr(action, "slots", []):
        display_name = (
            getattr(slot, "name_display", None)
            or getattr(slot, "identifier", None)
            or getattr(slot, "name", "")
        )
        slots.append(
            {
                "name": str(display_name),
                "name_display": str(getattr(slot, "name_display", "") or ""),
                "identifier": str(getattr(slot, "identifier", "")),
                "handle": str(getattr(slot, "handle", "")),
                "target_id_type": str(getattr(slot, "target_id_type", "")),
            }
        )
    layers: list[dict[str, Any]] = []
    for layer in getattr(action, "layers", []):
        strips: list[dict[str, Any]] = []
        for strip in getattr(layer, "strips", []):
            strips.append(
                {
                    "type": str(getattr(strip, "type", "")),
                    "frame_start": getattr(strip, "frame_start", None),
                    "frame_end": getattr(strip, "frame_end", None),
                    "action_frame_start": getattr(strip, "action_frame_start", None),
                    "action_frame_end": getattr(strip, "action_frame_end", None),
                    "channelbag_count": len(getattr(strip, "channelbags", [])),
                }
            )
        layers.append({"name": str(getattr(layer, "name", "")), "strips": strips})
    markers: list[dict[str, Any]] = []
    for marker in getattr(action, "pose_markers", []):
        markers.append({"name": str(marker.name), "frame": float(marker.frame)})
    frame_range = list(getattr(action, "frame_range", (0.0, 0.0)))
    return {
        "name": str(getattr(action, "name", "")),
        "frame_range": [float(x) for x in frame_range],
        "frame_start": float(getattr(action, "frame_start", 0.0)),
        "frame_end": float(getattr(action, "frame_end", 0.0)),
        "use_frame_range": bool(getattr(action, "use_frame_range", False)),
        "use_cyclic": bool(getattr(action, "use_cyclic", False)),
        "is_action_layered": bool(getattr(action, "is_action_layered", False)),
        "is_action_legacy": bool(getattr(action, "is_action_legacy", False)),
        "slots_feature_available_on_instance": hasattr(action, "slots"),
        "slots": slots,
        "layers": layers,
        "pose_markers": markers,
        "fcurves": _worker_action_curves(action),
    }


def _worker_animation_data_record(animation_data: Any) -> dict[str, Any]:
    action = getattr(animation_data, "action", None)
    current_slot = getattr(animation_data, "action_slot", None)
    current_slot_name = (
        getattr(current_slot, "name_display", None)
        or getattr(current_slot, "identifier", None)
        or getattr(current_slot, "name", "")
    )
    tracks: list[dict[str, Any]] = []
    for track in getattr(animation_data, "nla_tracks", []):
        strips: list[dict[str, Any]] = []
        for strip in getattr(track, "strips", []):
            strip_action = getattr(strip, "action", None)
            strips.append(
                {
                    "name": str(getattr(strip, "name", "")),
                    "action": str(getattr(strip_action, "name", "")) if strip_action else None,
                    "frame_start": getattr(strip, "frame_start", None),
                    "frame_end": getattr(strip, "frame_end", None),
                    "action_frame_start": getattr(strip, "action_frame_start", None),
                    "action_frame_end": getattr(strip, "action_frame_end", None),
                    "blend_type": str(getattr(strip, "blend_type", "")),
                    "extrapolation": str(getattr(strip, "extrapolation", "")),
                    "influence": getattr(strip, "influence", None),
                    "repeat": getattr(strip, "repeat", None),
                    "scale": getattr(strip, "scale", None),
                    "mute": bool(getattr(strip, "mute", False)),
                    "action_slot": str(
                        getattr(getattr(strip, "action_slot", None), "name_display", None)
                        or getattr(getattr(strip, "action_slot", None), "identifier", None)
                        or getattr(getattr(strip, "action_slot", None), "name", "")
                    ),
                }
            )
        tracks.append(
            {
                "name": str(getattr(track, "name", "")),
                "mute": bool(getattr(track, "mute", False)),
                "is_solo": bool(getattr(track, "is_solo", False)),
                "strips": strips,
            }
        )
    record: dict[str, Any] = {
        "action": str(getattr(action, "name", "")) if action else None,
        "action_slot": str(current_slot_name) if current_slot else None,
        "action_slot_handle": str(getattr(animation_data, "action_slot_handle", "")),
        "nla_tracks": tracks,
        "use_nla": bool(getattr(animation_data, "use_nla", False)),
        "use_tweak_mode": bool(getattr(animation_data, "use_tweak_mode", False)),
    }
    return record


def _worker_constraint_record(constraints: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for constraint in constraints:
        target = getattr(constraint, "target", None)
        records.append(
            {
                "name": str(getattr(constraint, "name", "")),
                "type": str(getattr(constraint, "type", "")),
                "influence": getattr(constraint, "influence", None),
                "mute": bool(getattr(constraint, "mute", False)),
                "target": str(getattr(target, "name", "")) if target else None,
                "subtarget": str(getattr(constraint, "subtarget", "")),
                "chain_length": getattr(constraint, "chain_count", None),
            }
        )
    return records


def _worker_world_bone(object_eval: Any, pose_bone: Any) -> dict[str, Any]:
    try:
        world_matrix = object_eval.matrix_world @ pose_bone.matrix
    except Exception:
        world_matrix = pose_bone.matrix
    return {
        "name": str(pose_bone.name),
        "parent": str(getattr(getattr(pose_bone, "parent", None), "name", "")) or None,
        "rotation_mode": str(getattr(pose_bone, "rotation_mode", "")),
        "rotation_quaternion": _worker_vec(getattr(pose_bone, "rotation_quaternion", []), 4),
        "location": _worker_vec(getattr(pose_bone, "location", []), 3),
        "scale": _worker_vec(getattr(pose_bone, "scale", []), 3),
        "world": _worker_matrix_record(world_matrix),
    }


def _worker_object_record(obj: Any, depsgraph: Any, include_bones: bool = True) -> dict[str, Any]:
    evaluated = obj.evaluated_get(depsgraph)
    record: dict[str, Any] = {
        "name": str(obj.name),
        "type": str(obj.type),
        "parent": str(getattr(getattr(obj, "parent", None), "name", "")) or None,
        "parent_type": str(getattr(obj, "parent_type", "")),
        "hide_viewport": bool(getattr(obj, "hide_viewport", False)),
        "hide_render": bool(getattr(obj, "hide_render", False)),
        "source_world": _worker_matrix_record(obj.matrix_world),
        "evaluated_world": _worker_matrix_record(evaluated.matrix_world),
        "dimensions": _worker_vec(getattr(evaluated, "dimensions", []), 3),
        "animation": _worker_animation_data_record(getattr(obj, "animation_data", None))
        if getattr(obj, "animation_data", None)
        else None,
        "constraints": _worker_constraint_record(getattr(obj, "constraints", [])),
    }
    if obj.type == "ARMATURE" and include_bones:
        pose_bones = []
        for pose_bone in getattr(evaluated.pose, "bones", []):
            pose_bones.append(_worker_world_bone(evaluated, pose_bone))
        rest_bones = []
        for bone in getattr(obj.data, "bones", []):
            rest_bones.append(
                {
                    "name": str(bone.name),
                    "parent": str(getattr(getattr(bone, "parent", None), "name", "")) or None,
                    "head_local": _worker_vec(bone.head_local, 3),
                    "tail_local": _worker_vec(bone.tail_local, 3),
                    "length": float(getattr(bone, "length", 0.0)),
                    "use_deform": bool(getattr(bone, "use_deform", False)),
                    "matrix_local": _worker_matrix(bone.matrix_local),
                }
            )
        record["armature"] = {
            "pose_bones": pose_bones,
            "rest_bones": rest_bones,
            "root_bones": [b["name"] for b in rest_bones if not b["parent"]],
            "pose_constraints": {
                str(pb.name): _worker_constraint_record(getattr(pb, "constraints", []))
                for pb in getattr(evaluated.pose, "bones", [])
                if getattr(pb, "constraints", None)
            },
        }
    return record


def _worker_scene_record(scene: Any, depsgraph: Any, include_objects: bool = True) -> dict[str, Any]:
    fps_base = float(getattr(scene.render, "fps_base", 1.0))
    fps = float(getattr(scene.render, "fps", 0.0)) / fps_base if fps_base else None
    markers = [
        {"name": str(marker.name), "frame": float(marker.frame)}
        for marker in getattr(scene, "timeline_markers", [])
    ]
    objects = []
    if include_objects:
        objects = [_worker_object_record(obj, depsgraph) for obj in scene.objects]
    return {
        "name": str(scene.name),
        "frame_current": float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0)),
        "frame_start": float(scene.frame_start),
        "frame_end": float(scene.frame_end),
        "frame_preview_start": float(getattr(scene, "frame_preview_start", scene.frame_start)),
        "frame_preview_end": float(getattr(scene, "frame_preview_end", scene.frame_end)),
        "fps": fps,
        "fps_numerator": float(getattr(scene.render, "fps", 0.0)),
        "fps_base": fps_base,
        "markers": markers,
        "camera": str(getattr(getattr(scene, "camera", None), "name", "")) or None,
        "render": {
            "engine": str(getattr(scene.render, "engine", "")),
            "resolution_x": int(getattr(scene.render, "resolution_x", 0)),
            "resolution_y": int(getattr(scene.render, "resolution_y", 0)),
            "resolution_percentage": int(getattr(scene.render, "resolution_percentage", 0)),
            "file_format": str(getattr(scene.render.image_settings, "file_format", "")),
        },
        "objects": objects,
    }


def _worker_evaluated_scene_record(scene: Any, depsgraph: Any) -> dict[str, Any]:
    """Compact per-frame state; source animation data is emitted once separately."""

    objects: list[dict[str, Any]] = []
    for obj in scene.objects:
        evaluated = obj.evaluated_get(depsgraph)
        record: dict[str, Any] = {
            "name": str(obj.name),
            "type": str(obj.type),
            "parent": str(getattr(getattr(obj, "parent", None), "name", "")) or None,
            "evaluated_world": _worker_matrix_record(evaluated.matrix_world),
            "dimensions": _worker_vec(getattr(evaluated, "dimensions", []), 3),
        }
        if obj.type == "ARMATURE":
            armature = obj.data
            pose_bones = [
                _worker_world_bone(evaluated, pose_bone)
                for pose_bone in getattr(evaluated.pose, "bones", [])
            ]
            root_bones = [
                str(bone.name)
                for bone in getattr(armature, "bones", [])
                if getattr(bone, "parent", None) is None
            ]
            record["armature"] = {"root_bones": root_bones, "pose_bones": pose_bones}
        objects.append(record)
    fps_base = float(getattr(scene.render, "fps_base", 1.0))
    return {
        "name": str(scene.name),
        "frame_current": float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0)),
        "fps": float(getattr(scene.render, "fps", 0.0)) / fps_base if fps_base else None,
        "camera": str(getattr(getattr(scene, "camera", None), "name", "")) or None,
        "objects": objects,
    }


def _worker_source_motion_evidence(scene: Any, objects: Sequence[Any]) -> dict[str, Any]:
    """Probe source channels and evaluated motion before baking/export."""

    original_frame = float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0))
    sample_frames = [float(scene.frame_start)]
    if float(scene.frame_end) > float(scene.frame_start):
        sample_frames.extend(
            [
                (float(scene.frame_start) + float(scene.frame_end)) / 2.0,
                float(scene.frame_end),
            ]
        )
    sample_frames = list(dict.fromkeys(sample_frames))
    object_names = {str(obj.name) for obj in objects}
    channel_counts: dict[str, int] = {}
    for obj in objects:
        count = 0
        for owner in (obj, getattr(obj, "data", None)):
            animation_data = getattr(owner, "animation_data", None) if owner is not None else None
            action = getattr(animation_data, "action", None) if animation_data is not None else None
            if action is not None:
                count += len(_worker_action_curves(action))
            if animation_data is not None:
                for track in getattr(animation_data, "nla_tracks", []):
                    for strip in getattr(track, "strips", []):
                        strip_action = getattr(strip, "action", None)
                        if strip_action is not None:
                            count += len(_worker_action_curves(strip_action))
        channel_counts[str(obj.name)] = count

    samples: dict[str, list[tuple[Any, ...]]] = {name: [] for name in object_names}
    try:
        for frame in sample_frames:
            _worker_set_frame(scene, frame)
            depsgraph = scene.view_layers[0].depsgraph
            record = _worker_evaluated_scene_record(scene, depsgraph)
            for obj in record.get("objects", []):
                name = str(obj.get("name"))
                if name not in samples:
                    continue
                values: list[Any] = []
                world = obj.get("evaluated_world", {})
                values.extend(world.get("translation") or [])
                values.extend(world.get("quaternion") or [])
                values.extend(obj.get("dimensions") or [])
                for pose in (obj.get("armature") or {}).get("pose_bones", []):
                    bone_world = pose.get("world", {})
                    values.extend(bone_world.get("translation") or [])
                    values.extend(bone_world.get("quaternion") or [])
                samples[name].append(tuple(float(value) for value in values if isinstance(value, (int, float))))
    finally:
        _worker_set_frame(scene, original_frame)

    evaluated_time_varying: dict[str, bool] = {}
    for name, values in samples.items():
        evaluated_time_varying[name] = bool(
            values
            and any(
                any(abs(first - second) > 1e-6 for first, second in zip(values[0], value))
                for value in values[1:]
            )
        )
    return {
        "sample_frames": sample_frames,
        "source_channel_counts": channel_counts,
        "evaluated_time_varying": evaluated_time_varying,
        "motion_detected": {
            name: bool(channel_counts.get(name, 0) or evaluated_time_varying.get(name, False))
            for name in object_names
        },
        "frame_restored": abs(
            (float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0))) - original_frame
        )
        <= 1e-9,
    }


def _worker_root_records(scene_record: Mapping[str, Any]) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    for obj in scene_record.get("objects", []):
        if obj.get("type") == "ARMATURE":
            armature = obj.get("armature") or {}
            pose_by_name = {p.get("name"): p for p in armature.get("pose_bones", [])}
            for root_name in armature.get("root_bones", []):
                pose = pose_by_name.get(root_name)
                if pose:
                    roots.append(
                        {
                            "id": f"{obj.get('name')}:{root_name}",
                            "object": obj.get("name"),
                            "bone": root_name,
                            "world": pose.get("world", {}),
                        }
                    )
        elif not obj.get("parent") and obj.get("type") in {"MESH", "EMPTY", "CAMERA", "LIGHT", "ARMATURE"}:
            roots.append(
                {
                    "id": str(obj.get("name")),
                    "object": obj.get("name"),
                    "bone": None,
                    "world": obj.get("evaluated_world", {}),
                }
            )
    return roots


def _worker_scene_action_records() -> list[dict[str, Any]]:
    import bpy  # type: ignore

    return [_worker_action_record(action) for action in bpy.data.actions]


def _worker_inspect(payload: Mapping[str, Any]) -> dict[str, Any]:
    import bpy  # type: ignore

    blend = str(payload["blend"])
    bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
    scene = bpy.context.scene
    depsgraph = scene.view_layers[0].depsgraph
    all_scenes = []
    for item in bpy.data.scenes:
        graph = item.view_layers[0].depsgraph
        all_scenes.append(_worker_scene_record(item, graph, include_objects=True))
    return {
        "blend_filepath": str(bpy.data.filepath),
        "missing_assets": _worker_missing_assets(),
        "simulation_caches": _worker_simulation_caches(),
        "feature_detection": {
            "action_slots_on_instance": any(hasattr(action, "slots") for action in bpy.data.actions),
            "action_layers_on_instance": any(hasattr(action, "layers") for action in bpy.data.actions),
            "action_count": len(bpy.data.actions),
        },
        "actions": _worker_scene_action_records(),
        "scenes": all_scenes,
        "active_scene": str(scene.name),
        "evaluated_active_scene": _worker_scene_record(scene, depsgraph, include_objects=True),
    }


def _worker_temporal_summary(
    samples: Sequence[Mapping[str, Any]],
    sample_step: float,
    source_fps: float | None = None,
) -> dict[str, Any]:
    if source_fps is None:
        for sample in samples:
            candidate = (sample.get("scene") or {}).get("fps")
            if isinstance(candidate, (int, float)) and math.isfinite(float(candidate)) and float(candidate) > 0.0:
                source_fps = float(candidate)
                break
    if source_fps is not None and (not math.isfinite(float(source_fps)) or float(source_fps) <= 0.0):
        source_fps = None
    trajectories: dict[str, list[dict[str, Any]]] = {}
    for sample in samples:
        for root in sample.get("roots", []):
            trajectories.setdefault(str(root.get("id")), []).append(root)
    summaries: list[dict[str, Any]] = []
    for identifier, values in trajectories.items():
        positions: list[tuple[float, float, float]] = []
        quaternions: list[tuple[float, float, float, float]] = []
        frames: list[float] = []
        for root in values:
            world = root.get("world") or {}
            translation = world.get("translation") or [0.0, 0.0, 0.0]
            quaternion = world.get("quaternion") or [1.0, 0.0, 0.0, 0.0]
            if len(translation) >= 3 and len(quaternion) >= 4:
                positions.append(tuple(float(x or 0.0) for x in translation[:3]))
                quaternions.append(tuple(float(x or 0.0) for x in quaternion[:4]))
                frames.append(float(root.get("frame", 0.0)))
        # The requested step is usually uniform, but frame_values deliberately
        # includes an irregular end sample when the range is not divisible by
        # the step. Derive each denominator from the observed frame stamps so
        # the last speed/acceleration is not falsely labelled with the regular
        # step.
        frame_intervals = [
            float(second - first)
            for first, second in zip(frames, frames[1:])
        ]
        speeds: list[float] = []
        for index, (first, second) in enumerate(zip(positions, positions[1:])):
            distance = math.sqrt(sum((b - a) ** 2 for a, b in zip(first, second)))
            interval = frame_intervals[index] if index < len(frame_intervals) else 0.0
            speeds.append(distance / interval if interval > 0.0 else 0.0)
        accelerations: list[float] = []
        acceleration_intervals = frame_intervals[1:]
        for index, (first, second) in enumerate(zip(speeds, speeds[1:])):
            interval = acceleration_intervals[index] if index < len(acceleration_intervals) else 0.0
            accelerations.append((second - first) / interval if interval > 0.0 else 0.0)
        jerks: list[float] = []
        jerk_intervals = frame_intervals[2:]
        for index, (first, second) in enumerate(zip(accelerations, accelerations[1:])):
            interval = jerk_intervals[index] if index < len(jerk_intervals) else 0.0
            jerks.append((second - first) / interval if interval > 0.0 else 0.0)
        speed_seconds: list[float] = []
        acceleration_seconds: list[float] = []
        jerk_seconds: list[float] = []
        time_intervals = (
            [interval / float(source_fps) for interval in frame_intervals]
            if source_fps is not None
            else []
        )
        for index, (first, second) in enumerate(zip(positions, positions[1:])):
            distance = math.sqrt(sum((b - a) ** 2 for a, b in zip(first, second)))
            interval = time_intervals[index] if index < len(time_intervals) else 0.0
            speed_seconds.append(distance / interval if interval > 0.0 else 0.0)
        for index, (first, second) in enumerate(zip(speed_seconds, speed_seconds[1:])):
            interval = time_intervals[index + 1] if index + 1 < len(time_intervals) else 0.0
            acceleration_seconds.append((second - first) / interval if interval > 0.0 else 0.0)
        for index, (first, second) in enumerate(zip(acceleration_seconds, acceleration_seconds[1:])):
            interval = time_intervals[index + 2] if index + 2 < len(time_intervals) else 0.0
            jerk_seconds.append((second - first) / interval if interval > 0.0 else 0.0)
        closure_distance = None
        if len(positions) > 1:
            closure_distance = math.sqrt(sum((b - a) ** 2 for a, b in zip(positions[0], positions[-1])))
        median_speed = sorted(abs(x) for x in speeds)[len(speeds) // 2] if speeds else 0.0
        abrupt_indices: list[int] = []
        if speeds and median_speed > 0:
            abrupt_indices = [i + 1 for i, value in enumerate(speeds) if abs(value) > median_speed * 5.0]
        summaries.append(
            {
                "id": identifier,
                "sample_count": len(values),
                "frame_stamps": frames,
                "frame_intervals": frame_intervals,
                "motion_present": any(abs(x) > 1e-9 for x in speeds),
                "stationary_at_sample_resolution": not any(abs(x) > 1e-9 for x in speeds),
                "max_speed": max((abs(x) for x in speeds), default=0.0),
                "max_acceleration": max((abs(x) for x in accelerations), default=0.0),
                "max_jerk": max((abs(x) for x in jerks), default=0.0),
                "max_speed_per_second": max((abs(x) for x in speed_seconds), default=None),
                "max_acceleration_per_second_squared": max((abs(x) for x in acceleration_seconds), default=None),
                "max_jerk_per_second_cubed": max((abs(x) for x in jerk_seconds), default=None),
                "abrupt_change_sample_indices": abrupt_indices,
                "first_last_position_distance": closure_distance,
                "loop_candidate": bool(closure_distance is not None and closure_distance <= 1e-5),
                "heuristic_note": "Motion/loop/abrupt-change fields are diagnostics, not aesthetic or physics pass gates.",
            }
        )
    return {
        "sample_step": sample_step,
        "source_fps": source_fps,
        "time_basis": {
            "frame_metrics": "scene_units_per_frame, scene_units_per_frame_squared, scene_units_per_frame_cubed",
            "second_metrics": "scene_units_per_second, scene_units_per_second_squared, scene_units_per_second_cubed"
            if source_fps is not None
            else None,
            "source_frame_duration_seconds": 1.0 / float(source_fps) if source_fps is not None else None,
        },
        "roots": summaries,
        "contact_detection": "not_inferred_without_contact_contract_or_markers",
    }


def _worker_sample(payload: Mapping[str, Any]) -> dict[str, Any]:
    import bpy  # type: ignore

    blend = str(payload["blend"])
    start = float(payload["start"])
    end = float(payload["end"])
    step = float(payload["step"])
    maximum = int(payload.get("max_frames", 240))
    values = _worker_frame_values(start, end, step, maximum)
    bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
    scene = bpy.context.scene
    original_frame = float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0))
    original_integer = int(scene.frame_current)
    original_subframe = float(getattr(scene, "frame_subframe", 0.0))
    action_records = _worker_scene_action_records()
    cache_records = _worker_simulation_caches()
    samples: list[dict[str, Any]] = []
    try:
        for frame in values:
            _worker_set_frame(scene, frame)
            depsgraph = scene.view_layers[0].depsgraph
            scene_record = _worker_evaluated_scene_record(scene, depsgraph)
            roots = []
            for root in _worker_root_records(scene_record):
                root["frame"] = frame
                roots.append(root)
            samples.append(
                {
                    "frame": frame,
                    "scene_frame_after_set": float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0)),
                    "roots": roots,
                    "scene": scene_record,
                    "armatures": [
                        {
                            "object": obj.get("name"),
                            "pose_bones": (obj.get("armature") or {}).get("pose_bones", []),
                        }
                        for obj in scene_record.get("objects", [])
                        if obj.get("type") == "ARMATURE"
                    ],
                }
            )
    finally:
        try:
            scene.frame_set(original_integer, subframe=original_subframe)
        except TypeError:
            scene.frame_set(original_frame)
    return {
        "blend_filepath": str(bpy.data.filepath),
        "source_animation": {"actions": action_records, "simulation_caches": cache_records},
        "requested_range": {"start": start, "end": end, "step": step, "frames": values},
        "evaluated_samples": samples,
        "temporal_summary": _worker_temporal_summary(
            samples,
            step,
            source_fps=(samples[0].get("scene") or {}).get("fps") if samples else None,
        ),
        "frame_preserved": {
            "before": original_frame,
            "after": float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0)),
            "restored": abs(
                (float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0))) - original_frame
            )
            <= 1e-9,
        },
        "review_note": "Evaluated scene state is separate from source Action curves. Review temporal samples and motion video; do not infer motion from a contact sheet alone.",
    }


def _worker_frame_values(start: float, end: float, step: float, maximum: int) -> list[float]:
    if not all(math.isfinite(x) for x in (start, end, step)) or step <= 0 or end < start:
        raise ValueError("invalid finite frame range")
    values: list[float] = []
    current = start
    epsilon = max(1e-9, abs(end) * 1e-12)
    while current <= end + epsilon:
        values.append(float(current))
        if len(values) > maximum:
            raise ValueError(f"frame count exceeds max_frames={maximum}")
        current += step
    if values and values[-1] > end and values[-1] - end <= epsilon:
        values[-1] = float(end)
    elif values and values[-1] < end - epsilon:
        values.append(float(end))
        if len(values) > maximum:
            raise ValueError(f"frame count exceeds max_frames={maximum}")
    return values


def _worker_apply_render_settings(scene: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    width = int(payload["width"])
    height = int(payload["height"])
    requested_samples = payload.get("samples")
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    applied_samples: int | None = None
    if requested_samples is not None:
        try:
            samples = max(1, int(requested_samples))
            if hasattr(scene, "cycles") and hasattr(scene.cycles, "samples"):
                scene.cycles.samples = samples
                applied_samples = int(scene.cycles.samples)
            elif hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
                scene.eevee.taa_render_samples = samples
                applied_samples = int(scene.eevee.taa_render_samples)
        except Exception:
            applied_samples = None
    return {
        "requested_resolution": [width, height],
        "applied_resolution": [int(scene.render.resolution_x), int(scene.render.resolution_y)],
        "requested_samples": requested_samples,
        "applied_samples": applied_samples,
        "engine": str(scene.render.engine),
        "file_format": str(scene.render.image_settings.file_format),
    }


def _worker_frame_token(frame: float) -> str:
    if abs(frame - round(frame)) <= 1e-9:
        return f"{int(round(frame)):06d}"
    text = f"{frame:.9f}".rstrip("0").rstrip(".")
    return text.replace("-", "m").replace(".", "p")


def _worker_preview(payload: Mapping[str, Any]) -> dict[str, Any]:
    import bpy  # type: ignore

    blend = str(payload["blend"])
    output_dir = str(payload["out_dir"])
    start = float(payload["start"])
    end = float(payload["end"])
    step = float(payload["step"])
    maximum = int(payload.get("max_frames", 240))
    values = _worker_frame_values(start, end, step, maximum)
    os.makedirs(output_dir, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
    scene = bpy.context.scene
    original_frame = float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0))
    original_path = str(scene.render.filepath)
    original_resolution = (scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage)
    render_settings = _worker_apply_render_settings(scene, payload)
    frames: list[dict[str, Any]] = []
    try:
        for frame in values:
            _worker_set_frame(scene, frame)
            token = _worker_frame_token(frame)
            path = os.path.join(output_dir, f"frame_{token}.png")
            scene.render.filepath = path
            started = time.monotonic()
            bpy.ops.render.render(write_still=True)
            elapsed = time.monotonic() - started
            image_path = __import__("pathlib").Path(path)
            size = _worker_png_size(image_path)
            frames.append(
                {
                    "requested_frame": frame,
                    "scene_frame_after_set": float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0)),
                    "path": path,
                    "exists": image_path.is_file(),
                    "size_bytes": image_path.stat().st_size if image_path.is_file() else None,
                    "sha256": _worker_sha256(image_path),
                    "png_size": list(size) if size else None,
                    "render_seconds": elapsed,
                }
            )
    finally:
        try:
            _worker_set_frame(scene, original_frame)
        except Exception:
            pass
        scene.render.filepath = original_path
        scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = original_resolution
    return {
        "blend_filepath": str(bpy.data.filepath),
        "out_dir": output_dir,
        "requested_range": {"start": start, "end": end, "step": step, "frames": values},
        "scene_fps": float(scene.render.fps) / float(scene.render.fps_base or 1.0),
        "render_settings": render_settings,
        "frames": frames,
        "frame_preserved": abs(
            (float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0))) - original_frame
        )
        <= 1e-9,
        "sequence_review_required": True,
        "review_note": "A contact sheet is only a navigation aid. Review the frame sequence at full speed and slow motion; inspect contact, loop, and abrupt-change frames individually.",
    }


def _worker_png_size(path: Any) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def _worker_sha256(path: Any) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _worker_probe() -> dict[str, Any]:
    import bpy  # type: ignore

    build_hash_value = getattr(bpy.app, "build_hash", "")
    if isinstance(build_hash_value, bytes):
        build_hash_value = build_hash_value.decode("ascii", errors="replace")
    action = bpy.data.actions.new("__blender_animation_probe_action__")
    try:
        action_features = {
            "instance_has_slots": hasattr(action, "slots"),
            "instance_has_layers": hasattr(action, "layers"),
            "instance_has_legacy_fcurves": hasattr(action, "fcurves"),
            "frame_range": [float(x) for x in action.frame_range],
        }
    finally:
        bpy.data.actions.remove(action)
    return {
        "blender_version": list(bpy.app.version),
        "blender_version_string": str(bpy.app.version_string),
        "build_hash": str(build_hash_value),
        "background": bool(getattr(bpy.app, "background", False)),
        "python_version": list(__import__("sys").version_info[:3]),
        "action_feature_detection": action_features,
        "operators": {
            "render": hasattr(bpy.ops.render, "render"),
            "save_mainfile": hasattr(bpy.ops.wm, "save_as_mainfile"),
            "gltf_export": hasattr(bpy.ops.export_scene, "gltf"),
            "fbx_export": hasattr(bpy.ops.export_scene, "fbx"),
            "gltf_import": hasattr(bpy.ops.import_scene, "gltf"),
            "fbx_import": hasattr(bpy.ops.import_scene, "fbx"),
        },
        "data_api": {
            "evaluated_depsgraph": hasattr(bpy.context.scene, "view_layers"),
            "timeline_markers": hasattr(bpy.context.scene, "timeline_markers"),
        },
    }


def _worker_has_animation_or_constraints(obj: Any) -> bool:
    if getattr(obj, "animation_data", None) is not None:
        return True
    if getattr(obj, "constraints", None):
        return True
    data = getattr(obj, "data", None)
    if data is not None and getattr(data, "animation_data", None) is not None:
        return True
    if obj.type == "ARMATURE" and getattr(obj, "pose", None):
        return any(getattr(bone, "constraints", None) for bone in obj.pose.bones)
    return False


def _worker_export_scope(scene: Any, scope: str) -> dict[str, Any]:
    """Choose export objects without silently dropping animated review objects."""

    if scope not in {"asset", "scene"}:
        raise ValueError("export scope must be 'asset' or 'scene'")
    objects = list(scene.objects)
    review_types = {"CAMERA", "LIGHT", "SPEAKER"}
    if scope == "scene":
        included = list(objects)
        excluded: list[Any] = []
    else:
        included = [obj for obj in objects if obj.type not in review_types]
        excluded = [obj for obj in objects if obj.type in review_types]
        # Keep a parent chain if an asset object depends on a review object for
        # its world transform. This is intentionally visible in the report.
        included_names = {obj.name for obj in included}
        required_review_parents: list[Any] = []
        for obj in list(included):
            parent = getattr(obj, "parent", None)
            while parent is not None:
                if parent.type in review_types and parent.name not in included_names:
                    included.append(parent)
                    included_names.add(parent.name)
                    required_review_parents.append(parent)
                parent = getattr(parent, "parent", None)
        excluded = [obj for obj in objects if obj.name not in included_names]

    animated_review = [obj for obj in objects if obj.type in review_types and _worker_has_animation_or_constraints(obj)]
    animated_review_names = {obj.name for obj in animated_review}
    required_review_parents = [
        obj for obj in included if obj.type in review_types and obj.name not in animated_review_names
    ]
    if scope == "asset" and animated_review:
        status = "unsupported_requested_animated_review_objects"
    else:
        status = "ready"
    excluded_records = []
    for obj in excluded:
        excluded_records.append(
            {
                "name": obj.name,
                "type": obj.type,
                "animated_or_constrained": _worker_has_animation_or_constraints(obj),
                "reason": "static review object omitted by asset scope",
            }
        )
    return {
        "mode": scope,
        "status": status,
        "included_objects": [obj.name for obj in included],
        "included_types": {obj.name: obj.type for obj in included},
        "excluded_review_objects": excluded_records,
        "animated_review_objects": [
            {"name": obj.name, "type": obj.type, "reason": "animated or constrained review object cannot be silently omitted"}
            for obj in animated_review
        ],
        "required_review_parents": [
            {"name": obj.name, "type": obj.type, "reason": "parent required by an included asset object"}
            for obj in required_review_parents
        ],
        "selection_rule": "asset scope includes non-review asset objects and required parents; scene scope includes all scene objects",
    }


def _worker_readback(payload: Mapping[str, Any]) -> dict[str, Any]:
    import bpy  # type: ignore

    source_blend = str(payload["source_blend"])
    export_path = str(payload["export_path"])
    format_name = str(payload["format"]).lower()
    bpy.ops.wm.open_mainfile(filepath=source_blend, load_ui=False)
    before_objects = {obj.name for obj in bpy.context.scene.objects}
    if format_name == "glb":
        result = bpy.ops.import_scene.gltf(filepath=export_path)
    elif format_name == "fbx":
        result = bpy.ops.import_scene.fbx(filepath=export_path)
    else:
        raise ValueError(f"unsupported readback format: {format_name}")
    imported_objects = [obj for obj in bpy.context.scene.objects if obj.name not in before_objects]
    imported_actions = []
    for obj in imported_objects:
        animation_data = getattr(obj, "animation_data", None)
        action = getattr(animation_data, "action", None) if animation_data else None
        if action:
            imported_actions.append(
                {
                    "object": obj.name,
                    "action": action.name,
                    "frame_range": [float(x) for x in action.frame_range],
                }
            )
        if animation_data:
            for track in getattr(animation_data, "nla_tracks", []):
                for strip in getattr(track, "strips", []):
                    strip_action = getattr(strip, "action", None)
                    if strip_action:
                        imported_actions.append(
                            {
                                "object": obj.name,
                                "nla_track": str(getattr(track, "name", "")),
                                "strip": str(getattr(strip, "name", "")),
                                "action": strip_action.name,
                                "frame_range": [float(x) for x in strip_action.frame_range],
                            }
                        )
        data = getattr(obj, "data", None)
        data_action = getattr(getattr(data, "animation_data", None), "action", None) if data else None
        if data_action:
            imported_actions.append(
                {
                    "object": obj.name,
                    "datablock": str(getattr(data, "name", "")),
                    "action": data_action.name,
                    "frame_range": [float(x) for x in data_action.frame_range],
                }
            )
    expected_names = [str(name) for name in payload.get("expected_animated_objects", [])]
    expected_types = {
        str(name): str(value)
        for name, value in dict(payload.get("expected_animated_object_types", {})).items()
    }
    all_ranges = [
        frame
        for action in imported_actions
        for frame in action.get("frame_range", [])
        if isinstance(frame, (int, float)) and math.isfinite(float(frame))
    ]
    if all_ranges:
        sample_start = min(float(frame) for frame in all_ranges)
        sample_end = max(float(frame) for frame in all_ranges)
    else:
        sample_start = float(bpy.context.scene.frame_start)
        sample_end = float(bpy.context.scene.frame_end)
    sample_frames = [sample_start]
    if sample_end > sample_start:
        sample_frames.extend([(sample_start + sample_end) / 2.0, sample_end])
    sample_frames = list(dict.fromkeys(sample_frames))
    original_frame = float(bpy.context.scene.frame_current) + float(getattr(bpy.context.scene, "frame_subframe", 0.0))
    temporal_samples: list[dict[str, Any]] = []
    try:
        for frame in sample_frames:
            _worker_set_frame(bpy.context.scene, frame)
            depsgraph = bpy.context.scene.view_layers[0].depsgraph
            evaluated = _worker_evaluated_scene_record(bpy.context.scene, depsgraph)
            temporal_samples.append(
                {
                    "frame": frame,
                    "objects": [
                        obj
                        for obj in evaluated.get("objects", [])
                        if obj.get("name") in {item.name for item in imported_objects}
                    ],
                }
            )
    finally:
        _worker_set_frame(bpy.context.scene, original_frame)
    imported_name_set = {item.name for item in imported_objects}
    expected_found = [name for name in expected_names if name in imported_name_set]
    if expected_names and not expected_found:
        # FBX importers may suffix a duplicate name. Keep a transparent prefix
        # match as evidence, while reporting the actual imported names.
        expected_found = [
            name
            for name in expected_names
            if any(imported_name.startswith(name + ".") for imported_name in imported_name_set)
        ]

    def object_signature(obj: Mapping[str, Any]) -> tuple[Any, ...]:
        values: list[Any] = []
        world = obj.get("evaluated_world", {})
        values.extend(world.get("translation") or [])
        values.extend(world.get("quaternion") or [])
        # Dimensions expose evaluated armature deformation when a target
        # importer materializes a skinned mesh under a proxy Empty.
        values.extend(obj.get("dimensions") or [])
        for pose_bone in (obj.get("armature") or {}).get("pose_bones", []):
            bone_world = pose_bone.get("world", {})
            values.extend(bone_world.get("translation") or [])
            values.extend(bone_world.get("quaternion") or [])
        return tuple(float(value) for value in values if isinstance(value, (int, float)))

    per_object_signatures: dict[str, list[tuple[Any, ...]]] = {}
    for state in temporal_samples:
        for obj in state.get("objects", []):
            per_object_signatures.setdefault(str(obj.get("name")), []).append(object_signature(obj))

    per_object_time_varying: dict[str, bool] = {}
    for name, signatures in per_object_signatures.items():
        per_object_time_varying[name] = any(
            any(abs(first - second) > 1e-6 for first, second in zip(signatures[0], signature))
            for signature in signatures[1:]
        ) if signatures else False

    object_records_by_name = {
        str(obj.get("name")): obj
        for state in temporal_samples
        for obj in state.get("objects", [])
    }
    expected_time_varying: dict[str, bool] = {}
    expected_evidence: dict[str, dict[str, Any]] = {}
    for expected_name in expected_names:
        candidate_names = [
            imported_name
            for imported_name in per_object_time_varying
            if imported_name == expected_name or imported_name.startswith(expected_name + ".")
        ]
        direct_time_varying = any(
            per_object_time_varying[name] for name in candidate_names
        )
        proxy_candidates: list[str] = []
        if not direct_time_varying and expected_types.get(expected_name) == "MESH":
            # glTF commonly imports an animated skinned mesh as a proxy Empty
            # plus a differently named mesh child. Attribute that evidence to
            # the expected mesh only when the child is parented to a varying
            # imported armature and its evaluated dimensions change.
            varying_armatures = {
                name
                for name, varying in per_object_time_varying.items()
                if varying and object_records_by_name.get(name, {}).get("type") == "ARMATURE"
            }
            for name, record in object_records_by_name.items():
                if (
                    record.get("type") == "MESH"
                    and record.get("parent") in varying_armatures
                    and per_object_time_varying.get(name, False)
                ):
                    proxy_candidates.append(name)
        expected_time_varying[expected_name] = bool(direct_time_varying or proxy_candidates)
        expected_evidence[expected_name] = {
            "direct_candidates": candidate_names,
            "direct_time_varying": direct_time_varying,
            "deformation_proxy_candidates": proxy_candidates,
        }
    transform_time_varying = any(per_object_time_varying.values())
    animation_survived = bool(imported_actions) and (
        all(expected_time_varying.values()) if expected_names else (transform_time_varying or len(sample_frames) == 1)
    )
    return {
        "ok": True,
        "operator_result": list(result) if result else [],
        "format": format_name,
        "imported_object_count": len(imported_objects),
        "imported_objects": [
            {"name": obj.name, "type": obj.type, "animation": bool(getattr(obj, "animation_data", None))}
            for obj in imported_objects
        ],
        "imported_actions": imported_actions,
        "expected_animated_objects": expected_names,
        "expected_animated_object_types": expected_types,
        "expected_animated_objects_found": expected_found,
        "expected_proxy_objects_found": {
            name: list(evidence.get("deformation_proxy_candidates", []))
            for name, evidence in expected_evidence.items()
            if evidence.get("deformation_proxy_candidates")
        },
        "temporal_samples": temporal_samples,
        "animation_survived_readback": animation_survived,
        "transform_time_varying": transform_time_varying,
        "per_object_time_varying": per_object_time_varying,
        "expected_object_time_varying": expected_time_varying,
        "expected_object_evidence": expected_evidence,
        "sample_frames": sample_frames,
        "missing_assets": _worker_missing_assets(),
        "readback_semantics": "import/readback evidence only; no claim that target preserves Blender-native constraints, drivers, slots, or simulation logic",
    }


def _worker_export_branch(payload: Mapping[str, Any]) -> dict[str, Any]:
    import bpy  # type: ignore

    source_blend = str(payload["source_blend"])
    branch_blend = str(payload["branch_blend"])
    export_path = str(payload["export_path"])
    format_name = str(payload["format"]).lower()
    bpy.ops.wm.open_mainfile(filepath=source_blend, load_ui=False)
    scene = bpy.context.scene
    source_frame = float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0))
    source_missing_assets = _worker_missing_assets()
    source_simulation_caches = _worker_simulation_caches()
    dependency_policy = (
        "explicit_optional_bypass"
        if bool(payload.get("allow_missing_optional", False))
        else "strict_required"
    )
    source_dependency_completeness = _worker_dependency_completeness(
        source_missing_assets,
        source_simulation_caches,
        dependency_policy,
    )
    if source_dependency_completeness["status"] == "incomplete":
        return {
            "_worker_ok": False,
            "error_kind": "missing_required_dependencies",
            "error": "Source images, libraries, or simulation caches are incomplete under the strict export policy",
            "source_blend": source_blend,
            "branch_blend": branch_blend,
            "export_path": export_path,
            "format": format_name,
            "dependency_completeness": source_dependency_completeness,
            "missing_assets_before_export": source_missing_assets,
            "simulation_caches_before_export": source_simulation_caches,
        }
    export_scope = _worker_export_scope(scene, str(payload.get("scope", "asset")))
    if export_scope["status"] != "ready":
        return {
            "_worker_ok": False,
            "error_kind": export_scope["status"],
            "error": "Asset scope cannot omit animated or constrained review objects; use --scope scene or a target-specific route",
            "source_blend": source_blend,
            "branch_blend": branch_blend,
            "export_path": export_path,
            "format": format_name,
            "export_scope": export_scope,
            "dependency_completeness": source_dependency_completeness,
            "missing_assets_before_export": source_missing_assets,
            "simulation_caches_before_export": source_simulation_caches,
        }
    included_names = set(export_scope["included_objects"])
    source_scope_objects = [obj for obj in scene.objects if obj.name in included_names]
    source_motion_evidence = _worker_source_motion_evidence(scene, source_scope_objects)
    path_preparation = _worker_make_paths_absolute()
    relative_dependencies = [
        record
        for record in source_missing_assets.get("checked", [])
        if str(record.get("filepath", "")).startswith("//") and not bool(record.get("packed", False))
    ]
    if path_preparation.get("status") == "FAILED" or (
        path_preparation.get("status") == "UNAVAILABLE" and relative_dependencies
    ):
        return {
            "_worker_ok": False,
            "error_kind": "dependency_path_prepare_failed",
            "error": "The separate export branch could not resolve source-relative external paths before saving",
            "source_blend": source_blend,
            "branch_blend": branch_blend,
            "export_path": export_path,
            "format": format_name,
            "dependency_completeness": source_dependency_completeness,
            "path_preparation": path_preparation,
            "relative_dependencies": relative_dependencies,
            "source_motion_evidence": source_motion_evidence,
        }
    bpy.ops.wm.save_as_mainfile(filepath=branch_blend)
    branch_saved_before_bake = str(bpy.data.filepath) == branch_blend
    scope_objects = [obj for obj in bpy.data.objects if obj.name in included_names]
    animated_objects = [
        obj
        for obj in scope_objects
        if _worker_has_animation_or_constraints(obj)
    ]
    bake: dict[str, Any]
    if not animated_objects:
        bake = {"status": "not_required", "animated_object_count": 0}
    else:
        # Bake one owner at a time. Blender's NLA bake operator can omit pose
        # channels when an armature and an animated mesh are selected together;
        # the mesh then appears to have exported while the rig is frozen.
        # Dependencies remain evaluable while only the current owner is keyed.
        animated_objects = sorted(
            animated_objects,
            key=lambda obj: (0 if obj.type == "ARMATURE" else 1, obj.name),
        )
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        bake_records: list[dict[str, Any]] = []
        bake_failed: str | None = None
        try:
            for obj in animated_objects:
                for selected in bpy.context.selected_objects:
                    selected.select_set(False)
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bake_types = {"POSE", "OBJECT"} if obj.type == "ARMATURE" else {"OBJECT"}
                result = bpy.ops.nla.bake(
                    frame_start=scene.frame_start,
                    frame_end=scene.frame_end,
                    step=1,
                    # In Blender 5.2, only_selected=True reports CANCELLED
                    # for an object-level bake unless pose selection state is
                    # also prepared. One selected owner plus False bakes that
                    # owner and keeps this route portable across versions.
                    only_selected=False,
                    visual_keying=True,
                    clear_constraints=True,
                    clear_parents=False,
                    use_current_action=False,
                    clean_curves=False,
                    bake_types=bake_types,
                )
                result_list = list(result) if result else []
                bake_records.append(
                    {
                        "object": obj.name,
                        "type": obj.type,
                        "operator_result": result_list,
                        "bake_types": sorted(bake_types),
                    }
                )
                if "FINISHED" not in result_list:
                    bake_failed = f"NLA bake returned {result_list or ['NO_RESULT']} for {obj.name}"
                    break
            bake = {
                "status": "attempted" if not bake_failed else "failed",
                "operator_result": ["FINISHED"] if not bake_failed else [],
                "animated_object_count": len(animated_objects),
                "visual_keying": True,
                "clear_constraints": True,
                "scene_frame_range": [float(scene.frame_start), float(scene.frame_end)],
                "per_object": bake_records,
            }
            if bake_failed:
                bake["error"] = bake_failed
        except Exception as exc:
            bake_failed = str(exc)
            bake = {
                "status": "failed",
                "error": str(exc),
                "animated_object_count": len(animated_objects),
                "visual_keying": True,
                "clear_constraints": True,
                "per_object": bake_records,
            }
    try:
        _worker_set_frame(scene, source_frame)
    except Exception:
        pass
    branch_path_preparation = _worker_make_paths_absolute()
    branch_pre_save_missing_assets = _worker_missing_assets()
    branch_relative_dependencies = [
        record
        for record in branch_pre_save_missing_assets.get("checked", [])
        if str(record.get("filepath", "")).startswith("//") and not bool(record.get("packed", False))
    ]
    if branch_path_preparation.get("status") == "FAILED" or (
        branch_path_preparation.get("status") == "UNAVAILABLE" and branch_relative_dependencies
    ):
        return {
            "_worker_ok": False,
            "error_kind": "branch_dependency_path_prepare_failed",
            "error": "The baked branch could not resolve source-relative external paths before its final save",
            "source_blend": source_blend,
            "branch_blend": branch_blend,
            "export_path": export_path,
            "format": format_name,
            "dependency_completeness": source_dependency_completeness,
            "path_preparation": path_preparation,
            "branch_path_preparation": branch_path_preparation,
            "branch_relative_dependencies": branch_relative_dependencies,
            "branch_saved_before_bake": branch_saved_before_bake,
            "source_motion_evidence": source_motion_evidence,
        }
    bpy.ops.wm.save_as_mainfile(filepath=branch_blend)
    branch_saved_after_bake = str(bpy.data.filepath) == branch_blend
    # Reopen the saved branch before export. This catches relative texture,
    # linked-library, and cache paths that only fail after save-as-mainfile.
    bpy.ops.wm.open_mainfile(filepath=branch_blend, load_ui=False)
    branch_context_reopened = str(bpy.data.filepath) == branch_blend
    branch_missing_assets = _worker_missing_assets()
    branch_simulation_caches = _worker_simulation_caches()
    branch_dependency_completeness = _worker_dependency_completeness(
        branch_missing_assets,
        branch_simulation_caches,
        dependency_policy,
    )
    if branch_dependency_completeness["status"] == "incomplete":
        return {
            "_worker_ok": False,
            "error_kind": "branch_dependency_reopen_failed",
            "error": "Saved export branch reopened with incomplete external dependencies",
            "source_blend": source_blend,
            "branch_blend": branch_blend,
            "export_path": export_path,
            "format": format_name,
            "dependency_completeness": branch_dependency_completeness,
            "source_dependency_completeness": source_dependency_completeness,
            "path_preparation": path_preparation,
            "branch_path_preparation": branch_path_preparation,
            "branch_saved_before_bake": branch_saved_before_bake,
            "branch_saved_after_bake": branch_saved_after_bake,
            "branch_context_reopened": branch_context_reopened,
            "source_motion_evidence": source_motion_evidence,
            "missing_assets_before_export": source_missing_assets,
            "simulation_caches_before_export": source_simulation_caches,
            "missing_assets_after_reopen": branch_missing_assets,
            "simulation_caches_after_reopen": branch_simulation_caches,
        }
    scene = bpy.context.scene
    export_scope = _worker_export_scope(scene, str(payload.get("scope", "asset")))
    if export_scope["status"] != "ready":
        return {
            "_worker_ok": False,
            "error_kind": export_scope["status"],
            "error": "Saved export branch contains animated or constrained review objects excluded by asset scope",
            "source_blend": source_blend,
            "branch_blend": branch_blend,
            "export_path": export_path,
            "format": format_name,
            "export_scope": export_scope,
            "dependency_completeness": branch_dependency_completeness,
            "source_motion_evidence": source_motion_evidence,
        }
    included_names = set(export_scope["included_objects"])
    scope_objects = [obj for obj in bpy.data.objects if obj.name in included_names]
    animated_objects = [obj for obj in scope_objects if _worker_has_animation_or_constraints(obj)]
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in scope_objects:
        obj.select_set(True)
    if scope_objects:
        bpy.context.view_layer.objects.active = scope_objects[0]
    if format_name == "glb":
        operator = bpy.ops.export_scene.gltf
        try:
            result = operator(
                filepath=export_path,
                export_format="GLB",
                export_animations=True,
                export_frame_range=True,
                export_nla_strips=True,
                use_selection=True,
            )
        except TypeError:
            raise RuntimeError("glTF exporter does not expose the required use_selection scope option")
    elif format_name == "fbx":
        operator = bpy.ops.export_scene.fbx
        try:
            result = operator(
                filepath=export_path,
                bake_anim=True,
                bake_anim_use_all_actions=True,
                bake_anim_use_nla_strips=True,
                bake_anim_step=1.0,
                add_leaf_bones=False,
                use_selection=True,
            )
        except TypeError:
            raise RuntimeError("FBX exporter does not expose the required use_selection scope option")
    else:
        raise ValueError(f"unsupported export format: {format_name}")
    return {
        "source_blend": source_blend,
        "branch_blend": branch_blend,
        "branch_saved_before_bake": branch_saved_before_bake,
        "export_path": export_path,
        "format": format_name,
        "export_scope": export_scope,
        "expected_animated_objects": [obj.name for obj in animated_objects],
        "expected_animated_object_types": {obj.name: obj.type for obj in animated_objects},
        "motion_expectation": "static_explicitly_allowed" if bool(payload.get("allow_static", False)) else "animation_required",
        "source_motion_evidence": source_motion_evidence,
        "bake": bake,
        "operator_result": list(result) if result else [],
        "source_frame_restored": float(scene.frame_current) + float(getattr(scene, "frame_subframe", 0.0)),
        "missing_assets_before_export": source_missing_assets,
        "simulation_caches_before_export": source_simulation_caches,
        "missing_assets_after_reopen": branch_missing_assets,
        "simulation_caches_after_reopen": branch_simulation_caches,
        "source_dependency_completeness": source_dependency_completeness,
        "dependency_completeness": branch_dependency_completeness,
        "dependency_policy": dependency_policy,
        "portable_delivery": portable_delivery_assessment(
            branch_missing_assets,
            branch_simulation_caches,
        ),
        "path_preparation": path_preparation,
        "branch_path_preparation": branch_path_preparation,
        "branch_saved_after_bake": branch_saved_after_bake,
        "branch_context_reopened": branch_context_reopened,
        "native_editable_source_preserved": "source process opened and wrote a separate branch; target export is not claimed native-editable",
    }


def worker_dispatch(payload: Mapping[str, Any]) -> dict[str, Any]:
    command = str(payload.get("command", ""))
    if command == "probe":
        return {"ok": True, "result": _worker_probe()}
    if command == "inspect":
        return {"ok": True, "result": _worker_inspect(payload)}
    if command == "sample":
        return {"ok": True, "result": _worker_sample(payload)}
    if command == "preview":
        return {"ok": True, "result": _worker_preview(payload)}
    if command == "export_branch":
        branch_result = _worker_export_branch(payload)
        worker_ok = bool(branch_result.pop("_worker_ok", True))
        return {"ok": worker_ok, "result": branch_result}
    if command == "readback":
        return {"ok": True, "result": _worker_readback(payload)}
    raise ValueError(f"unknown Blender worker command: {command}")


def blender_worker_entry() -> int:
    index = sys.argv.index(WORKER_MARKER)
    payload = json.loads(sys.argv[index + 1])
    try:
        result = worker_dispatch(payload)
    except Exception as exc:  # noqa: BLE001 - worker protocol must report traceback
        import traceback

        result = {
            "ok": False,
            "error_kind": "worker_exception",
            "error": str(exc),
            "traceback": traceback.format_exc(limit=20),
        }
    protocol_path = payload.get("protocol_path")
    if protocol_path:
        try:
            protocol_file = Path(str(protocol_path))
            protocol_file.parent.mkdir(parents=True, exist_ok=True)
            protocol_file.write_text(
                json.dumps(result, separators=(",", ":"), ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            # Keep the compact stdout fallback available if the protocol path
            # is not writable.
            pass
    print(WORKER_SENTINEL + json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0 if result.get("ok") else 1


# ---------------------------------------------------------------------------
# CLI command handlers.
# ---------------------------------------------------------------------------


def command_probe(args: argparse.Namespace) -> int:
    started = utc_now()
    blender = resolve_executable(args.blender)
    if blender is None:
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "command": "probe",
            "started_at": started,
            "finished_at": utc_now(),
            "ok": False,
            "error_kind": "blender_not_found",
            "error": "No executable found. Pass --blender, set BLENDER_BIN, or install Blender on PATH.",
            "runtime": {"blender": None, "platform": platform.platform()},
        }
        return emit_receipt(receipt, safe_path(args.out) if args.out else None, args.pretty)
    worker = run_blender(blender, {"command": "probe"}, args.timeout)
    receipt = standard_receipt("probe", blender, worker, started)
    return emit_receipt(receipt, safe_path(args.out) if args.out else None, args.pretty)


def common_worker_command(args: argparse.Namespace, command: str) -> tuple[Path, dict[str, Any], str]:
    blend = ensure_blend(args.blend)
    blender = resolve_executable(args.blender)
    if blender is None:
        raise FileNotFoundError("No Blender executable found")
    payload = {"command": command, "blend": str(blend)}
    started = utc_now()
    return blender, payload, started


def command_inspect(args: argparse.Namespace) -> int:
    try:
        blender, payload, started = common_worker_command(args, "inspect")
        worker = run_blender(blender, payload, args.timeout)
        receipt = standard_receipt("inspect", blender, worker, started)
        receipt["input"] = file_record(safe_path(args.blend))
    except Exception as exc:
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "command": "inspect",
            "started_at": utc_now(),
            "finished_at": utc_now(),
            "ok": False,
            "error_kind": "input_or_runtime",
            "error": str(exc),
        }
    return emit_receipt(receipt, safe_path(args.out) if args.out else None, args.pretty)


def command_sample(args: argparse.Namespace) -> int:
    try:
        blender, payload, started = common_worker_command(args, "sample")
        payload.update(
            {
                "start": args.start,
                "end": args.end,
                "step": args.step,
                "max_frames": args.max_frames,
            }
        )
        worker = run_blender(blender, payload, args.timeout)
        receipt = standard_receipt("sample", blender, worker, started)
        receipt["input"] = file_record(safe_path(args.blend))
    except Exception as exc:
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "command": "sample",
            "started_at": utc_now(),
            "finished_at": utc_now(),
            "ok": False,
            "error_kind": "input_or_runtime",
            "error": str(exc),
        }
    return emit_receipt(receipt, safe_path(args.out) if args.out else None, args.pretty)


def command_preview(args: argparse.Namespace) -> int:
    blender: Path | None = None
    try:
        blender, payload, started = common_worker_command(args, "preview")
        output_dir = safe_path(args.out_dir)
        width, height = parse_resolution(args.resolution)
        payload.update(
            {
                "out_dir": str(output_dir),
                "start": args.start,
                "end": args.end,
                "step": args.step,
                "max_frames": args.max_frames,
                "width": width,
                "height": height,
                "samples": args.samples,
            }
        )
        worker = run_blender(blender, payload, args.timeout)
        receipt = standard_receipt("preview", blender, worker, started)
        receipt["input"] = file_record(safe_path(args.blend))
        receipt["review_policy"] = {
            "contact_sheet_is_navigation_only": True,
            "full_speed_review_required": bool(args.video),
            "slow_motion_review_required": bool(args.slow_video),
            "sequence_frame_review_required": True,
        }
        if receipt.get("ok") and (args.video or args.slow_video):
            ffmpeg = resolve_ffmpeg(args.ffmpeg)
            ffprobe = resolve_ffprobe(args.ffprobe)
            if ffmpeg is None:
                if args.video:
                    receipt["video"] = {"ok": False, "error_kind": "ffmpeg_not_found"}
                if args.slow_video:
                    receipt["slow_video"] = {"ok": False, "error_kind": "ffmpeg_not_found"}
                receipt["ok"] = False
            else:
                render_result = receipt.get("result", {})
                frames = render_result.get("frames", []) if isinstance(render_result, dict) else []
                frame_paths = [Path(str(item.get("path", ""))) for item in frames]
                valid_frames = bool(frame_paths) and all(path.is_file() for path in frame_paths)
                requested_range = render_result.get("requested_range", {}) if isinstance(render_result, dict) else {}
                sampled_frames = [
                    float(value)
                    for value in requested_range.get("frames", [])
                    if isinstance(value, (int, float)) and math.isfinite(float(value))
                ]
                if len(sampled_frames) != len(frame_paths):
                    sampled_frames = [
                        float(item.get("requested_frame"))
                        for item in frames
                        if isinstance(item.get("requested_frame"), (int, float))
                    ]
                source_fps = float(render_result.get("scene_fps") or 24.0)
                requested_step = float(requested_range.get("step") or args.step)
                explicit_video_fps = args.video_fps is not None
                if explicit_video_fps:
                    effective_fps = float(args.video_fps)
                    if not math.isfinite(effective_fps) or effective_fps <= 0.0:
                        raise ValueError("--video-fps must be finite and greater than zero")
                    timing_mode = "retimed_override"
                    frame_durations = [1.0 / effective_fps for _ in sampled_frames]
                    source_duration = float(sum(frame_durations))
                    source_preserving = False
                    uniform_intervals = None
                else:
                    if not math.isfinite(source_fps) or source_fps <= 0.0:
                        raise ValueError("rendered scene FPS must be finite and greater than zero")
                    frame_durations = source_preserving_durations(sampled_frames, source_fps)
                    intervals = [
                        right - left for left, right in zip(sampled_frames, sampled_frames[1:])
                    ]
                    positive_intervals = [value for value in intervals if value > 0.0]
                    uniform_intervals = bool(
                        not positive_intervals
                        or all(abs(value - positive_intervals[0]) <= 1e-9 for value in positive_intervals)
                    )
                    timing_mode = "source_preserving_uniform" if uniform_intervals else "source_preserving_concat"
                    effective_fps = (
                        source_fps / positive_intervals[0]
                        if positive_intervals
                        else source_fps
                    )
                    source_duration = float(sum(frame_durations))
                    source_preserving = True
                receipt["video_timing"] = {
                    "source_fps": source_fps,
                    "sample_frames": sampled_frames,
                    "requested_step": requested_step,
                    "uniform_intervals": uniform_intervals,
                    "timing_mode": timing_mode,
                    "effective_fps": effective_fps,
                    "frame_durations_seconds": frame_durations,
                    "source_duration_seconds": source_duration,
                    "explicit_video_fps": args.video_fps,
                    "source_preserving": source_preserving,
                    "full_speed_label": bool(source_preserving),
                    "slow_motion_factor": 2.0 if args.slow_video else 1.0,
                    "endpoint_policy": "requested_end_included; final frame gets the preceding positive interval hold",
                }
                try:
                    def encode_video(output_value: str, slow: bool) -> dict[str, Any]:
                        output_path = safe_path(output_value)
                        if not valid_frames:
                            return {"ok": False, "error_kind": "render_frames_missing", "path": str(output_path)}
                        result = run_ffmpeg_timed_sequence(
                            ffmpeg,
                            frame_paths,
                            frame_durations,
                            output_path,
                            slow=slow,
                            timeout=args.timeout,
                            timing_mode=timing_mode,
                        )
                        expected_duration = (
                            source_duration * (2.0 if slow else 1.0)
                            if source_preserving
                            else (len(frame_paths) / effective_fps) * (2.0 if slow else 1.0)
                        )
                        result["full_speed_label"] = bool(source_preserving and not slow)
                        result["source_preserving"] = source_preserving
                        result["expected_duration_seconds"] = expected_duration
                        if result.get("ok") and output_path.is_file():
                            result["duration_probe"] = probe_media_duration(ffprobe, output_path, args.timeout)
                            actual_duration = result["duration_probe"].get("duration_seconds")
                            if isinstance(actual_duration, (int, float)):
                                result["duration_error_seconds"] = float(actual_duration) - expected_duration
                        return result

                    if args.video:
                        receipt["video"] = encode_video(args.video, slow=False)
                    if args.slow_video:
                        receipt["slow_video"] = encode_video(args.slow_video, slow=True)
                    if any(not receipt.get(name, {}).get("ok") for name in ("video", "slow_video") if name in receipt):
                        receipt["ok"] = False
                finally:
                    pass
    except Exception as exc:
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "command": "preview",
            "started_at": utc_now(),
            "finished_at": utc_now(),
            "ok": False,
            "error_kind": "input_or_runtime",
            "error": str(exc),
        }
    return emit_receipt(receipt, safe_path(args.out) if args.out else None, args.pretty)


def command_export(args: argparse.Namespace) -> int:
    started = utc_now()
    source: Path | None = None
    blender: Path | None = None
    branch: Path | None = None
    export_path: Path | None = None
    try:
        source = ensure_blend(args.blend)
        # Capture the source before the worker opens anything.  The worker is
        # intended to write only its isolated branch; comparing an after-only
        # hash would prove merely that the file is readable, not that it was
        # left untouched by the export route.
        source_before_sha256 = sha256_file(source)
        blender = resolve_executable(args.blender)
        if blender is None:
            raise FileNotFoundError("No Blender executable found")
        export_path = safe_path(args.out)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_before = file_record(export_path)
        branch_root = Path(tempfile.mkdtemp(prefix="blender-animation-export-"))
        branch = branch_root / "export_branch.blend"
        payload = {
            "command": "export_branch",
            "source_blend": str(source),
            "branch_blend": str(branch),
            "export_path": str(export_path),
            "format": args.format,
            "scope": args.scope,
            "allow_missing_optional": args.allow_missing_optional,
            "allow_static": args.allow_static,
        }
        worker = run_blender(blender, payload, args.timeout)
        receipt = standard_receipt("export", blender, worker, started)
        receipt["input"] = file_record(source)
        receipt["source_before_sha256"] = source_before_sha256
        receipt["source_after_sha256"] = sha256_file(source)
        receipt["export"] = file_record(export_path)
        receipt["export_before"] = export_before
        receipt["branch"] = file_record(branch)
        receipt["native_editable_source_preserved"] = (
            source_before_sha256 is not None
            and receipt["source_after_sha256"] == source_before_sha256
        )
        receipt["target_native_editability_claim"] = False
        receipt["export_semantics"] = "interchange artifact; exporter may bake or sample animation and does not preserve Blender-native constraints, drivers, Action Slots, or simulation logic as such"
        result_data = receipt.get("result", {}) if isinstance(receipt.get("result"), dict) else {}
        portable_delivery = result_data.get("portable_delivery")
        if not isinstance(portable_delivery, dict):
            portable_delivery = portable_delivery_assessment(
                result_data.get("missing_assets_after_reopen")
                or result_data.get("missing_assets_before_export"),
                result_data.get("simulation_caches_after_reopen")
                or result_data.get("simulation_caches_before_export"),
            )
        receipt["portable_delivery"] = portable_delivery
        receipt["portable_delivery_complete"] = bool(
            portable_delivery.get("portable_delivery_complete", False)
        )
        if not receipt.get("ok") and result_data.get("error_kind"):
            receipt["error_kind"] = result_data.get("error_kind")
            receipt["error"] = result_data.get("error")
        dependency_completeness = result_data.get("dependency_completeness", {})
        if dependency_completeness:
            receipt["dependency_completeness"] = dependency_completeness
        receipt["motion_expectation"] = result_data.get(
            "motion_expectation",
            "static_explicitly_allowed" if args.allow_static else "animation_required",
        )
        if result_data.get("source_motion_evidence"):
            receipt["source_motion_evidence"] = result_data["source_motion_evidence"]
        bake_result = receipt.get("result", {}).get("bake", {}) if isinstance(receipt.get("result"), dict) else {}
        if receipt.get("ok") and bake_result.get("status") == "failed":
            receipt["ok"] = False
            receipt["error_kind"] = "branch_bake_failed"
            receipt["error"] = "The isolated export branch could not complete the requested visual-keyed bake"
        if receipt.get("ok") and isinstance(receipt.get("result"), dict) and not receipt["result"].get("branch_saved_before_bake", False):
            receipt["ok"] = False
            receipt["error_kind"] = "branch_save_failed"
            receipt["error"] = "The isolated export branch was not confirmed saved before baking"
        if receipt.get("ok") and isinstance(receipt.get("result"), dict) and not receipt["result"].get("branch_saved_after_bake", False):
            receipt["ok"] = False
            receipt["error_kind"] = "branch_save_after_bake_failed"
            receipt["error"] = "The baked branch was not confirmed saved before export"
        if receipt.get("ok") and isinstance(receipt.get("result"), dict) and not receipt["result"].get("branch_context_reopened", False):
            receipt["ok"] = False
            receipt["error_kind"] = "branch_reopen_context_failed"
            receipt["error"] = "The saved branch could not be reopened at the exact staged path before export"
        if receipt.get("ok") and export_path.is_file() and branch.is_file():
            expected_animated_objects = []
            expected_animated_object_types: dict[str, str] = {}
            if isinstance(receipt.get("result"), dict):
                expected_animated_objects = receipt["result"].get("expected_animated_objects", [])
                expected_animated_object_types = receipt["result"].get("expected_animated_object_types", {})
            readback_payload = {
                "command": "readback",
                "source_blend": str(branch),
                "export_path": str(export_path),
                "format": args.format,
                "expected_animated_objects": expected_animated_objects,
                "expected_animated_object_types": expected_animated_object_types,
            }
            readback_worker = run_blender(blender, readback_payload, args.timeout)
            receipt["readback"] = standard_receipt("export_readback", blender, readback_worker, utc_now())
            if not receipt["readback"].get("ok"):
                receipt["ok"] = False
            elif expected_animated_objects and not receipt["readback"].get("result", {}).get("animation_survived_readback", False):
                receipt["ok"] = False
                receipt["error_kind"] = "animation_readback_missing_or_static"
                receipt["error"] = "Export readback found no time-varying imported animation for the expected animated objects"
                receipt["motion_readback_status"] = "INCOMPLETE"
            elif not expected_animated_objects:
                if args.allow_static:
                    receipt["motion_readback_status"] = "STATIC_READBACK_ALLOWED"
                else:
                    receipt["ok"] = False
                    receipt["error_kind"] = "static_readback_without_explicit_allowance"
                    receipt["error"] = "No animated or constrained asset objects were found; pass --allow-static for an intentional static interchange export"
                    receipt["motion_readback_status"] = "STATIC_READBACK"
            else:
                receipt["motion_readback_status"] = "TIME_VARYING_READBACK"
        else:
            receipt["readback"] = {"ok": False, "error_kind": "export_artifact_missing"}
            receipt["ok"] = False
        if not args.keep_branch:
            shutil.rmtree(branch_root, ignore_errors=True)
            receipt["branch_cleanup"] = "removed_after_readback"
        else:
            receipt["branch_cleanup"] = "kept"
        export_generated = bool(
            receipt.get("export", {}).get("exists")
            and (
                not export_before.get("exists")
                or receipt.get("export", {}).get("sha256") != export_before.get("sha256")
            )
        )
        if receipt.get("ok"):
            if dependency_completeness.get("status") == "explicit_optional_bypass":
                receipt["verification_status"] = "VERIFIED_WITH_OPTIONAL_MISSING"
                receipt["complete_delivery"] = False
            elif receipt.get("motion_readback_status") == "STATIC_READBACK_ALLOWED":
                receipt["verification_status"] = "STATIC_READBACK_ALLOWED"
                receipt["complete_delivery"] = bool(receipt["portable_delivery_complete"])
            else:
                receipt["verification_status"] = "VERIFIED"
                # VERIFIED describes fresh interchange readback. A complete
                # portable delivery additionally requires dependency bundling
                # evidence, which this helper deliberately does not claim for
                # external source paths.
                receipt["complete_delivery"] = bool(receipt["portable_delivery_complete"])
        elif export_generated:
            receipt["verification_status"] = "PARTIAL_VERIFIED"
        else:
            receipt["verification_status"] = "FAILED"
    except Exception as exc:
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "command": "export",
            "started_at": started,
            "finished_at": utc_now(),
            "ok": False,
            "error_kind": "input_or_runtime",
            "error": str(exc),
            "native_editable_source_preserved": None,
            "target_native_editability_claim": False,
            "verification_status": "FAILED",
        }
    return emit_receipt(receipt, safe_path(args.receipt) if args.receipt else None, args.pretty)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="indent JSON output")
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe = subparsers.add_parser("probe", help="probe the selected Blender executable and API features")
    probe.add_argument("--blender", help="Blender executable; overrides BLENDER_BIN")
    probe.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    probe.add_argument("--out", help="write the JSON receipt to this path")
    probe.set_defaults(handler=command_probe)

    def add_blend_command(name: str, help_text: str) -> argparse.ArgumentParser:
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--blender", help="Blender executable; overrides BLENDER_BIN")
        command.add_argument("--blend", required=True, help="input .blend path")
        command.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
        command.add_argument("--out", help="write JSON receipt to this path")
        return command

    inspect = add_blend_command("inspect", "inspect source Actions, Slots, NLA, rigs, channels, markers, and caches")
    inspect.set_defaults(handler=command_inspect)

    sample = add_blend_command("sample", "sample evaluated scene, armature, world, and root motion state")
    sample.add_argument("--start", type=float, required=True)
    sample.add_argument("--end", type=float, required=True)
    sample.add_argument("--step", type=float, default=1.0)
    sample.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES)
    sample.set_defaults(handler=command_sample)

    preview = add_blend_command("preview", "render a temporally indexed PNG sequence with optional ffmpeg videos")
    preview.add_argument("--out-dir", required=True, help="directory for frame PNGs")
    preview.add_argument("--start", type=float, required=True)
    preview.add_argument("--end", type=float, required=True)
    preview.add_argument("--step", type=float, default=1.0)
    preview.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES)
    preview.add_argument("--resolution", default="512x512", help="WIDTHxHEIGHT or a square integer")
    preview.add_argument("--samples", type=int)
    preview.add_argument("--video", help="optional full-speed ffmpeg output path")
    preview.add_argument("--slow-video", help="optional two-times-duration ffmpeg output path")
    preview.add_argument(
        "--video-fps",
        type=float,
        default=None,
        help="explicit retime FPS; omission preserves source FPS and sampled frame intervals",
    )
    preview.add_argument("--ffmpeg", help="ffmpeg executable; overrides FFMPEG_BIN")
    preview.add_argument("--ffprobe", help="ffprobe executable; overrides FFPROBE_BIN")
    preview.set_defaults(handler=command_preview)

    export = subparsers.add_parser("export", help="export a separate baked branch and read it back")
    export.add_argument("--blender", help="Blender executable; overrides BLENDER_BIN")
    export.add_argument("--blend", required=True, help="source .blend path")
    export.add_argument("--format", required=True, choices=("glb", "fbx"))
    export.add_argument(
        "--scope",
        choices=("asset", "scene"),
        default="asset",
        help="asset excludes static review cameras/lights; scene includes every scene object",
    )
    export.add_argument(
        "--allow-missing-optional",
        action="store_true",
        help="explicitly declare missing external assets/caches optional; receipt remains incomplete-visible",
    )
    export.add_argument(
        "--allow-static",
        action="store_true",
        help="allow a static interchange export; otherwise an animation export needs motion evidence",
    )
    export.add_argument("--out", required=True, help="target .glb or .fbx artifact path")
    export.add_argument("--receipt", help="write JSON receipt to this path")
    export.add_argument("--keep-branch", action="store_true", help="keep the temporary baked branch for audit")
    export.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    export.set_defaults(handler=command_export)
    return parser


def cli_entry() -> int:
    if WORKER_MARKER in sys.argv:
        return blender_worker_entry()
    parser = build_parser()
    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(cli_entry())
