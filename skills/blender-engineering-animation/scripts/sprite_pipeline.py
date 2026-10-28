#!/usr/bin/env python3
"""Portable sprite timeline, atlas, validation, and preview helper.

This module deliberately has no Blender dependency.  It packs an explicit
timeline JSON file and PNG frames into a deterministic RGBA atlas while
preserving frame durations, action tags, logical canvas offsets, and pivots.
Pillow is an optional dependency for the programmatic PNG/atlas/GIF route.
An Aseprite file remains the editable source when one is available; this
helper does not pretend that a generic PNG export is an editable source or
that LibreSprite has Aseprite CLI parity.

The JSON format is documented in ``references/sprites.md``.  Coordinates are
pixel coordinates from the top-left of the logical canvas and atlas.  Atlas
``frame`` rectangles exclude extrusion; ``packed_frame`` includes extrusion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:  # Pillow is optional so --help/probe can work without it.
    from PIL import Image, ImageChops

    PILLOW_AVAILABLE = True
    PILLOW_VERSION = getattr(__import__("PIL"), "__version__", "unknown")
except ImportError:  # pragma: no cover - exercised by packaging environments.
    Image = None  # type: ignore[assignment]
    ImageChops = None  # type: ignore[assignment]
    PILLOW_AVAILABLE = False
    PILLOW_VERSION = None


SCHEMA_TIMELINE = "blender-engineering.sprite-timeline.v1"
SCHEMA_ATLAS = "blender-engineering.sprite-atlas.v1"
LOOP_MODES = {"loop", "once", "pingpong", "reverse"}


class PipelineError(ValueError):
    """A user-actionable input, validation, or packing error."""


@dataclass
class ValidationReport:
    """Structured validation result used by the CLI and unit tests."""

    kind: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": "PASS" if self.ok else "FAIL",
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "checks": self.checks,
        }


@dataclass
class FrameSpec:
    frame_id: str
    source_file: str
    source_path: Path
    duration_ms: int
    action: str
    direction: str | None
    index: int
    pivot: tuple[float, float]
    source_offset: tuple[int, int]
    image: Any = None
    source_hash: str | None = None
    source_size: tuple[int, int] | None = None
    source_mode: str | None = None


@dataclass
class ActionSpec:
    name: str
    frame_ids: list[str]
    loop: str
    direction: str | None = None
    allow_boundary_duplicate: bool = False


def _require_pillow() -> None:
    if not PILLOW_AVAILABLE:
        raise PipelineError(
            "Pillow is optional but missing from the active Python environment. "
            "Install it into an isolated environment for this sprite helper, "
            "for example: python3 -m venv .venv && .venv/bin/python -m pip install Pillow"
        )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise PipelineError(f"JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PipelineError(f"Top-level JSON value must be an object: {path}")
    return data


def _positive_int(value: Any, label: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PipelineError(f"{label} must be an integer")
    if int(value) != value:
        raise PipelineError(f"{label} must be an integer")
    value = int(value)
    if value < 0 or (value == 0 and not allow_zero):
        qualifier = "non-negative" if allow_zero else "positive"
        raise PipelineError(f"{label} must be {qualifier}")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PipelineError(f"{label} must be numeric")
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise PipelineError(f"{label} must be finite")
    return value


def _point(value: Any, label: str, *, default: tuple[float, float] | None = None) -> tuple[float, float]:
    if value is None:
        if default is None:
            raise PipelineError(f"{label} is required")
        return default
    if isinstance(value, Mapping):
        if "x" not in value or "y" not in value:
            raise PipelineError(f"{label} must contain x and y")
        x = _number(value["x"], f"{label}.x")
        y = _number(value["y"], f"{label}.y")
        if value.get("normalized") is True:
            # The caller scales normalized values after it knows the logical
            # canvas.  Keeping this marker avoids silently treating 0..1 as
            # pixel coordinates.
            return x, y
        return x, y
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2:
        return _number(value[0], f"{label}[0]"), _number(value[1], f"{label}[1]")
    raise PipelineError(f"{label} must be an {{x,y}} object or [x,y]")


def _size(value: Any, label: str) -> tuple[int, int]:
    if isinstance(value, Mapping):
        width = value.get("width", value.get("w"))
        height = value.get("height", value.get("h"))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2:
        width, height = value
    else:
        raise PipelineError(f"{label} must be {{width,height}} or [width,height]")
    return _positive_int(width, f"{label}.width"), _positive_int(height, f"{label}.height")


def _loop_mode(value: Any, label: str, default: str = "loop") -> str:
    if value is None:
        return default
    if value is True:
        return "loop"
    if value is False:
        return "once"
    mode = str(value).lower()
    if mode not in LOOP_MODES:
        raise PipelineError(f"{label} must be one of {sorted(LOOP_MODES)}")
    return mode


def _frame_records(raw_frames: Any) -> list[dict[str, Any]]:
    if isinstance(raw_frames, list):
        records = raw_frames
    elif isinstance(raw_frames, Mapping):
        records = []
        for frame_id, value in raw_frames.items():
            if not isinstance(value, Mapping):
                raise PipelineError(f"frames.{frame_id} must be an object")
            record = dict(value)
            record.setdefault("id", frame_id)
            records.append(record)
    else:
        raise PipelineError("timeline.frames must be a list or object")
    if not records:
        raise PipelineError("timeline.frames must not be empty")
    result: list[dict[str, Any]] = []
    for index, value in enumerate(records):
        if not isinstance(value, Mapping):
            raise PipelineError(f"timeline.frames[{index}] must be an object")
        result.append(dict(value))
    return result


def _canvas_from_data(data: Mapping[str, Any]) -> tuple[int, int] | None:
    value = data.get("canvas", data.get("canvas_size"))
    if value is None and "canvas_width" in data and "canvas_height" in data:
        value = {"width": data["canvas_width"], "height": data["canvas_height"]}
    if value is None:
        return None
    return _size(value, "timeline.canvas")


def _resolve_source_path(timeline_path: Path, value: Any, label: str) -> tuple[str, Path]:
    if not isinstance(value, str) or not value:
        raise PipelineError(f"{label}.file must be a non-empty string")
    source_file = value
    source_path = Path(value)
    if not source_path.is_absolute():
        source_path = timeline_path.parent / source_path
    return source_file, source_path


def _normalized_actions(data: Mapping[str, Any], frames: list[FrameSpec]) -> list[ActionSpec]:
    by_id = {frame.frame_id: frame for frame in frames}
    raw_actions = data.get("actions")
    if raw_actions is None:
        grouped: OrderedDict[str, list[str]] = OrderedDict()
        for frame in frames:
            grouped.setdefault(frame.action, []).append(frame.frame_id)
        return [
            ActionSpec(name, ids, _loop_mode(data.get("loop"), "timeline.loop"))
            for name, ids in grouped.items()
        ]

    records: list[tuple[str, Mapping[str, Any]]] = []
    if isinstance(raw_actions, list):
        for index, value in enumerate(raw_actions):
            if not isinstance(value, Mapping):
                raise PipelineError(f"timeline.actions[{index}] must be an object")
            name = value.get("name")
            if not isinstance(name, str) or not name:
                raise PipelineError(f"timeline.actions[{index}].name must be non-empty")
            records.append((name, value))
    elif isinstance(raw_actions, Mapping):
        for name, value in raw_actions.items():
            if not isinstance(value, Mapping):
                raise PipelineError(f"actions.{name} must be an object")
            record = dict(value)
            record.setdefault("name", name)
            records.append((str(name), record))
    else:
        raise PipelineError("timeline.actions must be a list or object")

    result: list[ActionSpec] = []
    seen_names: set[str] = set()
    for name, value in records:
        if name in seen_names:
            raise PipelineError(f"duplicate action name: {name}")
        seen_names.add(name)
        refs = value.get("frames", value.get("frame_ids", value.get("timeline")))
        if refs is None:
            # A compact action can specify a frame range by its frame action
            # label; this remains deterministic and avoids inventing IDs.
            refs = [frame.frame_id for frame in frames if frame.action == name]
        if not isinstance(refs, list) or not refs:
            raise PipelineError(f"action {name!r} must contain a non-empty frames list")
        frame_ids: list[str] = []
        for ref in refs:
            if not isinstance(ref, str) or ref not in by_id:
                raise PipelineError(f"action {name!r} references unknown frame {ref!r}")
            frame_ids.append(ref)
        result.append(
            ActionSpec(
                name=name,
                frame_ids=frame_ids,
                loop=_loop_mode(value.get("loop", value.get("loop_mode")), f"actions.{name}.loop"),
                direction=value.get("direction") if isinstance(value.get("direction"), str) else None,
                allow_boundary_duplicate=bool(
                    value.get("allow_boundary_duplicate", value.get("intentional_boundary_duplicate", False))
                ),
            )
        )
    if not result:
        raise PipelineError("timeline.actions must not be empty")
    return result


def load_timeline(path: str | os.PathLike[str], *, load_images: bool = True) -> tuple[dict[str, Any], list[FrameSpec], list[ActionSpec], tuple[int, int]]:
    """Load and normalize a timeline JSON file.

    The returned frame images are RGBA Pillow images when ``load_images`` is
    true.  This function performs semantic validation but does not reject an
    intentional loop boundary duplicate until action metadata is available.
    """

    _require_pillow()
    timeline_path = Path(path).expanduser().resolve()
    data = _read_json(timeline_path)
    schema = data.get("schema", SCHEMA_TIMELINE)
    if schema != SCHEMA_TIMELINE:
        raise PipelineError(f"unsupported timeline schema {schema!r}; expected {SCHEMA_TIMELINE!r}")

    raw_frames = _frame_records(data.get("frames"))
    canvas = _canvas_from_data(data)
    default_pivot_raw = data.get("default_pivot", data.get("pivot"))
    # A pixel pivot is intentionally explicit in metadata.  The fallback is
    # center-of-canvas and is marked in the generated metadata.
    provisional_pivot = _point(default_pivot_raw, "timeline.default_pivot", default=(0.0, 0.0))

    frames: list[FrameSpec] = []
    seen_ids: set[str] = set()
    per_action_index: dict[str, int] = {}
    loaded: list[tuple[FrameSpec, Any]] = []
    for position, raw in enumerate(raw_frames):
        frame_id = raw.get("id", raw.get("name"))
        if not isinstance(frame_id, str) or not frame_id:
            raise PipelineError(f"timeline.frames[{position}].id must be non-empty")
        if frame_id in seen_ids:
            raise PipelineError(f"duplicate frame id: {frame_id}")
        seen_ids.add(frame_id)
        source_file, source_path = _resolve_source_path(
            timeline_path, raw.get("file", raw.get("path", raw.get("image"))), f"frames[{position}]"
        )
        duration = raw.get("duration_ms", raw.get("duration"))
        duration_ms = _positive_int(duration, f"frames[{position}].duration_ms")
        action = raw.get("action", "default")
        if not isinstance(action, str) or not action:
            raise PipelineError(f"frames[{position}].action must be non-empty")
        index = raw.get("index", per_action_index.get(action, 0))
        index = _positive_int(index, f"frames[{position}].index", allow_zero=True)
        per_action_index[action] = index + 1

        pivot_raw = raw.get("pivot", default_pivot_raw)
        if pivot_raw is None:
            pivot = (0.0, 0.0)
            pivot_defaulted = True
        else:
            pivot = _point(pivot_raw, f"frames[{position}].pivot")
            pivot_defaulted = False
            if isinstance(pivot_raw, Mapping) and pivot_raw.get("normalized") is True:
                # Scale normalized pivots after the logical canvas is known.
                pass
        offset_raw = raw.get("source_offset", raw.get("offset", {"x": 0, "y": 0}))
        offset_point = _point(offset_raw, f"frames[{position}].source_offset", default=(0, 0))
        if int(offset_point[0]) != offset_point[0] or int(offset_point[1]) != offset_point[1]:
            raise PipelineError(f"frames[{position}].source_offset must be integer pixels")
        offset = (int(offset_point[0]), int(offset_point[1]))
        if offset[0] < 0 or offset[1] < 0:
            raise PipelineError(f"frames[{position}].source_offset must be non-negative")

        if not source_path.exists():
            raise PipelineError(f"frame image does not exist: {source_path}")
        try:
            image = Image.open(source_path).convert("RGBA")
            image.load()
        except Exception as exc:  # Pillow exposes several image-specific errors.
            raise PipelineError(f"cannot read frame image {source_path}: {exc}") from exc
        width, height = image.size
        if canvas is None:
            canvas = (max(canvas[0] if canvas else 0, offset[0] + width), max(canvas[1] if canvas else 0, offset[1] + height))
        if offset[0] + width > canvas[0] or offset[1] + height > canvas[1]:
            raise PipelineError(
                f"frame {frame_id!r} ({width}x{height} at offset {offset}) exceeds logical canvas {canvas[0]}x{canvas[1]}"
            )
        if pivot_raw is None:
            pivot = (canvas[0] / 2.0, canvas[1] / 2.0)
        elif isinstance(pivot_raw, Mapping) and pivot_raw.get("normalized") is True:
            pivot = (pivot[0] * canvas[0], pivot[1] * canvas[1])
        frame = FrameSpec(
            frame_id=frame_id,
            source_file=source_file,
            source_path=source_path,
            duration_ms=duration_ms,
            action=action,
            direction=raw.get("direction") if isinstance(raw.get("direction"), str) else None,
            index=index,
            pivot=pivot,
            source_offset=offset,
            image=image if load_images else None,
            source_hash=hashlib.sha256(image.tobytes()).hexdigest(),
            source_size=(width, height),
            source_mode="RGBA",
        )
        frame._pivot_defaulted = pivot_defaulted  # type: ignore[attr-defined]
        frames.append(frame)
        loaded.append((frame, image))

    assert canvas is not None
    actions = _normalized_actions(data, frames)
    # Keep the images attached even when the caller asked for metadata-only
    # normalization; validation callers still need dimensions and hashes.
    if not load_images:
        for frame, _image in loaded:
            frame.image = None
    return data, frames, actions, canvas


def _action_duplicate_report(frames_by_id: Mapping[str, FrameSpec], actions: Iterable[ActionSpec]) -> list[str]:
    duplicates: list[str] = []
    for action in actions:
        if action.loop not in {"loop", "pingpong"} or len(action.frame_ids) < 2:
            continue
        first = frames_by_id[action.frame_ids[0]]
        last = frames_by_id[action.frame_ids[-1]]
        if first.source_hash and first.source_hash == last.source_hash and not action.allow_boundary_duplicate:
            duplicates.append(
                f"action {action.name!r} repeats identical source pixels at loop boundary "
                f"({first.frame_id!r} and {last.frame_id!r}); set allow_boundary_duplicate=true if intentional"
            )
    return duplicates


def validate_timeline(
    path: str | os.PathLike[str],
    *,
    expected_frames: int | None = None,
    expected_actions: Mapping[str, int] | None = None,
) -> ValidationReport:
    """Validate timeline files, frame files, dimensions, durations, and loops."""

    report = ValidationReport("timeline")
    try:
        data, frames, actions, canvas = load_timeline(path)
    except PipelineError as exc:
        report.errors.append(str(exc))
        return report
    frame_map = {frame.frame_id: frame for frame in frames}
    report.checks.update(
        {
            "schema": data.get("schema", SCHEMA_TIMELINE),
            "frame_count": len(frames),
            "action_count": len(actions),
            "canvas": {"width": canvas[0], "height": canvas[1]},
            "durations_positive": all(frame.duration_ms > 0 for frame in frames),
            "source_files_read": True,
            "alpha_dimensions": all(frame.image is not None and frame.image.getchannel("A").size == frame.image.size for frame in frames),
        }
    )
    if expected_frames is not None and len(frames) != expected_frames:
        report.errors.append(f"expected {expected_frames} frames but found {len(frames)}")
    if expected_actions:
        for name, expected in expected_actions.items():
            matches = [action for action in actions if action.name == name]
            if not matches:
                report.errors.append(f"expected action is missing: {name}")
            elif len(matches[0].frame_ids) != expected:
                report.errors.append(
                    f"expected action {name!r} to contain {expected} frames but found {len(matches[0].frame_ids)}"
                )
    report.errors.extend(_action_duplicate_report(frame_map, actions))
    for frame in frames:
        if getattr(frame, "_pivot_defaulted", False):
            report.warnings.append(f"frame {frame.frame_id!r} uses the default center pivot")
        if frame.image is not None and frame.image.getchannel("A").getbbox() is None:
            report.errors.append(f"frame {frame.frame_id!r} is fully transparent")
    report.checks["loop_boundary_duplicates_intentional"] = not any(
        "loop boundary" in error for error in report.errors
    )
    return report


def _alpha_bbox(image: Any, frame_id: str) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise PipelineError(f"frame {frame_id!r} is fully transparent and cannot be packed")
    return bbox


def _extrude(image: Any, amount: int) -> Any:
    if amount == 0:
        return image.copy()
    width, height = image.size
    output = Image.new("RGBA", (width + amount * 2, height + amount * 2), (0, 0, 0, 0))
    output.paste(image, (amount, amount))
    # Repeating edge pixels prevents bilinear filtering from sampling a
    # neighboring sprite.  This is intentionally pixel duplication, not
    # alpha dilation or a claim that every engine uses the same sampler.
    nearest = getattr(getattr(Image, "Resampling", Image), "NEAREST", 0)
    output.paste(image.crop((0, 0, width, 1)).resize((width, amount), resample=nearest), (amount, 0))
    output.paste(image.crop((0, height - 1, width, height)).resize((width, amount), resample=nearest), (amount, amount + height))
    output.paste(image.crop((0, 0, 1, height)).resize((amount, height), resample=nearest), (0, amount))
    output.paste(image.crop((width - 1, 0, width, height)).resize((amount, height), resample=nearest), (amount + width, amount))
    output.paste(image.crop((0, 0, 1, 1)).resize((amount, amount), resample=nearest), (0, 0))
    output.paste(image.crop((width - 1, 0, width, 1)).resize((amount, amount), resample=nearest), (amount + width, 0))
    output.paste(image.crop((0, height - 1, 1, height)).resize((amount, amount), resample=nearest), (0, amount + height))
    output.paste(image.crop((width - 1, height - 1, width, height)).resize((amount, amount), resample=nearest), (amount + width, amount + height))
    return output


def _shelf_positions(sizes: Sequence[tuple[int, int]], padding: int, max_width: int) -> tuple[list[tuple[int, int]], tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    x = padding
    y = padding
    row_height = 0
    atlas_width = padding
    for width, height in sizes:
        if width + 2 * padding > max_width:
            raise PipelineError(
                f"sprite rectangle {width}x{height} cannot fit max atlas width {max_width} with padding {padding}"
            )
        if x != padding and x + width + padding > max_width:
            x = padding
            y += row_height + padding
            row_height = 0
        if x + width + padding > max_width:
            raise PipelineError(f"atlas width {max_width} is too small for sprite rectangle {width}x{height}")
        positions.append((x, y))
        x += width + padding
        row_height = max(row_height, height)
        atlas_width = max(atlas_width, x)
    atlas_height = y + row_height + padding
    return positions, (max(1, atlas_width), max(1, atlas_height))


def _rect(x: int, y: int, width: int, height: int) -> dict[str, int]:
    return {"x": int(x), "y": int(y), "w": int(width), "h": int(height)}


def _rect_from_mapping(value: Any, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, Mapping):
        raise PipelineError(f"{label} must be an object")
    return (
        _positive_int(value.get("x"), f"{label}.x", allow_zero=True),
        _positive_int(value.get("y"), f"{label}.y", allow_zero=True),
        _positive_int(value.get("w", value.get("width")), f"{label}.w"),
        _positive_int(value.get("h", value.get("height")), f"{label}.h"),
    )


def pack_atlas(
    timeline_path: str | os.PathLike[str],
    atlas_path: str | os.PathLike[str],
    metadata_path: str | os.PathLike[str] | None = None,
    *,
    padding: int = 2,
    extrude: int = 1,
    trim: bool = False,
    max_width: int = 2048,
    source_route: str = "programmatic_png_sequence",
    aseprite_source: str | None = None,
) -> dict[str, Any]:
    """Pack a timeline into an atlas and return the generated metadata."""

    _require_pillow()
    padding = _positive_int(padding, "padding", allow_zero=True)
    extrude = _positive_int(extrude, "extrude", allow_zero=True)
    max_width = _positive_int(max_width, "max_width")
    data, frames, actions, canvas = load_timeline(timeline_path)
    frame_map = {frame.frame_id: frame for frame in frames}
    duplicates = _action_duplicate_report(frame_map, actions)
    if duplicates:
        raise PipelineError("; ".join(duplicates))

    atlas_file = Path(atlas_path).expanduser()
    metadata_file = Path(metadata_path).expanduser() if metadata_path else atlas_file.with_suffix(".json")
    atlas_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)

    content_images: list[Any] = []
    records: list[dict[str, Any]] = []
    for frame in frames:
        assert frame.image is not None
        image = frame.image
        bbox = _alpha_bbox(image, frame.frame_id) if trim else (0, 0, image.width, image.height)
        content = image.crop(bbox)
        source_offset = (frame.source_offset[0] + bbox[0], frame.source_offset[1] + bbox[1])
        extruded = _extrude(content, extrude)
        content_images.append(extruded)
        records.append(
            {
                "frame": frame,
                "content": content,
                "extruded": extruded,
                "bbox": bbox,
                "source_offset": source_offset,
            }
        )

    positions, atlas_size = _shelf_positions(
        [(image.width, image.height) for image in content_images], padding, max_width
    )
    atlas = Image.new("RGBA", atlas_size, (0, 0, 0, 0))
    output_frames: list[dict[str, Any]] = []
    for record, (x, y) in zip(records, positions):
        frame = record["frame"]
        content = record["content"]
        extruded = record["extruded"]
        atlas.paste(extruded, (x, y))
        content_x = x + extrude
        content_y = y + extrude
        source_offset = record["source_offset"]
        px, py = frame.pivot
        frame_record = {
            "id": frame.frame_id,
            "source_file": frame.source_file,
            "source_hash": frame.source_hash,
            "action": frame.action,
            "direction": frame.direction,
            "index": frame.index,
            "duration_ms": frame.duration_ms,
            "frame": _rect(content_x, content_y, content.width, content.height),
            "packed_frame": _rect(x, y, extruded.width, extruded.height),
            "sprite_source_size": _rect(source_offset[0], source_offset[1], content.width, content.height),
            "source_size": {"w": canvas[0], "h": canvas[1]},
            "offset": {"x": source_offset[0], "y": source_offset[1]},
            "pivot": {
                "x": px,
                "y": py,
                "normalized_x": px / canvas[0],
                "normalized_y": py / canvas[1],
            },
            "trimmed": bool(trim),
        }
        output_frames.append(frame_record)

    output_actions: list[dict[str, Any]] = []
    for action in actions:
        output_actions.append(
            {
                "name": action.name,
                "frame_ids": list(action.frame_ids),
                "frame_count": len(action.frame_ids),
                "loop": action.loop,
                "direction": action.direction,
                "allow_boundary_duplicate": action.allow_boundary_duplicate,
                "total_duration_ms": sum(frame_map[frame_id].duration_ms for frame_id in action.frame_ids),
            }
        )

    source_meta = data.get("source") if isinstance(data.get("source"), Mapping) else {}
    source_meta = dict(source_meta)
    source_meta.setdefault("route", source_route)
    source_meta.setdefault("editable_source", "timeline_json_plus_png_sequence")
    source_meta["native_aseprite"] = {
        "provided": bool(aseprite_source),
        "path": aseprite_source,
        "status": "PRESENT_NOT_USED" if aseprite_source and Path(aseprite_source).exists() else ("NOT_PROVIDED" if not aseprite_source else "MISSING"),
    }
    try:
        atlas_reference = Path(os.path.relpath(atlas_file.resolve(), metadata_file.parent.resolve())).as_posix()
    except ValueError:
        # Windows drives can be unrelated. Keep the explicit absolute path;
        # the validator still reports runtime portability separately.
        atlas_reference = str(atlas_file.resolve())
    metadata: dict[str, Any] = {
        "schema": SCHEMA_ATLAS,
        "generator": "sprite_pipeline.py",
        "source": source_meta,
        "timeline": {"file": Path(timeline_path).name, "schema": data.get("schema", SCHEMA_TIMELINE)},
        "canvas": {"width": canvas[0], "height": canvas[1], "coordinate_origin": "top_left"},
        "atlas": {
            "file": atlas_reference,
            "width": atlas_size[0],
            "height": atlas_size[1],
            "mode": "RGBA",
            "padding": padding,
            "extrude": extrude,
            "trim": trim,
            "max_width": max_width,
        },
        "frames": output_frames,
        "actions": output_actions,
        "runtime_playback": "NOT_TESTED",
        "preview_claim": "Atlas metadata and static packing checks only; native target playback is not implied.",
    }
    atlas.save(atlas_file, format="PNG", optimize=False)
    with metadata_file.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    metadata["atlas"]["file"] = atlas_reference
    metadata["metadata_file"] = str(metadata_file)
    metadata["atlas_file"] = str(atlas_file)
    return metadata


def _inside(rect: tuple[int, int, int, int], width: int, height: int) -> bool:
    x, y, w, h = rect
    return x >= 0 and y >= 0 and x + w <= width and y + h <= height


def _rects_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _axis_gap(a_start: int, a_size: int, b_start: int, b_size: int) -> int:
    return max(b_start - (a_start + a_size), a_start - (b_start + b_size), 0)


def validate_atlas(
    path: str | os.PathLike[str],
    *,
    expected_frames: int | None = None,
    expected_actions: Mapping[str, int] | None = None,
) -> ValidationReport:
    """Validate atlas JSON, atlas dimensions, rects, actions, and metadata."""

    report = ValidationReport("atlas")
    metadata_path = Path(path).expanduser().resolve()
    try:
        data = _read_json(metadata_path)
    except PipelineError as exc:
        report.errors.append(str(exc))
        return report
    if data.get("schema") != SCHEMA_ATLAS:
        report.errors.append(f"unsupported atlas schema: {data.get('schema')!r}")
        return report
    atlas_info = data.get("atlas")
    if not isinstance(atlas_info, Mapping):
        report.errors.append("atlas metadata is missing atlas object")
        return report
    try:
        atlas_width = _positive_int(atlas_info.get("width"), "atlas.width")
        atlas_height = _positive_int(atlas_info.get("height"), "atlas.height")
        padding = _positive_int(atlas_info.get("padding"), "atlas.padding", allow_zero=True)
        extrude = _positive_int(atlas_info.get("extrude"), "atlas.extrude", allow_zero=True)
    except PipelineError as exc:
        report.errors.append(str(exc))
        return report
    atlas_file_raw = atlas_info.get("file")
    if not isinstance(atlas_file_raw, str):
        report.errors.append("atlas.file must be a relative filename")
        return report
    atlas_file = Path(atlas_file_raw)
    if not atlas_file.is_absolute():
        atlas_file = metadata_path.parent / atlas_file
    if not atlas_file.exists():
        report.errors.append(f"atlas PNG does not exist: {atlas_file}")
        return report
    _require_pillow()
    try:
        with Image.open(atlas_file) as raw_image:
            has_alpha = "A" in raw_image.getbands() or "transparency" in raw_image.info
            raw_mode = raw_image.mode
            image = raw_image.convert("RGBA")
            image.load()
    except Exception as exc:
        report.errors.append(f"cannot read atlas PNG {atlas_file}: {exc}")
        return report
    if not has_alpha:
        report.errors.append(f"atlas PNG has no alpha channel: mode={raw_mode}")
    if image.size != (atlas_width, atlas_height):
        report.errors.append(
            f"atlas dimensions mismatch metadata: image={image.width}x{image.height}, metadata={atlas_width}x{atlas_height}"
        )
    frames = data.get("frames")
    if not isinstance(frames, list) or not frames:
        report.errors.append("atlas.frames must be a non-empty list")
        return report
    canvas_info = data.get("canvas")
    try:
        canvas_width, canvas_height = _size(canvas_info, "canvas")
    except PipelineError as exc:
        report.errors.append(str(exc))
        return report
    ids: set[str] = set()
    packed_rects: list[tuple[str, tuple[int, int, int, int]]] = []
    frame_map: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(frames):
        if not isinstance(record, Mapping):
            report.errors.append(f"atlas.frames[{index}] must be an object")
            continue
        frame_id = record.get("id")
        if not isinstance(frame_id, str) or not frame_id:
            report.errors.append(f"atlas.frames[{index}].id must be non-empty")
            continue
        if frame_id in ids:
            report.errors.append(f"duplicate atlas frame id: {frame_id}")
        ids.add(frame_id)
        frame_map[frame_id] = dict(record)
        try:
            frame_rect = _rect_from_mapping(record.get("frame"), f"frames[{index}].frame")
            packed_rect = _rect_from_mapping(record.get("packed_frame"), f"frames[{index}].packed_frame")
            source_rect = _rect_from_mapping(record.get("sprite_source_size"), f"frames[{index}].sprite_source_size")
            source_size = _size(record.get("source_size"), f"frames[{index}].source_size")
            duration = _positive_int(record.get("duration_ms"), f"frames[{index}].duration_ms")
            pivot = record.get("pivot")
            _point(pivot, f"frames[{index}].pivot")
        except PipelineError as exc:
            report.errors.append(str(exc))
            continue
        if not _inside(frame_rect, atlas_width, atlas_height):
            report.errors.append(f"frame {frame_id!r} is outside atlas bounds")
        if not _inside(packed_rect, atlas_width, atlas_height):
            report.errors.append(f"packed frame {frame_id!r} is outside atlas bounds")
        if source_size != (canvas_width, canvas_height):
            report.errors.append(f"frame {frame_id!r} source_size does not match logical canvas")
        if not _inside(source_rect, canvas_width, canvas_height):
            report.errors.append(f"frame {frame_id!r} sprite_source_size is outside logical canvas")
        if packed_rect[2] != frame_rect[2] + 2 * extrude or packed_rect[3] != frame_rect[3] + 2 * extrude:
            report.errors.append(f"frame {frame_id!r} packed_frame does not match extrude metadata")
        if packed_rect[0] + extrude != frame_rect[0] or packed_rect[1] + extrude != frame_rect[1]:
            report.errors.append(f"frame {frame_id!r} frame is not centered inside packed_frame according to extrude metadata")
        offset = record.get("offset")
        if isinstance(offset, Mapping) and (offset.get("x"), offset.get("y")) != (source_rect[0], source_rect[1]):
            report.errors.append(f"frame {frame_id!r} offset does not match sprite_source_size")
        packed_rects.append((frame_id, packed_rect))
    for index, (id_a, rect_a) in enumerate(packed_rects):
        for id_b, rect_b in packed_rects[index + 1 :]:
            if _rects_overlap(rect_a, rect_b):
                report.errors.append(f"packed frame rectangles overlap: {id_a!r} and {id_b!r}")
            elif _axis_gap(rect_a[0], rect_a[2], rect_b[0], rect_b[2]) < padding and _axis_gap(
                rect_a[1], rect_a[3], rect_b[1], rect_b[3]
            ) < padding:
                report.errors.append(
                    f"packed frame rectangles do not preserve requested padding {padding}: {id_a!r} and {id_b!r}"
                )

    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        report.errors.append("atlas.actions must be a non-empty list")
        actions = []
    action_names: set[str] = set()
    for index, action in enumerate(actions):
        if not isinstance(action, Mapping):
            report.errors.append(f"atlas.actions[{index}] must be an object")
            continue
        name = action.get("name")
        refs = action.get("frame_ids")
        if not isinstance(name, str) or not name:
            report.errors.append(f"atlas.actions[{index}].name must be non-empty")
        elif name in action_names:
            report.errors.append(f"duplicate atlas action name: {name}")
        else:
            action_names.add(name)
        if not isinstance(refs, list) or not refs:
            report.errors.append(f"atlas.actions[{index}].frame_ids must be non-empty")
            continue
        for ref in refs:
            if ref not in frame_map:
                report.errors.append(f"action {name!r} references missing frame {ref!r}")
        try:
            loop = _loop_mode(action.get("loop"), f"atlas.actions[{index}].loop")
        except PipelineError as exc:
            report.errors.append(str(exc))
            loop = "loop"
        if name and expected_actions and name in expected_actions and len(refs) != expected_actions[name]:
            report.errors.append(f"expected action {name!r} to contain {expected_actions[name]} frames but found {len(refs)}")
        if loop in {"loop", "pingpong"} and len(refs) > 1:
            first = frame_map.get(refs[0])
            last = frame_map.get(refs[-1])
            if first and last and first.get("source_hash") == last.get("source_hash") and not bool(action.get("allow_boundary_duplicate")):
                report.errors.append(
                    f"action {name!r} repeats identical source pixels at loop boundary; set allow_boundary_duplicate=true if intentional"
                )
    if expected_frames is not None and len(frames) != expected_frames:
        report.errors.append(f"expected {expected_frames} frames but found {len(frames)}")
    report.checks.update(
        {
            "schema": data.get("schema"),
            "frame_count": len(frames),
            "action_count": len(actions),
            "atlas_dimensions": {"width": atlas_width, "height": atlas_height},
            "alpha_dimensions": image.getchannel("A").size == image.size,
            "padding_non_negative": padding >= 0,
            "extrude_non_negative": extrude >= 0,
            "rects_in_bounds": not any("outside atlas bounds" in error for error in report.errors),
            "rects_non_overlapping": not any("rectangles overlap" in error for error in report.errors),
            "runtime_playback": "NOT_TESTED",
        }
    )
    return report


def _load_playback_frames(
    timeline_path: str | os.PathLike[str], action_name: str | None = None
) -> tuple[list[Any], list[int], dict[str, Any]]:
    data, frames, actions, canvas = load_timeline(timeline_path)
    frame_map = {frame.frame_id: frame for frame in frames}
    if action_name:
        action = next((item for item in actions if item.name == action_name), None)
        if action is None:
            raise PipelineError(f"unknown action {action_name!r}; available actions: {[item.name for item in actions]}")
    else:
        action = actions[0]
    ids = list(action.frame_ids)
    if action.loop == "reverse":
        ids.reverse()
    elif action.loop == "pingpong" and len(ids) > 2:
        ids.extend(reversed(ids[1:-1]))
    output_images: list[Any] = []
    durations: list[int] = []
    for frame_id in ids:
        frame = frame_map[frame_id]
        assert frame.image is not None
        image = Image.new("RGBA", canvas, (0, 0, 0, 0))
        image.paste(frame.image, frame.source_offset)
        output_images.append(image)
        durations.append(frame.duration_ms)
    return output_images, durations, {"action": action.name, "loop": action.loop, "frame_ids": ids, "canvas": canvas}


def _write_gif_preview(
    images: Sequence[Any], durations: Sequence[int], output: Path, *, kind: str, source: str, action: str, slow_factor: float = 1.0
) -> dict[str, Any]:
    if not images:
        raise PipelineError("cannot write an empty preview")
    output.parent.mkdir(parents=True, exist_ok=True)
    scaled = [max(1, int(round(duration * slow_factor))) for duration in durations]
    # GIF is deliberately a preview format: palette conversion and its
    # limited transparency model are recorded in the sidecar receipt.
    palette_images = [image.convert("P", palette=Image.Palette.ADAPTIVE, colors=255, dither=Image.Dither.NONE) for image in images]
    save_kwargs: dict[str, Any] = {
        "save_all": True,
        "append_images": palette_images[1:],
        "duration": scaled,
        "loop": 0,
        "disposal": 2,
        "optimize": False,
    }
    palette_images[0].save(output, format="GIF", **save_kwargs)
    sidecar = output.with_suffix(output.suffix + ".json")
    partial_alpha = any(image.getchannel("A").getextrema()[0] != image.getchannel("A").getextrema()[1] for image in images)
    receipt = {
        "schema": "blender-engineering.sprite-preview.v1",
        "preview_file": output.name,
        "preview_kind": kind,
        "source_timeline": source,
        "action": action,
        "frame_count": len(images),
        "durations_ms": scaled,
        "source_durations_ms": list(durations),
        "slow_factor": slow_factor,
        "format": "GIF",
        "gif_palette_limited": True,
        "partial_alpha_warning": partial_alpha,
        "claim": "Timing and appearance preview only; this does not prove native target playback or editable-source fidelity.",
        "target_playback": "NOT_TESTED",
    }
    with sidecar.open("w", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    receipt["sidecar"] = str(sidecar)
    return receipt


def make_preview(
    timeline_path: str | os.PathLike[str],
    output: str | os.PathLike[str],
    *,
    action: str | None = None,
    slow_output: str | os.PathLike[str] | None = None,
    slow_factor: float = 2.0,
) -> dict[str, Any]:
    """Write full-speed and optional slowed GIF previews with sidecars."""

    _require_pillow()
    if slow_factor < 1.0 or slow_factor != slow_factor:
        raise PipelineError("slow_factor must be finite and at least 1")
    images, durations, playback = _load_playback_frames(timeline_path, action)
    result = {
        "fullspeed": _write_gif_preview(
            images,
            durations,
            Path(output).expanduser(),
            kind="fullspeed",
            source=Path(timeline_path).name,
            action=playback["action"],
            slow_factor=1.0,
        )
    }
    if slow_output:
        result["slow"] = _write_gif_preview(
            images,
            durations,
            Path(slow_output).expanduser(),
            kind="slow",
            source=Path(timeline_path).name,
            action=playback["action"],
            slow_factor=slow_factor,
        )
    return result


def _find_executable(names: Sequence[str], extra_candidates: Sequence[str] = ()) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    for candidate in extra_candidates:
        if Path(candidate).exists() and os.access(candidate, os.X_OK):
            return candidate
    return None


def probe_tools() -> dict[str, Any]:
    """Report optional tools without installing or invoking them."""

    aseprite = _find_executable(
        ["aseprite"],
        ["/Applications/Aseprite.app/Contents/MacOS/aseprite", "/usr/local/bin/aseprite"],
    )
    libresprite = _find_executable(["libresprite"], ["/Applications/LibreSprite.app/Contents/MacOS/libresprite"])
    rive_cli = _find_executable(["rive"])
    ffmpeg = _find_executable(["ffmpeg"])
    return {
        "pillow": {
            "available": PILLOW_AVAILABLE,
            "version": PILLOW_VERSION,
            "role": "programmatic PNG/atlas/GIF helper",
            "dependency": "Pillow (optional)",
            "install_hint": "python3 -m venv .venv && .venv/bin/python -m pip install Pillow",
        },
        "aseprite": {
            "available": bool(aseprite),
            "path": aseprite,
            "route": "native editable source plus CLI export when explicitly selected",
            "parity": "not_assumed_for_libresprite",
        },
        "libresprite": {
            "available": bool(libresprite),
            "path": libresprite,
            "cli_parity": "NOT_ASSUMED",
        },
        "rive_cli": {
            "available": bool(rive_cli),
            "path": rive_cli,
            "route": "RML source build/verify when explicitly selected",
            "signed_export": "NOT_TESTED",
        },
        "ffmpeg": {
            "available": bool(ffmpeg),
            "path": ffmpeg,
            "role": "optional video preview backend; not invoked by this helper",
        },
    }


def inspect_rive(
    *,
    rml: str | None = None,
    riv: str | None = None,
    rev: str | None = None,
    target_runtime: str | None = None,
) -> dict[str, Any]:
    """Check Rive source/runtime/backup paths without claiming playback."""

    def path_status(value: str | None, kind: str) -> dict[str, Any]:
        if not value:
            return {"kind": kind, "status": "NOT_PROVIDED", "path": None}
        path = Path(value).expanduser()
        return {
            "kind": kind,
            "status": "PRESENT" if path.exists() else "MISSING",
            "path": str(path),
            "is_file": path.is_file(),
            "is_directory": path.is_dir(),
        }

    return {
        "schema": "blender-engineering.rive-delivery-check.v1",
        "editable_source": path_status(rml, "RML_project_source"),
        "runtime": path_status(riv, ".riv_runtime_export"),
        "backup": path_status(rev, ".rev_backup_export"),
        "cli": probe_tools().get("rive_cli", {"status": "NOT_PROBED"}),
        "target_runtime": target_runtime,
        "runtime_license_note": "Rive documents MIT open-source runtimes; feature support varies by runtime.",
        "signed_export": "NOT_TESTED",
        "target_playback": "NOT_TESTED",
        "claim": "A present .riv or .rev path is not proof of signed export, runtime compatibility, or editable round-trip fidelity.",
    }


def inspect_lottie(path: str | os.PathLike[str], *, target_runtime: str | None = None) -> dict[str, Any]:
    """Inspect only the JSON envelope; feature-subset playback remains untested."""

    json_path = Path(path).expanduser()
    data = _read_json(json_path)
    required = {"v", "fr", "ip", "op", "layers"}
    missing = sorted(required - set(data))
    return {
        "schema": "blender-engineering.lottie-check.v1",
        "file": str(json_path),
        "json_envelope": "PASS" if not missing else "FAIL",
        "missing_fields": missing,
        "version": data.get("v"),
        "frame_rate": data.get("fr"),
        "in_point": data.get("ip"),
        "out_point": data.get("op"),
        "layer_count": len(data.get("layers", [])) if isinstance(data.get("layers"), list) else None,
        "target_runtime": target_runtime,
        "feature_subset": "NOT_TESTED",
        "target_playback": "NOT_TESTED",
        "claim": "Envelope inspection does not prove that expressions, effects, masks, assets, or stateful playback are supported by the chosen player.",
    }


def inspect_spine(
    *,
    source: str | None = None,
    runtime: str | None = None,
    atlas: str | None = None,
    version: str | None = None,
    target_runtime: str | None = None,
) -> dict[str, Any]:
    """Check Spine source/runtime/atlas paths without claiming version matching."""

    def status(value: str | None, kind: str) -> dict[str, Any]:
        if not value:
            return {"kind": kind, "status": "NOT_PROVIDED", "path": None}
        path = Path(value).expanduser()
        return {"kind": kind, "status": "PRESENT" if path.exists() else "MISSING", "path": str(path)}

    observed_runtime_version: str | None = None
    if runtime:
        runtime_path = Path(runtime).expanduser()
        if runtime_path.suffix.lower() == ".json" and runtime_path.exists():
            try:
                runtime_data = _read_json(runtime_path)
                skeleton = runtime_data.get("skeleton")
                if isinstance(skeleton, Mapping):
                    value = skeleton.get("spine", skeleton.get("version"))
                    if isinstance(value, str):
                        observed_runtime_version = value
            except PipelineError:
                observed_runtime_version = None
    if version and observed_runtime_version:
        version_relation = "MATCH" if version == observed_runtime_version else "MISMATCH"
    else:
        version_relation = "NOT_TESTED"

    return {
        "schema": "blender-engineering.spine-delivery-check.v1",
        "source": status(source, "Spine_project_or_source"),
        "runtime_data": status(runtime, "JSON_or_binary_runtime_data"),
        "atlas": status(atlas, "atlas_and_texture_pages"),
        "declared_version": version,
        "observed_runtime_version": observed_runtime_version,
        "atlas_version": "NOT_DECLARED_BY_ATLAS_TEXT",
        "target_runtime": target_runtime,
        "editor_runtime_version_match": version_relation,
        "atlas_version_match": "NOT_TESTED",
        "target_playback": "NOT_TESTED",
        "claim": "Presence of source, runtime data, and atlas does not prove version pairing or target playback.",
    }


def _expected_actions(values: Sequence[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        if "=" not in value:
            raise PipelineError("--expected-action must use NAME=COUNT")
        name, count = value.split("=", 1)
        if not name:
            raise PipelineError("--expected-action name must not be empty")
        result[name] = _positive_int(int(count), f"expected action {name}", allow_zero=True)
    return result


def _print_json(value: Any) -> None:
    json.dump(value, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite_pipeline.py",
        description=(
            "Pack an explicit timeline JSON plus PNG frames into a deterministic RGBA atlas, "
            "preserving durations, actions, full-canvas offsets, pivots, trim metadata, and preview receipts. "
            "Pillow is optional. If it is missing, install it in an active isolated "
            "environment, for example: python3 -m venv .venv && .venv/bin/python -m pip install Pillow."
        ),
    )
    parser.add_argument("--version", action="version", version="sprite_pipeline.py 1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack = subparsers.add_parser("pack", help="pack a timeline JSON and PNG frames into atlas PNG + metadata JSON")
    pack.add_argument("timeline", type=Path)
    pack.add_argument("--atlas", type=Path, required=True, help="output atlas PNG")
    pack.add_argument("--metadata", type=Path, help="output metadata JSON (default: atlas path with .json)")
    pack.add_argument("--padding", type=int, default=2, help="non-negative pixels between packed rectangles (default: 2)")
    pack.add_argument("--extrude", type=int, default=1, help="non-negative duplicated edge pixels (default: 1)")
    pack.add_argument("--max-width", type=int, default=2048, help="maximum atlas width (default: 2048)")
    pack.add_argument("--trim", action="store_true", help="trim transparent borders while preserving source offsets")
    pack.add_argument("--preview", type=Path, help="also write a full-speed GIF preview")
    pack.add_argument("--slow-preview", type=Path, help="also write a slowed GIF preview")
    pack.add_argument("--slow-factor", type=float, default=2.0, help="slow preview multiplier (default: 2)")
    pack.add_argument("--action", help="action to use when writing previews")
    pack.add_argument("--aseprite-source", type=str, help="optional editable .aseprite source path to record, never silently converted")

    validate = subparsers.add_parser("validate", help="validate timeline JSON or atlas metadata JSON")
    validate.add_argument("input", type=Path)
    validate.add_argument("--expected-frames", type=int)
    validate.add_argument("--expected-action", action="append", default=[], metavar="NAME=COUNT")

    preview = subparsers.add_parser("preview", help="write full-speed and optional slowed GIF previews")
    preview.add_argument("timeline", type=Path)
    preview.add_argument("--output", type=Path, required=True)
    preview.add_argument("--slow-output", type=Path)
    preview.add_argument("--slow-factor", type=float, default=2.0)
    preview.add_argument("--action")

    subparsers.add_parser("probe", help="report optional Pillow/Aseprite/LibreSprite/FFmpeg availability")

    rive = subparsers.add_parser("check-rive", help="check RML source, .riv runtime, and .rev backup paths")
    rive.add_argument("--rml")
    rive.add_argument("--riv")
    rive.add_argument("--rev")
    rive.add_argument("--target-runtime")

    lottie = subparsers.add_parser("check-lottie", help="inspect Lottie JSON envelope without claiming target playback")
    lottie.add_argument("file", type=Path)
    lottie.add_argument("--target-runtime")

    spine = subparsers.add_parser("check-spine", help="check Spine source/runtime/atlas paths without claiming version match")
    spine.add_argument("--source")
    spine.add_argument("--runtime")
    spine.add_argument("--atlas")
    spine.add_argument("--version")
    spine.add_argument("--target-runtime")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            metadata = pack_atlas(
                args.timeline,
                args.atlas,
                args.metadata,
                padding=args.padding,
                extrude=args.extrude,
                trim=args.trim,
                max_width=args.max_width,
                aseprite_source=args.aseprite_source,
            )
            if args.preview or args.slow_preview:
                preview_output = args.preview or args.atlas.with_name(args.atlas.stem + "_preview.gif")
                metadata["preview"] = make_preview(
                    args.timeline,
                    preview_output,
                    action=args.action,
                    slow_output=args.slow_preview,
                    slow_factor=args.slow_factor,
                )
            _print_json(metadata)
            return 0
        if args.command == "validate":
            expected_actions = _expected_actions(args.expected_action)
            data = _read_json(args.input)
            if data.get("schema") == SCHEMA_ATLAS:
                report = validate_atlas(args.input, expected_frames=args.expected_frames, expected_actions=expected_actions)
            else:
                report = validate_timeline(args.input, expected_frames=args.expected_frames, expected_actions=expected_actions)
            _print_json(report.as_dict())
            return 0 if report.ok else 1
        if args.command == "preview":
            _print_json(
                make_preview(
                    args.timeline,
                    args.output,
                    action=args.action,
                    slow_output=args.slow_output,
                    slow_factor=args.slow_factor,
                )
            )
            return 0
        if args.command == "probe":
            _print_json(probe_tools())
            return 0
        if args.command == "check-rive":
            _print_json(inspect_rive(rml=args.rml, riv=args.riv, rev=args.rev, target_runtime=args.target_runtime))
            return 0
        if args.command == "check-lottie":
            _print_json(inspect_lottie(args.file, target_runtime=args.target_runtime))
            return 0
        if args.command == "check-spine":
            _print_json(
                inspect_spine(
                    source=args.source,
                    runtime=args.runtime,
                    atlas=args.atlas,
                    version=args.version,
                    target_runtime=args.target_runtime,
                )
            )
            return 0
    except PipelineError as exc:
        print(f"sprite_pipeline.py: error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"sprite_pipeline.py: filesystem error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
