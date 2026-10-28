"""Optional real-Blender integration coverage for the modeling adapter.

The tests use only temporary files and a discovered Blender executable.  They
skip as a class only when no executable is available; once Blender is found,
fixture creation, receipts, renders, and fresh import readback are hard test
requirements rather than mocked or text-only checks.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


TESTS_ROOT = Path(__file__).resolve().parent


def _discover_skill_root() -> Path:
    """Find the skill in either repository or normalized public layout.

    The released package places ``tests/`` beside ``skills/``.  The source
    repository places both under ``plugin/``.  Search from the test directory
    upward so the test never depends on a fixed repository depth.
    """

    candidates: list[Path] = []
    for ancestor in (TESTS_ROOT, *TESTS_ROOT.parents):
        candidates.extend(
            [
                ancestor / "skills" / "blender-engineering-modeling",
                ancestor / "plugin" / "skills" / "blender-engineering-modeling",
            ]
        )
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "scripts" / "blender_engineering.py").is_file():
            return candidate
    searched = ", ".join(str(path) for path in candidates)
    raise RuntimeError(f"Could not locate blender-engineering-modeling skill; searched: {searched}")


SKILL_ROOT = _discover_skill_root()
ADAPTER = SKILL_ROOT / "scripts" / "blender_engineering.py"
FIXTURE_SCRIPT = TESTS_ROOT / "fixtures" / "create_blender_fixture.py"


def _resolve_blender() -> Path | None:
    """Resolve a real Blender binary without depending on a user home path."""

    candidates: list[Path] = []
    explicit = os.environ.get("BLENDER_BIN")
    if explicit:
        candidates.append(Path(explicit).expanduser())
    for name in ("blender", "blender.exe"):
        found = shutil.which(name)
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
    program_files = os.environ.get("PROGRAMFILES")
    if program_files:
        candidates.append(Path(program_files) / "Blender Foundation" / "Blender" / "blender.exe")
    candidates.extend(Path("/Applications").glob("Blender*.app/Contents/MacOS/Blender"))

    seen: set[str] = set()
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


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object at {path}")
    return value


class BlenderEngineeringIntegrationTests(unittest.TestCase):
    """Run the adapter against a fresh Blender process for each operation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.blender = _resolve_blender()
        if cls.blender is None:
            raise unittest.SkipTest("No real Blender executable found")
        if not ADAPTER.is_file():
            raise AssertionError(f"adapter not found: {ADAPTER}")
        if not FIXTURE_SCRIPT.is_file():
            raise AssertionError(f"fixture script not found: {FIXTURE_SCRIPT}")

        cls._temp_dir = tempfile.TemporaryDirectory(prefix="blender-engineering-tests-")
        cls.root = Path(cls._temp_dir.name)
        cls.fixture = cls.root / "fixture.blend"
        command = [
            str(cls.blender),
            "--background",
            "--factory-startup",
            "--python",
            str(FIXTURE_SCRIPT),
            "--",
            "--out",
            str(cls.fixture),
        ]
        started = time.monotonic()
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=90,
            check=False,
        )
        cls.fixture_elapsed_seconds = round(time.monotonic() - started, 3)
        if completed.returncode != 0 or not cls.fixture.is_file():
            raise AssertionError(
                "Blender fixture creation failed "
                f"(exit={completed.returncode}, stdout={completed.stdout[-2000:]!r}, "
                f"stderr={completed.stderr[-2000:]!r})"
            )
        cls.source_sha256 = hashlib.sha256(cls.fixture.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls) -> None:
        temp_dir = getattr(cls, "_temp_dir", None)
        if temp_dir is not None:
            temp_dir.cleanup()

    def _run_adapter(self, *arguments: str) -> tuple[dict, subprocess.CompletedProcess[str]]:
        command = [sys.executable, str(ADAPTER), *arguments, "--blender", str(self.blender)]
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )
        if not completed.stdout.strip():
            self.fail(
                f"adapter produced no JSON (exit={completed.returncode}, "
                f"stderr={completed.stderr[-2000:]!r})"
            )
        try:
            receipt = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"adapter stdout was not JSON: {exc}; "
                f"stdout={completed.stdout[-2000:]!r}; stderr={completed.stderr[-2000:]!r}"
            )
        self.assertIsInstance(receipt, dict)
        return receipt, completed

    def _write_contract(self, name: str, contract: dict) -> Path:
        path = self.root / name
        path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
        return path

    def _create_fixture(
        self,
        path: Path,
        *,
        with_dependencies: bool = False,
        with_faraway_helpers: bool = False,
        with_beveled_curve: bool = False,
    ) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.blender),
            "--background",
            "--factory-startup",
            "--python",
            str(FIXTURE_SCRIPT),
            "--",
            "--out",
            str(path),
        ]
        if with_dependencies:
            command.append("--with-dependencies")
        if with_faraway_helpers:
            command.append("--with-faraway-helpers")
        if with_beveled_curve:
            command.append("--with-beveled-curve")
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=90,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=f"fixture creation failed: {completed.stderr[-3000:]}",
        )
        self.assertTrue(path.is_file())
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _geometry_signature(manifest: dict) -> list[tuple]:
        signature = []
        for record in manifest["objects"]:
            if record["type"] != "MESH":
                continue
            evaluated = record["evaluated_stats"]
            bounds = record["world_bounds"]
            signature.append(
                (
                    record["name"],
                    record["type"],
                    evaluated.get("vertices"),
                    evaluated.get("edges"),
                    evaluated.get("polygons"),
                    tuple(round(float(value), 6) for value in bounds["dimensions"]),
                )
            )
        return sorted(signature)

    def test_inspect_proves_evaluated_modifier_and_external_path(self) -> None:
        receipt_path = self.root / "inspect.json"
        receipt, completed = self._run_adapter(
            "inspect",
            "--blend",
            str(self.fixture),
            "--out",
            str(receipt_path),
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["source_sha256"], self.source_sha256)

        body = next(
            item for item in receipt["inspection"]["objects"] if item.get("part_id") == "body"
        )
        source_stats = body["source_stats"]
        evaluated_stats = body["evaluated_stats"]
        self.assertGreater(source_stats["polygons"], 0)
        self.assertGreater(evaluated_stats["polygons"], source_stats["polygons"])
        self.assertGreater(evaluated_stats["vertices"], source_stats["vertices"])
        self.assertEqual(body["nonfinite_count"], 0)
        self.assertTrue(body["world_bounds"]["finite"])

        missing = receipt["inspection"]["external_files"]["missing"]
        expected_missing = str((self.fixture.parent / "missing-texture.png").resolve())
        self.assertIn(expected_missing, missing)

    def test_curve_bounds_use_fresh_evaluated_mesh_vertices(self) -> None:
        curve_fixture = self.root / "curve-fixture" / "fixture.blend"
        curve_sha = self._create_fixture(curve_fixture, with_beveled_curve=True)
        inspect_path = self.root / "curve-inspect.json"
        inspected, inspect_process = self._run_adapter(
            "inspect",
            "--blend",
            str(curve_fixture),
            "--out",
            str(inspect_path),
        )
        self.assertEqual(inspect_process.returncode, 0)
        self.assertEqual(inspected["status"], "PASS")
        curve_record = next(
            record for record in inspected["inspection"]["objects"] if record["name"] == "BeveledCurve"
        )
        self.assertEqual(curve_record["type"], "CURVE")
        self.assertGreater(curve_record["evaluated_stats"]["vertices"], 0)
        self.assertEqual(curve_record["evaluated_stats"]["bounds_method"], "evaluated_mesh_vertices")
        self.assertTrue(curve_record["evaluated_stats"]["bounds_exact"])

        fresh_script = self.root / "fresh_curve_bounds.py"
        fresh_script.write_text(
            """import json, math, sys
from pathlib import Path


def args_after_marker():
    values = sys.argv[sys.argv.index("--") + 1 :]
    return dict(zip(values[::2], values[1::2]))


def main():
    import bpy

    args = args_after_marker()
    result = {"status": "FAIL"}
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj = bpy.data.objects.get("BeveledCurve")
        if obj is None or obj.type != "CURVE":
            raise RuntimeError("beveled curve object was not found")
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
        try:
            points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
            if not points:
                raise RuntimeError("evaluated curve mesh had no vertices")
            finite = all(math.isfinite(float(value)) for point in points for value in point)
            lower = [min(float(point[index]) for point in points) for index in range(3)]
            upper = [max(float(point[index]) for point in points) for index in range(3)]
            dimensions = [upper[index] - lower[index] for index in range(3)]
            result = {
                "status": "PASS" if finite else "FAIL",
                "finite": finite,
                "vertex_count": len(mesh.vertices),
                "polygon_count": len(mesh.polygons),
                "min": lower,
                "max": upper,
                "dimensions": dimensions,
            }
        finally:
            evaluated.to_mesh_clear()
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    Path(args["--out"]).write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
""",
            encoding="utf-8",
        )
        fresh_report = self.root / "fresh-curve-bounds.json"
        fresh_process = subprocess.run(
            [
                str(self.blender),
                "--background",
                "--factory-startup",
                str(curve_fixture),
                "--python",
                str(fresh_script),
                "--",
                "--out",
                str(fresh_report),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual(
            fresh_process.returncode,
            0,
            msg=f"fresh curve bounds readback failed: {fresh_process.stderr[-3000:]}",
        )
        fresh = _read_json(fresh_report)
        self.assertEqual(fresh["status"], "PASS")
        self.assertEqual(fresh["vertex_count"], curve_record["evaluated_stats"]["vertices"])
        self.assertEqual(fresh["polygon_count"], curve_record["evaluated_stats"]["polygons"])
        for key in ("min", "max", "dimensions"):
            for actual, expected in zip(curve_record["world_bounds"][key], fresh[key]):
                self.assertTrue(math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-6))
        self.assertEqual(hashlib.sha256(curve_fixture.read_bytes()).hexdigest(), curve_sha)

    def test_validate_spoofed_empty_fails_type_and_nonzero_extent(self) -> None:
        contract = self._write_contract(
            "spoof-contract.json",
            {
                "asset_class": "hard_surface",
                "required_parts": [
                    {
                        "part_id": "spoofed_mesh",
                        "count": 1,
                        "type": "MESH",
                        "min_extent": 0.1,
                    }
                ],
                "allow_missing_files": True,
            },
        )
        receipt_path = self.root / "spoof-validation.json"
        receipt, completed = self._run_adapter(
            "validate",
            "--blend",
            str(self.fixture),
            "--contract",
            str(contract),
            "--out",
            str(receipt_path),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(receipt["status"], "FAIL")
        required = receipt["validation"]["checks"]["required_parts"]
        self.assertEqual(required["status"], "FAIL")
        proof = required["evidence"]["parts"][0]["evidence"]
        self.assertEqual(proof["actual_count"], 1)
        self.assertEqual(proof["matched"][0]["type"], "EMPTY")
        self.assertEqual(proof["type_error"], "MESH")
        self.assertEqual(proof["matched"][0]["extent"], [0.0, 0.0, 0.0])
        self.assertEqual(proof["extent_error"]["minimum"], 0.1)

    def test_validate_units_bounds_and_missing_file_failures(self) -> None:
        contract = self._write_contract(
            "hard-failure-contract.json",
            {
                "asset_class": "hard_surface",
                "required_parts": [{"part_id": "body", "count": 1, "type": "MESH"}],
                "units": {"system": "IMPERIAL", "scale_length": 2.0},
                "dimensions": {"target": [10.0, 10.0, 10.0], "tolerance": 0.001},
                "allow_missing_files": False,
            },
        )
        receipt_path = self.root / "hard-failure-validation.json"
        receipt, completed = self._run_adapter(
            "validate",
            "--blend",
            str(self.fixture),
            "--contract",
            str(contract),
            "--out",
            str(receipt_path),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(receipt["status"], "FAIL")
        checks = receipt["validation"]["checks"]
        self.assertEqual(checks["units"]["status"], "FAIL")
        self.assertEqual(checks["dimensions"]["status"], "FAIL")
        self.assertEqual(checks["missing_external_files"]["status"], "FAIL")

    def test_validate_omitted_checks_are_coverage_only_and_unsupported_blocks(self) -> None:
        contract = self._write_contract(
            "omitted-check-contract.json",
            {
                "required_parts": [{"part_id": "body", "count": 1, "type": "MESH"}],
                "allow_missing_files": True,
            },
        )
        receipt_path = self.root / "omitted-check-validation.json"
        receipt, completed = self._run_adapter(
            "validate",
            "--blend",
            str(self.fixture),
            "--contract",
            str(contract),
            "--out",
            str(receipt_path),
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(receipt["status"], "PASS")
        validation = receipt["validation"]
        self.assertEqual(validation["status"], "PASS")
        self.assertIn("required_parts", validation["declared_check_names"])
        for omitted in ("units", "dimensions", "floor_contact"):
            self.assertNotIn(omitted, validation["declared_check_names"])
            self.assertEqual(validation["checks"][omitted]["status"], "NOT_TESTED")
            self.assertIn(omitted, validation["untested_coverage"])

        unsupported_contract = self._write_contract(
            "unsupported-check-contract.json",
            {
                "required_parts": [{"part_id": "body", "count": 1, "type": "MESH"}],
                "allow_missing_files": True,
                "required_checks": ["rig"],
            },
        )
        unsupported_receipt_path = self.root / "unsupported-check-validation.json"
        unsupported, unsupported_process = self._run_adapter(
            "validate",
            "--blend",
            str(self.fixture),
            "--contract",
            str(unsupported_contract),
            "--out",
            str(unsupported_receipt_path),
        )
        self.assertEqual(unsupported_process.returncode, 2)
        self.assertEqual(unsupported["status"], "NOT_TESTED")
        unsupported_validation = unsupported["validation"]
        self.assertIn("unsupported_requested_checks", unsupported_validation["declared_check_names"])
        self.assertEqual(
            unsupported_validation["checks"]["unsupported_requested_checks"]["status"],
            "NOT_TESTED",
        )

    def test_validate_preserves_relative_image_and_linked_library_context(self) -> None:
        dependency_fixture = self.root / "dependency-fixture" / "fixture.blend"
        dependency_sha = self._create_fixture(dependency_fixture, with_dependencies=True)

        inspect_path = self.root / "dependency-inspect.json"
        inspected, inspect_process = self._run_adapter(
            "inspect",
            "--blend",
            str(dependency_fixture),
            "--out",
            str(inspect_path),
        )
        self.assertEqual(inspect_process.returncode, 0)
        self.assertEqual(inspected["status"], "PASS")
        self.assertEqual(inspected["source_sha256"], dependency_sha)
        inspected_manifest = inspected["inspection"]
        self.assertEqual(inspected_manifest["external_files"]["missing"], [])
        external_by_kind = {
            item["kind"]: item for item in inspected_manifest["external_files"]["files"]
        }
        self.assertTrue(external_by_kind["image"]["exists"])
        self.assertTrue(external_by_kind["library"]["exists"])
        self.assertTrue(external_by_kind["image"]["path"].endswith("/textures/relative.png"))
        self.assertTrue(external_by_kind["library"]["path"].endswith("/libraries/linked_part.blend"))

        contract = self._write_contract(
            "dependency-contract.json",
            {
                "required_parts": [
                    {"name": "Body", "count": 1, "type": "MESH"},
                    {"name": "LinkedLibraryPart", "count": 1, "type": "MESH"},
                ],
                "allow_missing_files": False,
            },
        )
        validation_path = self.root / "dependency-validation.json"
        validated, validate_process = self._run_adapter(
            "validate",
            "--blend",
            str(dependency_fixture),
            "--contract",
            str(contract),
            "--out",
            str(validation_path),
        )
        self.assertEqual(validate_process.returncode, 0)
        self.assertEqual(validated["status"], "PASS")
        self.assertEqual(validated["validation"]["status"], "PASS")
        self.assertEqual(validated["source_sha256"], dependency_sha)
        self.assertEqual(validated["validation_policy"]["mode"], "source_read_only")
        self.assertEqual(validated["validation_policy"]["dependency_context"], "original_blend_directory")
        self.assertTrue(validated["validation_policy"]["source_unchanged"])
        self.assertEqual(validated["validation_policy"]["source_sha256_before"], dependency_sha)
        self.assertEqual(validated["validation_policy"]["source_sha256_after"], dependency_sha)
        self.assertEqual(Path(validated["opened_blend"]).resolve(), dependency_fixture.resolve())

        validated_manifest = validated["inspection"]
        self.assertEqual(validated_manifest["external_files"]["missing"], [])
        self.assertEqual(
            self._geometry_signature(inspected_manifest),
            self._geometry_signature(validated_manifest),
        )
        self.assertEqual(
            inspected_manifest["stable_fingerprint"],
            validated_manifest["stable_fingerprint"],
        )
        self.assertEqual(
            hashlib.sha256(dependency_fixture.read_bytes()).hexdigest(),
            dependency_sha,
        )

    def test_render_produces_five_neutral_diagnostic_views(self) -> None:
        render_dir = self.root / "render"
        receipt, completed = self._run_adapter(
            "render",
            "--blend",
            str(self.fixture),
            "--out-dir",
            str(render_dir),
            "--views",
            "hero,front,side,back,top",
            "--resolution",
            "64",
            "--samples",
            "4",
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(receipt["status"], "PASS")
        render = receipt["render"]
        self.assertEqual(render["render_role"], "neutral_diagnostic")
        self.assertFalse(render["artistic_beauty_render"])
        self.assertTrue(render["fresh_saved_blend"])
        views = render["views"]
        self.assertEqual([view["view"] for view in views], ["hero", "front", "side", "back", "top"])
        for view in views:
            self.assertEqual(view["status"], "PASS")
            path = Path(view["path"])
            self.assertTrue(path.is_file())
            self.assertEqual(view["png_dimensions"], [64, 64])
            self.assertEqual(len(view["sha256"]), 64)
            self.assertEqual(view["actual_settings"]["resolution"], [64, 64, 100])
            self.assertEqual(view["actual_settings"]["samples_status"], "PASS")
        self.assertEqual(hashlib.sha256(self.fixture.read_bytes()).hexdigest(), self.source_sha256)

    def test_faraway_presentation_helpers_do_not_change_fit_bounds(self) -> None:
        helper_fixture = self.root / "faraway-helpers" / "fixture.blend"
        helper_sha = self._create_fixture(helper_fixture, with_faraway_helpers=True)

        base_inspect_path = self.root / "base-fit-inspect.json"
        base_inspect, base_process = self._run_adapter(
            "inspect",
            "--blend",
            str(self.fixture),
            "--out",
            str(base_inspect_path),
        )
        self.assertEqual(base_process.returncode, 0)
        self.assertEqual(base_inspect["status"], "PASS")
        base_bounds = base_inspect["inspection"]["scene_bounds"]

        helper_inspect_path = self.root / "helper-fit-inspect.json"
        helper_inspect, helper_process = self._run_adapter(
            "inspect",
            "--blend",
            str(helper_fixture),
            "--out",
            str(helper_inspect_path),
        )
        self.assertEqual(helper_process.returncode, 0)
        self.assertEqual(helper_inspect["status"], "PASS")
        helper_manifest = helper_inspect["inspection"]
        self.assertEqual(helper_manifest["scene_bounds"], base_bounds)
        helper_records = {record["name"]: record for record in helper_manifest["objects"]}
        self.assertEqual(helper_records["FarAwayCamera"]["type"], "CAMERA")
        self.assertEqual(helper_records["FarAwayLight"]["type"], "LIGHT")
        self.assertEqual(helper_records["FarAwayEmpty"]["type"], "EMPTY")
        self.assertFalse(helper_records["FarAwayCamera"]["renderable_for_bounds"])
        self.assertFalse(helper_records["FarAwayLight"]["renderable_for_bounds"])
        self.assertFalse(helper_records["FarAwayEmpty"]["renderable_for_bounds"])

        render_dir = self.root / "faraway-helpers" / "render"
        rendered, render_process = self._run_adapter(
            "render",
            "--blend",
            str(helper_fixture),
            "--out-dir",
            str(render_dir),
            "--views",
            "hero",
            "--resolution",
            "32",
            "--samples",
            "1",
        )
        self.assertEqual(render_process.returncode, 0)
        self.assertEqual(rendered["status"], "PASS")
        self.assertEqual(rendered["render"]["source_scene_fingerprint"], helper_manifest["stable_fingerprint"])
        fit = rendered["render"]["camera_rig"]
        expected_center = [
            (base_bounds["min"][index] + base_bounds["max"][index]) * 0.5
            for index in range(3)
        ]
        expected_radius = max(base_bounds["dimensions"]) * 0.5
        for actual, expected in zip(fit["fit_center"], expected_center):
            self.assertTrue(math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-6))
        self.assertTrue(math.isclose(fit["fit_radius"], expected_radius, rel_tol=1e-6, abs_tol=1e-6))
        self.assertEqual(hashlib.sha256(helper_fixture.read_bytes()).hexdigest(), helper_sha)

    def test_glb_fresh_blender_import_has_geometry_bounds(self) -> None:
        inspect_receipt_path = self.root / "source-for-glb-inspect.json"
        inspect_receipt, inspect_process = self._run_adapter(
            "inspect",
            "--blend",
            str(self.fixture),
            "--out",
            str(inspect_receipt_path),
        )
        self.assertEqual(inspect_process.returncode, 0)
        self.assertEqual(inspect_receipt["status"], "PASS")
        source_dimensions = inspect_receipt["inspection"]["scene_bounds"]["dimensions"]

        artifact = self.root / "fixture.glb"
        export_receipt, export_process = self._run_adapter(
            "export",
            "--blend",
            str(self.fixture),
            "--format",
            "glb",
            "--out",
            str(artifact),
        )
        self.assertEqual(export_process.returncode, 0)
        self.assertEqual(export_receipt["status"], "PASS")
        self.assertFalse(export_receipt["export"]["native_engine_verified"])
        self.assertEqual(export_receipt["export"]["readback"]["status"], "PASS")
        self.assertEqual(export_receipt["source_sha256"], self.source_sha256)

        import_script = self.root / "fresh_import_readback.py"
        import_script.write_text(
            """import json, math, sys
from pathlib import Path


def args_after_marker():
    values = sys.argv[sys.argv.index("--") + 1 :]
    return dict(zip(values[::2], values[1::2]))


def main():
    import bpy

    args = args_after_marker()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = {"status": "FAIL", "mesh_count": 0}
    try:
        operation = bpy.ops.import_scene.gltf(filepath=args["--glb"])
        if "FINISHED" not in operation:
            raise RuntimeError("GLB importer did not finish")
        depsgraph = bpy.context.evaluated_depsgraph_get()
        points = []
        mesh_count = 0
        for obj in bpy.context.scene.objects:
            if obj.type != "MESH":
                continue
            mesh_count += 1
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            try:
                points.extend(evaluated.matrix_world @ vertex.co for vertex in mesh.vertices)
            finally:
                evaluated.to_mesh_clear()
        if not points:
            raise RuntimeError("fresh import contained no mesh vertices")
        finite = all(math.isfinite(float(value)) for point in points for value in point)
        lower = [min(float(point[index]) for point in points) for index in range(3)]
        upper = [max(float(point[index]) for point in points) for index in range(3)]
        dimensions = [upper[index] - lower[index] for index in range(3)]
        result = {
            "status": "PASS" if finite and all(value > 0.0 for value in dimensions) else "FAIL",
            "mesh_count": mesh_count,
            "finite": finite,
            "min": lower,
            "max": upper,
            "dimensions": dimensions,
        }
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    Path(args["--out"]).write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
""",
            encoding="utf-8",
        )
        import_report_path = self.root / "fresh-import.json"
        import_process = subprocess.run(
            [
                str(self.blender),
                "--background",
                "--factory-startup",
                "--python",
                str(import_script),
                "--",
                "--glb",
                str(artifact),
                "--out",
                str(import_report_path),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual(
            import_process.returncode,
            0,
            msg=f"fresh GLB import failed: {import_process.stderr[-3000:]}",
        )
        imported = _read_json(import_report_path)
        self.assertEqual(imported["status"], "PASS")
        self.assertGreaterEqual(imported["mesh_count"], 1)
        self.assertTrue(imported["finite"])
        self.assertTrue(all(value > 0.0 for value in imported["dimensions"]))
        for imported_value, source_value in zip(imported["dimensions"], source_dimensions):
            self.assertTrue(math.isclose(imported_value, source_value, rel_tol=0.03, abs_tol=0.03))
        self.assertEqual(hashlib.sha256(self.fixture.read_bytes()).hexdigest(), self.source_sha256)


if __name__ == "__main__":
    unittest.main(verbosity=2)
