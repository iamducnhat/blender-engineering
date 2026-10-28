#!/usr/bin/env python3
"""stdlib unittest coverage for the portable sprite pipeline.

Fixtures are generated as tiny PNGs in a temporary directory. No asset or
dataset is downloaded.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_pipeline as pipeline  # noqa: E402


class SpritePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.frames_dir = self.root / "frames"
        self.frames_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_frame(self, name: str, pixels: list[tuple[int, int, tuple[int, int, int, int]]]) -> Path:
        image = Image.new("RGBA", (6, 6), (0, 0, 0, 0))
        for x, y, color in pixels:
            image.putpixel((x, y), color)
        path = self.frames_dir / name
        image.save(path)
        return path

    def _write_timeline(self, *, duplicate_boundary: bool = False) -> Path:
        first = self._write_frame("idle_000.png", [(1, 2, (255, 0, 0, 255))])
        second = self._write_frame("idle_001.png", [(2, 2, (0, 0, 255, 255))])
        frame_records = [
            {
                "id": "idle_000",
                "file": str(first.relative_to(self.root)),
                "duration_ms": 100,
                "action": "idle",
                "direction": "south",
                "index": 0,
                "pivot": {"x": 3, "y": 5},
            },
            {
                "id": "idle_001",
                "file": str(second.relative_to(self.root)),
                "duration_ms": 200,
                "action": "idle",
                "direction": "south",
                "index": 1,
                "pivot": {"x": 3, "y": 5},
            },
        ]
        if duplicate_boundary:
            third = self._write_frame("idle_002.png", [(1, 2, (255, 0, 0, 255))])
            frame_records.append(
                {
                    "id": "idle_002",
                    "file": str(third.relative_to(self.root)),
                    "duration_ms": 100,
                    "action": "idle",
                    "direction": "south",
                    "index": 2,
                    "pivot": {"x": 3, "y": 5},
                }
            )
        data = {
            "schema": pipeline.SCHEMA_TIMELINE,
            "canvas": {"width": 6, "height": 6},
            "frames": frame_records,
            "actions": {
                "idle_south": {
                    "frames": [frame["id"] for frame in frame_records],
                    "loop": "loop",
                    **({"allow_boundary_duplicate": True} if duplicate_boundary else {}),
                }
            },
        }
        path = self.root / "timeline.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def test_pack_preserves_trim_offset_pivot_duration_and_actions(self) -> None:
        timeline = self._write_timeline()
        atlas_path = self.root / "build" / "hero_atlas.png"
        metadata_path = self.root / "build" / "hero_atlas.json"
        metadata = pipeline.pack_atlas(
            timeline,
            atlas_path,
            metadata_path,
            padding=2,
            extrude=1,
            trim=True,
            max_width=32,
        )

        self.assertTrue(atlas_path.exists())
        self.assertTrue(metadata_path.exists())
        self.assertEqual(metadata["canvas"], {"width": 6, "height": 6, "coordinate_origin": "top_left"})
        self.assertEqual([frame["duration_ms"] for frame in metadata["frames"]], [100, 200])
        self.assertEqual(metadata["frames"][0]["sprite_source_size"], {"x": 1, "y": 2, "w": 1, "h": 1})
        self.assertEqual(metadata["frames"][0]["offset"], {"x": 1, "y": 2})
        self.assertEqual(metadata["frames"][0]["pivot"]["x"], 3.0)
        self.assertEqual(metadata["frames"][0]["pivot"]["y"], 5.0)
        self.assertEqual(metadata["actions"][0]["frame_ids"], ["idle_000", "idle_001"])
        self.assertEqual(metadata["atlas"]["padding"], 2)
        self.assertEqual(metadata["atlas"]["extrude"], 1)

        report = pipeline.validate_atlas(metadata_path, expected_frames=2, expected_actions={"idle_south": 2})
        self.assertTrue(report.ok, report.as_dict())
        with Image.open(atlas_path) as atlas_image:
            self.assertEqual(atlas_image.mode, "RGBA")
            self.assertGreater(atlas_image.width, 0)
            self.assertGreater(atlas_image.height, 0)

    def test_loop_boundary_duplicate_requires_explicit_intent(self) -> None:
        timeline = self._write_timeline(duplicate_boundary=True)
        data = json.loads(timeline.read_text(encoding="utf-8"))
        data["actions"]["idle_south"].pop("allow_boundary_duplicate", None)
        timeline.write_text(json.dumps(data, indent=2), encoding="utf-8")
        report = pipeline.validate_timeline(timeline)
        self.assertFalse(report.ok)
        self.assertTrue(any("loop boundary" in error for error in report.errors))

        data = json.loads(timeline.read_text(encoding="utf-8"))
        data["actions"]["idle_south"]["allow_boundary_duplicate"] = True
        timeline.write_text(json.dumps(data, indent=2), encoding="utf-8")
        report = pipeline.validate_timeline(timeline)
        self.assertTrue(report.ok, report.as_dict())

    def test_preview_keeps_full_speed_and_slow_durations_in_sidecars(self) -> None:
        timeline = self._write_timeline()
        fullspeed = self.root / "preview.gif"
        slow = self.root / "preview_slow.gif"
        result = pipeline.make_preview(timeline, fullspeed, slow_output=slow, slow_factor=2.5)
        self.assertTrue(fullspeed.exists())
        self.assertTrue(slow.exists())
        self.assertEqual(result["fullspeed"]["durations_ms"], [100, 200])
        self.assertEqual(result["slow"]["durations_ms"], [250, 500])
        full_receipt = json.loads(Path(result["fullspeed"]["sidecar"]).read_text(encoding="utf-8"))
        slow_receipt = json.loads(Path(result["slow"]["sidecar"]).read_text(encoding="utf-8"))
        self.assertEqual(full_receipt["target_playback"], "NOT_TESTED")
        self.assertEqual(slow_receipt["preview_kind"], "slow")
        self.assertEqual(slow_receipt["source_durations_ms"], [100, 200])

    def test_expected_counts_and_out_of_bounds_frame_fail(self) -> None:
        timeline = self._write_timeline()
        report = pipeline.validate_timeline(timeline, expected_frames=3, expected_actions={"idle_south": 3})
        self.assertFalse(report.ok)
        self.assertTrue(any("expected 3 frames" in error for error in report.errors))

        data = json.loads(timeline.read_text(encoding="utf-8"))
        data["frames"][0]["source_offset"] = {"x": 5, "y": 5}
        timeline.write_text(json.dumps(data, indent=2), encoding="utf-8")
        report = pipeline.validate_timeline(timeline)
        self.assertFalse(report.ok)
        self.assertTrue(any("exceeds logical canvas" in error for error in report.errors))

    def test_rive_lottie_and_spine_checks_are_honest_about_runtime(self) -> None:
        rml_dir = self.root / "rive_project"
        rml_dir.mkdir()
        riv = self.root / "hero.riv"
        rev = self.root / "hero.rev"
        riv.write_bytes(b"runtime placeholder")
        rev.write_bytes(b"backup placeholder")
        rive = pipeline.inspect_rive(rml=str(rml_dir), riv=str(riv), rev=str(rev), target_runtime="web")
        self.assertEqual(rive["editable_source"]["status"], "PRESENT")
        self.assertEqual(rive["runtime"]["status"], "PRESENT")
        self.assertEqual(rive["backup"]["status"], "PRESENT")
        self.assertEqual(rive["signed_export"], "NOT_TESTED")
        self.assertEqual(rive["target_playback"], "NOT_TESTED")

        lottie = self.root / "animation.json"
        lottie.write_text(json.dumps({"v": "5.7.0", "fr": 24, "ip": 0, "op": 12, "layers": []}), encoding="utf-8")
        lottie_report = pipeline.inspect_lottie(lottie, target_runtime="web")
        self.assertEqual(lottie_report["json_envelope"], "PASS")
        self.assertEqual(lottie_report["feature_subset"], "NOT_TESTED")

        spine = pipeline.inspect_spine(source=str(rml_dir), runtime=str(riv), atlas=str(rev), version="4.2", target_runtime="unity")
        self.assertEqual(spine["editor_runtime_version_match"], "NOT_TESTED")
        self.assertEqual(spine["target_playback"], "NOT_TESTED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
