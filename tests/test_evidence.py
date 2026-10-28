"""Focused tests for the fail-closed structural evidence gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = PLUGIN_ROOT / "tools" / "evidence.py"
MODULE_SPEC = importlib.util.spec_from_file_location("plugin_evidence", EVIDENCE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
evidence = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(evidence)
VALIDATOR_PATH = PLUGIN_ROOT / "tools" / "validate_package.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "plugin_validate_package", VALIDATOR_PATH
)
assert VALIDATOR_SPEC is not None and VALIDATOR_SPEC.loader is not None
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(validator)


class EvidenceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "evidence").mkdir()
        (self.root / "deliverable").mkdir()
        (self.root / "evidence" / "hero.png").write_bytes(b"render evidence")
        (self.root / "evidence" / "readback.json").write_text(
            '{"reopened": true}\n', encoding="utf-8"
        )
        (self.root / "deliverable" / "model.blend").write_bytes(b"blend bytes")
        self.contract_path = self.root / "contract.json"
        self.report_path = self.root / "report.json"
        self.contract = {
            "schema_version": "0.1",
            "criteria": [
                {
                    "id": "C001",
                    "required": True,
                    "origin": "user_explicit",
                    "requirement": "The primary form is present.",
                },
                {
                    "id": "C002",
                    "required": False,
                    "origin": "agent_assumption",
                    "requirement": "An optional preview exists.",
                },
                {
                    "id": "C003",
                    "required": True,
                    "origin": "use_requirement",
                    "requirement": "The artifact can be reopened.",
                },
            ],
            "required_artifacts": [{"path": "deliverable/model.blend"}],
        }
        self.report = {
            "schema_version": "0.1",
            "results": [
                {
                    "criterion_id": "C001",
                    "status": "PASS",
                    "evidence": [
                        {"path": "evidence/hero.png", "kind": "render", "view": "hero"}
                    ],
                },
                {
                    "criterion_id": "C002",
                    "status": "NOT_APPLICABLE",
                    "applicabilityreason": "The optional preview was not requested.",
                },
                {
                    "criterion_id": "C003",
                    "status": "PASS",
                    "evidence": [
                        {"path": "evidence/readback.json", "kind": "reopen_readback"}
                    ],
                },
            ],
            "artifacts": [
                {"path": "deliverable/model.blend", "kind": "blend_scene"}
            ],
        }
        self._write_inputs()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_inputs(self) -> None:
        self.contract_path.write_text(
            json.dumps(self.contract), encoding="utf-8"
        )
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")

    def _run(self) -> dict:
        return evidence.run_gate(self.contract_path, self.report_path)

    def test_ready_requires_real_evidence_and_reports_structural_limits(self) -> None:
        result = self._run()
        self.assertEqual(result["status"], evidence.READY)
        self.assertTrue(result["structural_gate_only"])
        self.assertFalse(result["visual_quality_proven"])
        self.assertFalse(result["actual_reading_proven"])
        self.assertEqual(result["user_taste_status"], "NOT_EVALUATED")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["required"]["pass"], 2)
        self.assertEqual(result["required"]["not_applicable"], 0)
        self.assertTrue(all(item["evidence"] for item in result["criteria"] if item["status"] == "PASS"))

    def test_optional_failure_does_not_mask_required_passes(self) -> None:
        self.report["results"][1] = {
            "criterion_id": "C002",
            "status": "FAIL",
            "evidence": [],
        }
        self._write_inputs()
        result = self._run()
        self.assertEqual(result["status"], evidence.READY)
        self.assertTrue(any("optional criteria" in warning for warning in result["warnings"]))

    def test_all_optional_criteria_cannot_be_ready(self) -> None:
        for criterion in self.contract["criteria"]:
            criterion["required"] = False
        self._write_inputs()
        result = self._run()
        self.assertEqual(result["status"], evidence.INCOMPLETE)
        self.assertTrue(
            any("at least one required criterion" in item for item in result["errors"])
        )

    def test_required_failure_uncertain_and_not_tested_block(self) -> None:
        for blocked_status in ("FAIL", "UNCERTAIN", "NOT_TESTED"):
            with self.subTest(status=blocked_status):
                self.report["results"][0] = {
                    "criterion_id": "C001",
                    "status": blocked_status,
                    "evidence": [],
                }
                self._write_inputs()
                result = self._run()
                self.assertEqual(result["status"], evidence.INCOMPLETE)
                self.assertTrue(
                    any(f"C001: {blocked_status}" in item for item in result["required"]["blockers"])
                )
                self.report["results"][0] = {
                    "criterion_id": "C001",
                    "status": "PASS",
                    "evidence": [{"path": "evidence/hero.png", "kind": "render"}],
                }

    def test_duplicate_criterion_ids_fail_closed(self) -> None:
        self.contract["criteria"].append(dict(self.contract["criteria"][0]))
        self._write_inputs()
        result = self._run()
        self.assertEqual(result["status"], evidence.INCOMPLETE)
        self.assertTrue(any("duplicate criterion id" in item for item in result["errors"]))

    def test_not_applicable_requires_an_explanation(self) -> None:
        self.report["results"][0] = {
            "criterion_id": "C001",
            "status": "NOT_APPLICABLE",
            "evidence": [],
        }
        self._write_inputs()
        result = self._run()
        self.assertEqual(result["status"], evidence.INCOMPLETE)
        self.assertTrue(any("applicabilityreason" in item for item in result["errors"]))

    def test_missing_evidence_and_hash_mismatch_fail_closed(self) -> None:
        self.report["results"][0] = {
            "criterion_id": "C001",
            "status": "PASS",
            "evidence": [{"path": "evidence/missing.png", "kind": "render"}],
        }
        self._write_inputs()
        missing = self._run()
        self.assertEqual(missing["status"], evidence.INCOMPLETE)
        self.assertTrue(any("not a real file" in item for item in missing["errors"]))

        self.report["results"][0] = {
            "criterion_id": "C001",
            "status": "PASS",
            "evidence": [
                {
                    "path": "evidence/hero.png",
                    "kind": "render",
                    "sha256": "0" * 64,
                }
            ],
        }
        self._write_inputs()
        mismatch = self._run()
        self.assertEqual(mismatch["status"], evidence.INCOMPLETE)
        self.assertTrue(any("sha256 mismatch" in item for item in mismatch["errors"]))

    def test_missing_artifact_blocks_even_when_criteria_pass(self) -> None:
        self.report["artifacts"] = []
        self._write_inputs()
        result = self._run()
        self.assertEqual(result["status"], evidence.INCOMPLETE)
        self.assertTrue(any("artifacts must contain" in item for item in result["errors"]))

    def test_missing_result_id_is_not_silently_ignored(self) -> None:
        self.report["results"] = self.report["results"][:2]
        self._write_inputs()
        result = self._run()
        self.assertEqual(result["status"], evidence.INCOMPLETE)
        self.assertTrue(any("missing result for criterion_id: C003" in item for item in result["errors"]))

    def test_empty_requirements_are_invalid(self) -> None:
        self.contract["requirements"] = []
        self._write_inputs()
        result = self._run()
        self.assertEqual(result["status"], evidence.INCOMPLETE)
        self.assertTrue(any("requirements must be a non-empty" in item for item in result["errors"]))

    def test_invalid_json_and_nonfinite_values_fail_closed(self) -> None:
        self.contract_path.write_text("{not valid json", encoding="utf-8")
        result = self._run()
        self.assertEqual(result["status"], evidence.INCOMPLETE)
        self.assertTrue(any("invalid JSON" in item for item in result["errors"]))

        self.contract_path.write_text('{"criteria": [], "weight": NaN}', encoding="utf-8")
        result = self._run()
        self.assertEqual(result["status"], evidence.INCOMPLETE)
        self.assertTrue(any("non-finite" in item for item in result["errors"]))

    def test_inventory_hash_and_identical_skill_copies(self) -> None:
        inventory = evidence.inventory_files([str(self.root)], include_hash=True)
        self.assertEqual(inventory["errors"], [])
        self.assertTrue(any(item["path"].endswith("model.blend") for item in inventory["entries"]))
        hashes = evidence.hash_files([str(self.root / "deliverable" / "model.blend")])
        self.assertEqual(hashes["errors"], [])
        self.assertEqual(len(hashes["entries"][0]["sha256"]), 64)
        canonical = EVIDENCE_PATH.read_bytes()
        for relative in (
            "skills/blender-engineering-modeling/scripts/evidence.py",
            "skills/blender-engineering-animation/scripts/evidence.py",
        ):
            self.assertEqual(canonical, (PLUGIN_ROOT / relative).read_bytes())

    def test_package_validator_resolves_root_and_document_relative_helpers(self) -> None:
        package = self.root / "nested-helper-skill"
        (package / "references" / "nested").mkdir(parents=True)
        (package / "scripts").mkdir()
        (package / "assets").mkdir()
        (package / "SKILL.md").write_text(
            "---\n"
            "name: nested-helper-skill\n"
            "description: A nested helper resolution fixture.\n"
            "---\n"
            "[recipe](references/nested/recipe.md)\n"
            "The package also includes scripts/helper.py and assets/template.json.\n",
            encoding="utf-8",
        )
        (package / "scripts" / "helper.py").write_text(
            "import json\nprint(json.dumps({}))\n", encoding="utf-8"
        )
        (package / "assets" / "template.json").write_text("{}\n", encoding="utf-8")
        (package / "references" / "root-reference.md").write_text(
            "# Root reference\n", encoding="utf-8"
        )
        (package / "references" / "recipe.md").write_text(
            "Use the explicit document-relative helper ../scripts/helper.py.\n"
            "[root reference](root-reference.md)\n",
            encoding="utf-8",
        )
        (package / "references" / "nested" / "recipe.md").write_text(
            "Use bare package-root helpers: scripts/helper.py, "
            "references/root-reference.md, and assets/template.json.\n",
            encoding="utf-8",
        )

        valid = validator.validate_package(package)
        self.assertEqual(valid["status"], "PASS")
        self.assertFalse(
            any(item["code"] == "missing_helper" for item in valid["errors"])
        )

        (package / "references" / "nested" / "escape.md").write_text(
            "This must fail: ../../../scripts/outside.py.\n", encoding="utf-8"
        )
        escaped = validator.validate_package(package)
        self.assertEqual(escaped["status"], "FAIL")
        self.assertTrue(
            any(item["code"] == "helper_outside_skill" for item in escaped["errors"])
        )


if __name__ == "__main__":
    unittest.main()
