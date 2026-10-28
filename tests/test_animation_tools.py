"""Timing and fresh-process animation coverage for the standalone helper.

The unit cases run without Blender. The integration case is skipped when the
local Blender/ffmpeg toolchain is unavailable, and otherwise creates a tiny
animated mesh-plus-armature fixture, renders a 30 FPS step-2 preview, and
round-trips both GLB and FBX through a new Blender process.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest


TESTS_ROOT = Path(__file__).resolve().parent


def _discover_skill_root() -> Path:
    """Find the skill in either ``skills/`` or ``plugin/skills/`` layout."""

    candidates: list[Path] = []
    for ancestor in (TESTS_ROOT, *TESTS_ROOT.parents):
        candidates.extend(
            [
                ancestor / "skills" / "blender-engineering-animation",
                ancestor / "plugin" / "skills" / "blender-engineering-animation",
            ]
        )
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "scripts" / "blender_animation.py").is_file():
            return candidate
    raise RuntimeError(f"Could not locate animation skill; searched: {candidates}")


SKILL_ROOT = _discover_skill_root()
SCRIPT_PATH = SKILL_ROOT / "scripts" / "blender_animation.py"
MODULE_SPEC = importlib.util.spec_from_file_location("blender_animation_test_module", SCRIPT_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
animation = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(animation)


def _resolve_blender() -> Path | None:
    candidates: list[Path] = []
    explicit = os.environ.get("BLENDER_BIN")
    if explicit:
        candidates.append(Path(explicit).expanduser())
    found = shutil.which("blender")
    if found:
        candidates.append(Path(found))
    candidates.extend(
        [
            Path("/Applications/Blender.app/Contents/MacOS/Blender"),
            Path("/Applications/Blender.app/Contents/MacOS/blender"),
            Path("/usr/local/bin/blender"),
            Path("/opt/homebrew/bin/blender"),
            Path("/usr/bin/blender"),
        ]
    )
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except OSError:
            pass
        if candidate.is_file() and (os.access(candidate, os.X_OK) or os.name == "nt"):
            return candidate
    return None


FIXTURE_SCRIPT = r'''
import bpy, math, sys
from pathlib import Path

argv = sys.argv[sys.argv.index("--") + 1:]
out = Path(argv[argv.index("--out") + 1]).resolve()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 30
scene.render.fps_base = 1.0
scene.frame_start = 1
scene.frame_end = 24

bpy.ops.object.armature_add(enter_editmode=True)
arm = bpy.context.object
arm.name = "Rig"
arm.data.name = "RigData"
root = arm.data.edit_bones[0]
root.name = "root"
root.head = (0, 0, 0)
root.tail = (0, 0, 1)
child = arm.data.edit_bones.new("child")
child.head = (0, 0, 1)
child.tail = (0, 0, 2)
child.parent = root
child.use_connect = True
bpy.ops.object.mode_set(mode="POSE")
arm.pose.bones["root"].rotation_mode = "XYZ"
arm.pose.bones["child"].rotation_mode = "XYZ"
scene.frame_set(1)
arm.pose.bones["root"].location = (0, 0, 0)
arm.pose.bones["root"].keyframe_insert(data_path="location", frame=1)
arm.pose.bones["child"].rotation_euler = (0, 0, 0)
arm.pose.bones["child"].keyframe_insert(data_path="rotation_euler", frame=1)
scene.frame_set(24)
arm.pose.bones["root"].location = (1, 0, 0)
arm.pose.bones["root"].keyframe_insert(data_path="location", frame=24)
arm.pose.bones["child"].rotation_euler = (0, math.radians(70), 0)
arm.pose.bones["child"].keyframe_insert(data_path="rotation_euler", frame=24)
bpy.ops.object.mode_set(mode="OBJECT")

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))
mesh = bpy.context.object
mesh.name = "SkinnedMesh"
mesh.parent = arm
mesh.parent_type = "OBJECT"
mesh.matrix_parent_inverse = arm.matrix_world.inverted()
modifier = mesh.modifiers.new("Armature", "ARMATURE")
modifier.object = arm
mesh.vertex_groups.new(name="root")
mesh.vertex_groups.new(name="child")
for vertex in mesh.data.vertices:
    mesh.vertex_groups["child" if vertex.co.z > 0 else "root"].add([vertex.index], 1.0, "REPLACE")
scene.frame_set(1)
mesh.location = (0, 0, 1)
mesh.keyframe_insert(data_path="location", frame=1)
scene.frame_set(24)
mesh.location = (0, 0, 1.25)
mesh.keyframe_insert(data_path="location", frame=24)

bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
ground = bpy.context.object
ground.name = "Ground"
# Keep a real source-relative image dependency in the fixture. The export
# helper must resolve it while the source filepath is active, save/reopen the
# isolated branch, and retain a valid dependency record before readback.
texture_dir = out.parent / "textures"
texture_dir.mkdir(parents=True, exist_ok=True)
texture_file = texture_dir / "relative.png"
texture_file.write_bytes(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cf000000020001e221bc330000000049454e44ae426082"
))
image = bpy.data.images.load(str(texture_file), check_existing=False)
image.filepath = "//textures/relative.png"
material = bpy.data.materials.new("RelativeTextureMaterial")
material.use_nodes = True
texture_node = material.node_tree.nodes.new("ShaderNodeTexImage")
texture_node.image = image
mesh.data.materials.append(material)
bpy.ops.object.camera_add(location=(5, -7, 4))
camera = bpy.context.object
camera.name = "ReviewCamera"
camera.rotation_euler = (math.radians(67), 0, math.radians(35))
scene.camera = camera
bpy.ops.object.light_add(type="AREA", location=(4, -4, 6))
bpy.context.object.name = "KeyLight"
bpy.context.object.data.energy = 500
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out))
'''


STATIC_COPY_SCRIPT = r'''
import bpy, sys
from pathlib import Path

argv = sys.argv[sys.argv.index("--") + 1:]
source = Path(argv[argv.index("--source") + 1]).resolve()
out = Path(argv[argv.index("--out") + 1]).resolve()
bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False)
for owner in list(bpy.data.objects) + list(bpy.data.meshes) + list(bpy.data.armatures):
    clear = getattr(owner, "animation_data_clear", None)
    if clear is not None:
        clear()
bpy.ops.wm.save_as_mainfile(filepath=str(out))
'''


class AnimationTimingTests(unittest.TestCase):
    def test_public_layout_discovery_and_timing_units(self) -> None:
        self.assertTrue((SKILL_ROOT / "scripts" / "blender_animation.py").is_file())
        self.assertEqual(animation.frame_values(1, 6, 4, 20), [1.0, 5.0, 6.0])
        self.assertEqual(
            animation.source_preserving_durations([1.0, 3.0, 5.0], 30.0),
            [2.0 / 30.0, 2.0 / 30.0, 2.0 / 30.0],
        )

    def test_fractional_and_irregular_intervals_are_explicit(self) -> None:
        fractional = animation.frame_values(1.0, 1.5, 0.25, 20)
        self.assertEqual(fractional, [1.0, 1.25, 1.5])
        self.assertAlmostEqual(sum(animation.source_preserving_durations(fractional, 24.0)), 0.03125)
        irregular = animation.frame_values(1.0, 6.0, 4.0, 20)
        self.assertEqual(
            animation.source_preserving_durations(irregular, 30.0),
            [4.0 / 30.0, 1.0 / 30.0, 1.0 / 30.0],
        )

    def test_dependency_policy_is_fail_closed_until_explicit_bypass(self) -> None:
        missing = {"missing": [{"filepath": "//missing.png"}], "missing_count": 1}
        caches = {"status": "none_detected", "point_caches": [], "geometry_nodes": []}
        strict = animation._worker_dependency_completeness(missing, caches, "strict_required")
        bypass = animation._worker_dependency_completeness(missing, caches, "explicit_optional_bypass")
        self.assertEqual(strict["status"], "incomplete")
        self.assertFalse(strict["complete"])
        self.assertEqual(bypass["status"], "explicit_optional_bypass")
        self.assertTrue(bypass["bypassed_as_optional"])

    def test_portable_delivery_requires_external_dependency_bundle_evidence(self) -> None:
        caches = {"status": "none_detected", "point_caches": [], "geometry_nodes": []}
        no_external = animation.portable_delivery_assessment(
            {"checked": [], "missing": [], "missing_count": 0},
            caches,
        )
        self.assertTrue(no_external["portable_delivery_complete"])
        external = animation.portable_delivery_assessment(
            {
                "checked": [{"datablock": "Image", "filepath": "//textures/a.png", "exists": True}],
                "missing": [],
                "missing_count": 0,
            },
            caches,
        )
        self.assertFalse(external["portable_delivery_complete"])
        self.assertEqual(external["status"], "NOT_TESTED_EXTERNAL_DEPENDENCIES")
        packed = animation.portable_delivery_assessment(
            {
                "checked": [{"datablock": "Image", "filepath": "//textures/a.png", "exists": True, "packed": True}],
                "missing": [],
                "missing_count": 0,
            },
            caches,
        )
        self.assertTrue(packed["portable_delivery_complete"])

    def test_geometry_nodes_probe_only_blocks_actual_simulation_nodes(self) -> None:
        simple_tree = SimpleNamespace(
            name="SimpleGeometry",
            nodes=[SimpleNamespace(name="Noise", bl_idname="GeometryNodeNoiseTexture", type="TEX_NOISE", node_tree=None)],
        )
        self.assertEqual(animation._worker_geometry_node_simulation_nodes(simple_tree), [])
        simulation_tree = SimpleNamespace(
            name="SimulationGeometry",
            nodes=[
                SimpleNamespace(
                    name="Simulation Input",
                    bl_idname="GeometryNodeSimulationInput",
                    type="SIMULATION_INPUT",
                    node_tree=None,
                )
            ],
        )
        nested_tree = SimpleNamespace(
            name="OuterGeometry",
            nodes=[
                SimpleNamespace(
                    name="NestedGroup",
                    bl_idname="GeometryNodeGroup",
                    type="GROUP",
                    node_tree=simulation_tree,
                )
            ],
        )
        records = animation._worker_geometry_node_simulation_nodes(nested_tree)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "geometry_nodes_simulation_requires_runtime_probe")
        no_simulation = animation._worker_dependency_completeness(
            {"missing": [], "missing_count": 0},
            {
                "status": "geometry_nodes_without_simulation",
                "point_caches": [],
                "geometry_nodes": [],
            },
            "strict_required",
        )
        self.assertEqual(no_simulation["status"], "complete")
        actual_simulation = animation._worker_dependency_completeness(
            {"missing": [], "missing_count": 0},
            {
                "status": "unknown_runtime_state",
                "point_caches": [],
                "geometry_nodes": [{"status": "geometry_nodes_cache_requires_runtime_probe"}],
            },
            "strict_required",
        )
        self.assertEqual(actual_simulation["status"], "incomplete")


class RealBlenderAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.blender = _resolve_blender()
        cls.ffmpeg = shutil.which("ffmpeg")
        cls.ffprobe = shutil.which("ffprobe")
        if cls.blender is None or cls.ffmpeg is None or cls.ffprobe is None:
            raise unittest.SkipTest("Blender, ffmpeg, and ffprobe are required for real animation coverage")
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="blender-animation-tests-")
        cls.root = Path(cls.temp_dir.name)
        cls.fixture_script = cls.root / "create_fixture.py"
        cls.fixture_script.write_text(FIXTURE_SCRIPT, encoding="utf-8")
        cls.fixture = cls.root / "animated.blend"
        result = subprocess.run(
            [
                str(cls.blender),
                "--background",
                "--factory-startup",
                "--python",
                str(cls.fixture_script),
                "--",
                "--out",
                str(cls.fixture),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=90,
            check=False,
        )
        if result.returncode != 0 or not cls.fixture.is_file():
            raise AssertionError(f"fixture creation failed: {result.stderr[-3000:]}")
        cls.static_fixture_script = cls.root / "make_static_fixture.py"
        cls.static_fixture_script.write_text(STATIC_COPY_SCRIPT, encoding="utf-8")
        cls.static_fixture = cls.root / "static.blend"
        static_result = subprocess.run(
            [
                str(cls.blender),
                "--background",
                "--factory-startup",
                "--python",
                str(cls.static_fixture_script),
                "--",
                "--source",
                str(cls.fixture),
                "--out",
                str(cls.static_fixture),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=90,
            check=False,
        )
        if static_result.returncode != 0 or not cls.static_fixture.is_file():
            raise AssertionError(f"static fixture creation failed: {static_result.stderr[-3000:]}")

    @classmethod
    def tearDownClass(cls) -> None:
        temp_dir = getattr(cls, "temp_dir", None)
        if temp_dir is not None:
            temp_dir.cleanup()

    def _run(self, *args: str) -> tuple[dict, subprocess.CompletedProcess[str]]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--pretty", *args, "--blender", str(self.blender)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180,
            check=False,
        )
        self.assertTrue(completed.stdout.strip(), completed.stderr[-3000:])
        return json.loads(completed.stdout), completed

    def test_source_timed_preview_and_fresh_glb_fbx_readback(self) -> None:
        frames = self.root / "frames"
        full = self.root / "full.mp4"
        slow = self.root / "slow.mp4"
        preview, completed = self._run(
            "preview",
            "--blend",
            str(self.fixture),
            "--out-dir",
            str(frames),
            "--start",
            "1",
            "--end",
            "5",
            "--step",
            "2",
            "--resolution",
            "32x32",
            "--video",
            str(full),
            "--slow-video",
            str(slow),
            "--ffmpeg",
            str(self.ffmpeg),
            "--ffprobe",
            str(self.ffprobe),
            "--out",
            str(self.root / "preview.json"),
        )
        self.assertEqual(completed.returncode, 0, preview)
        self.assertTrue(preview["video_timing"]["full_speed_label"])
        self.assertEqual(preview["video_timing"]["effective_fps"], 15.0)
        self.assertAlmostEqual(preview["video"]["duration_probe"]["duration_seconds"], 0.2, places=3)
        self.assertAlmostEqual(preview["slow_video"]["duration_probe"]["duration_seconds"], 0.4, places=3)

        for format_name, suffix in (("glb", "glb"), ("fbx", "fbx")):
            target = self.root / f"animated.{suffix}"
            receipt, export_process = self._run(
                "export",
                "--blend",
                str(self.fixture),
                "--format",
                format_name,
                "--scope",
                "asset",
                "--out",
                str(target),
                "--receipt",
                str(self.root / f"export-{suffix}.json"),
            )
            self.assertEqual(export_process.returncode, 0, receipt)
            self.assertEqual(receipt["verification_status"], "VERIFIED", receipt)
            self.assertTrue(receipt["readback"]["result"]["animation_survived_readback"])
            expected = receipt["readback"]["result"]["expected_object_time_varying"]
            self.assertEqual(expected, {"Rig": True, "SkinnedMesh": True})
            result_data = receipt["result"]
            self.assertEqual(result_data["dependency_completeness"]["status"], "complete")
            self.assertEqual(result_data["path_preparation"]["status"], "APPLIED")
            self.assertEqual(result_data["branch_path_preparation"]["status"], "APPLIED")
            self.assertEqual(receipt["source_before_sha256"], receipt["source_after_sha256"])
            self.assertFalse(receipt["portable_delivery_complete"])
            self.assertEqual(receipt["portable_delivery"]["status"], "NOT_TESTED_EXTERNAL_DEPENDENCIES")
            self.assertFalse(receipt["complete_delivery"])
            self.assertTrue(
                any(
                    record.get("filepath") == "//textures/relative.png"
                    and record.get("exists") is True
                    for record in result_data["missing_assets_before_export"]["checked"]
                )
            )
            self.assertEqual(result_data["missing_assets_after_reopen"]["missing_count"], 0)

    def test_required_missing_image_and_static_export_gates(self) -> None:
        texture = self.root / "textures" / "relative.png"
        backup = self.root / "textures" / "relative.png.backup"
        texture.rename(backup)
        try:
            strict_target = self.root / "missing-strict.glb"
            strict_receipt, strict_process = self._run(
                "export",
                "--blend",
                str(self.fixture),
                "--format",
                "glb",
                "--scope",
                "asset",
                "--out",
                str(strict_target),
            )
            self.assertNotEqual(strict_process.returncode, 0, strict_receipt)
            self.assertEqual(strict_receipt["verification_status"], "FAILED")
            self.assertEqual(strict_receipt["error_kind"], "missing_required_dependencies")
            self.assertEqual(strict_receipt["dependency_completeness"]["status"], "incomplete")

            optional_target = self.root / "missing-optional.glb"
            optional_receipt, optional_process = self._run(
                "export",
                "--blend",
                str(self.fixture),
                "--format",
                "glb",
                "--scope",
                "asset",
                "--allow-missing-optional",
                "--out",
                str(optional_target),
            )
            self.assertEqual(optional_process.returncode, 0, optional_receipt)
            self.assertEqual(optional_receipt["verification_status"], "VERIFIED_WITH_OPTIONAL_MISSING")
            self.assertFalse(optional_receipt["complete_delivery"])
        finally:
            backup.rename(texture)

        static_target = self.root / "static.glb"
        static_receipt, static_process = self._run(
            "export",
            "--blend",
            str(self.static_fixture),
            "--format",
            "glb",
            "--scope",
            "asset",
            "--out",
            str(static_target),
        )
        self.assertNotEqual(static_process.returncode, 0, static_receipt)
        # The exporter may create an artifact before the gate rejects its
        # unrequested static motion; retain that evidence as partial rather
        # than relabelling it a verified animation delivery.
        self.assertEqual(static_receipt["verification_status"], "PARTIAL_VERIFIED")
        self.assertEqual(static_receipt["motion_readback_status"], "STATIC_READBACK")
        self.assertEqual(static_receipt["error_kind"], "static_readback_without_explicit_allowance")


if __name__ == "__main__":
    unittest.main()
