#!/usr/bin/env python3
"""Small, fail-closed evidence and package inventory helper.

This module deliberately proves only filesystem and report-structure facts.
It never claims that an image was read, that a render is attractive, or that a
user agrees with the result.  The same file is copied into each public skill so
that an individually installed skill does not depend on the plugin root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "0.1"
READY = "READY_FOR_REVIEW"
INCOMPLETE = "INCOMPLETE"
STRUCTURAL_GATE = "structural_gate_only"
VALID_STATUSES = frozenset(
    {"PASS", "FAIL", "UNCERTAIN", "NOT_APPLICABLE", "NOT_TESTED"}
)
class InputError(ValueError):
    """Raised when an input document is not a valid strict JSON document."""


def _reject_nonfinite(name: str) -> Any:
    raise InputError(f"non-finite JSON value is not allowed: {name}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _ensure_finite(value: Any, location: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise InputError(f"non-finite value at {location}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _ensure_finite(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _ensure_finite(child, f"{location}[{index}]")


def load_json(path: Path) -> Any:
    """Load one strict UTF-8 JSON document.

    Python's default decoder accepts NaN and Infinity even though they are not
    JSON.  Reports and contracts are audit inputs, so this helper rejects those
    values and duplicate object keys.
    """

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InputError(f"cannot read JSON file {path}: {exc}") from exc
    try:
        value = json.loads(
            text,
            parse_constant=_reject_nonfinite,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (json.JSONDecodeError, InputError, TypeError) as exc:
        raise InputError(f"invalid JSON in {path}: {exc}") from exc
    _ensure_finite(value)
    return value


def _nonempty_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _absolute_path(value: Any, base: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise InputError("path must be a non-empty string")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve(strict=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_hash(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdefABCDEF" for character in value)


def _iter_files(paths: Sequence[str]) -> tuple[list[Path], list[str]]:
    """Return deterministic files and missing-input diagnostics."""

    found: dict[str, Path] = {}
    errors: list[str] = []
    for raw in paths:
        try:
            path = _absolute_path(raw, Path.cwd())
        except InputError as exc:
            errors.append(f"{raw!r}: {exc}")
            continue
        if not path.exists():
            errors.append(f"path does not exist: {path}")
            continue
        if path.is_file():
            found[str(path)] = path
            continue
        if not path.is_dir():
            errors.append(f"path is neither a file nor directory: {path}")
            continue
        try:
            children = sorted(
                (child for child in path.rglob("*") if child.is_file()),
                key=lambda item: str(item),
            )
        except OSError as exc:
            errors.append(f"cannot inventory directory {path}: {exc}")
            continue
        for child in children:
            resolved = child.resolve(strict=False)
            found[str(resolved)] = resolved
    return [found[key] for key in sorted(found)], errors


def inventory_files(paths: Sequence[str], include_hash: bool = True) -> dict[str, Any]:
    files, errors = _iter_files(paths)
    entries: list[dict[str, Any]] = []
    for path in files:
        entry: dict[str, Any] = {
            "path": str(path),
            "kind": "file",
            "size": path.stat().st_size,
        }
        if include_hash:
            try:
                entry["sha256"] = sha256_file(path)
            except OSError as exc:
                errors.append(f"cannot hash {path}: {exc}")
        entries.append(entry)
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "inventory" if include_hash else "files",
        "entries": entries,
        "errors": errors,
    }


def hash_files(paths: Sequence[str]) -> dict[str, Any]:
    files, errors = _iter_files(paths)
    entries: list[dict[str, Any]] = []
    for path in files:
        try:
            entries.append(
                {
                    "path": str(path),
                    "kind": "file",
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        except OSError as exc:
            errors.append(f"cannot hash {path}: {exc}")
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "hash",
        "entries": entries,
        "errors": errors,
    }


def _criterion_description(criterion: Mapping[str, Any]) -> str | None:
    for key in ("requirement", "description", "text", "label"):
        value = _nonempty_text(criterion.get(key))
        if value:
            return value
    return None


def _validate_contract(
    contract: Any,
) -> tuple[list[dict[str, Any]], list[Any], list[str], list[dict[str, Any]]]:
    """Validate the structural portion of a TaskContract.

    The returned criteria are the original criterion objects, while artifact
    declarations are retained for path/hash comparison.  A criterion's
    description is optional because the stable contract fields are id,
    required, and origin; if a description is supplied, it must not be empty.
    """

    errors: list[str] = []
    criteria: list[dict[str, Any]] = []
    artifact_specs: list[Any] = []
    if not isinstance(contract, dict):
        return [], [], ["contract must be a JSON object"], []

    raw_criteria = contract.get("criteria")
    if not isinstance(raw_criteria, list) or not raw_criteria:
        errors.append("contract.criteria must be a non-empty array")
    else:
        seen: set[str] = set()
        for index, raw in enumerate(raw_criteria):
            if not isinstance(raw, dict):
                errors.append(f"contract.criteria[{index}] must be an object")
                continue
            criterion_id = _nonempty_text(raw.get("id"))
            if criterion_id is None:
                errors.append(f"contract.criteria[{index}] is missing a non-empty id")
                continue
            if criterion_id in seen:
                errors.append(f"duplicate criterion id: {criterion_id}")
            seen.add(criterion_id)
            if not isinstance(raw.get("required"), bool):
                errors.append(
                    f"criterion {criterion_id} must set required to a JSON boolean"
                )
            if _nonempty_text(raw.get("origin")) is None:
                errors.append(f"criterion {criterion_id} is missing a non-empty origin")
            for key in ("requirement", "description", "text", "label"):
                if key in raw and _nonempty_text(raw.get(key)) is None:
                    errors.append(f"criterion {criterion_id} has an empty {key}")
            # Keep a copy so later output cannot mutate the input document.
            criteria.append(dict(raw))
        if criteria and not any(item.get("required") is True for item in criteria):
            errors.append(
                "contract.criteria must contain at least one required criterion"
            )

    if "requirements" in contract:
        requirements = contract["requirements"]
        if not isinstance(requirements, list) or not requirements:
            errors.append("contract.requirements must be a non-empty array when present")
        else:
            for index, requirement in enumerate(requirements):
                if isinstance(requirement, str):
                    if _nonempty_text(requirement) is None:
                        errors.append(f"contract.requirements[{index}] is empty")
                elif isinstance(requirement, dict):
                    if not any(
                        _nonempty_text(requirement.get(key))
                        for key in ("id", "requirement", "description", "text")
                    ):
                        errors.append(f"contract.requirements[{index}] is empty")
                else:
                    errors.append(f"contract.requirements[{index}] must be text or object")

    if "required_artifacts" in contract:
        raw_artifacts = contract["required_artifacts"]
        if not isinstance(raw_artifacts, list):
            errors.append("contract.required_artifacts must be an array")
        else:
            artifact_specs = raw_artifacts
    elif "artifacts" in contract:
        raw_artifacts = contract["artifacts"]
        if not isinstance(raw_artifacts, list):
            errors.append("contract.artifacts must be an array")
        else:
            artifact_specs = raw_artifacts

    for index, spec in enumerate(artifact_specs):
        if isinstance(spec, str):
            if _nonempty_text(spec) is None:
                errors.append(f"contract artifact {index} has an empty path")
        elif isinstance(spec, dict):
            if _nonempty_text(spec.get("path")) is None:
                errors.append(f"contract artifact {index} is missing a non-empty path")
            if "sha256" in spec and not _valid_hash(spec["sha256"]):
                errors.append(f"contract artifact {index} has an invalid sha256")
        else:
            errors.append(f"contract artifact {index} must be text or object")

    return criteria, artifact_specs, errors, [
        {
            "id": criterion.get("id"),
            "required": criterion.get("required"),
            "origin": criterion.get("origin"),
            "description": _criterion_description(criterion),
        }
        for criterion in criteria
    ]


def _path_record(
    raw: Any,
    base: Path,
    *,
    label: str,
) -> tuple[dict[str, Any] | None, str | None]:
    if isinstance(raw, str):
        path_value = raw
        metadata: dict[str, Any] = {}
    elif isinstance(raw, dict):
        metadata = dict(raw)
        path_value = raw.get("path")
    else:
        return None, f"{label} must be an object with a path"
    try:
        resolved = _absolute_path(path_value, base)
    except InputError as exc:
        return None, f"{label}: {exc}"
    if not resolved.is_file():
        return None, f"{label} is not a real file: {resolved}"
    try:
        digest = sha256_file(resolved)
        size = resolved.stat().st_size
    except OSError as exc:
        return None, f"{label} cannot be read: {resolved}: {exc}"
    expected_hash = metadata.get("sha256")
    if expected_hash is not None and not _valid_hash(expected_hash):
        return None, f"{label} has an invalid sha256"
    if expected_hash is not None and expected_hash.lower() != digest:
        return None, f"{label} sha256 mismatch: {resolved}"
    metadata["path"] = str(resolved)
    metadata.setdefault("kind", "file")
    metadata["sha256"] = digest
    metadata["size"] = size
    return metadata, None


def _contract_artifact_record(
    raw: Any, base: Path
) -> tuple[dict[str, Any] | None, str | None]:
    if isinstance(raw, str):
        spec: dict[str, Any] = {"path": raw}
    elif isinstance(raw, dict):
        spec = dict(raw)
    else:
        return None, "contract artifact is not text or object"
    try:
        path = _absolute_path(spec.get("path"), base)
    except InputError as exc:
        return None, f"contract artifact: {exc}"
    record = {"path": str(path)}
    if "sha256" in spec:
        record["sha256"] = spec["sha256"]
    return record, None


def _reason_value(result: Mapping[str, Any]) -> str | None:
    for key in ("applicabilityreason", "applicability_reason", "reason"):
        value = _nonempty_text(result.get(key))
        if value:
            return value
    return None


def _gate(
    contract: Any,
    report: Any,
    *,
    contract_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    criteria, contract_artifacts, contract_errors, criterion_summary = _validate_contract(
        contract
    )
    errors.extend(contract_errors)

    if not isinstance(report, dict):
        errors.append("delivery report must be a JSON object")
        report = {}

    raw_results = report.get("results")
    if not isinstance(raw_results, list):
        errors.append("delivery report.results must be an array")
        raw_results = []

    result_map: dict[str, dict[str, Any]] = {}
    for index, raw_result in enumerate(raw_results):
        if not isinstance(raw_result, dict):
            errors.append(f"delivery report.results[{index}] must be an object")
            continue
        criterion_id = _nonempty_text(raw_result.get("criterion_id"))
        if criterion_id is None:
            errors.append(f"delivery report.results[{index}] is missing criterion_id")
            continue
        if criterion_id in result_map:
            errors.append(f"duplicate result criterion_id: {criterion_id}")
            continue
        result_map[criterion_id] = dict(raw_result)

    criterion_ids = {
        criterion.get("id")
        for criterion in criteria
        if isinstance(criterion.get("id"), str)
    }
    for criterion_id in sorted(set(result_map) - criterion_ids):
        errors.append(f"result has unknown criterion_id: {criterion_id}")
    for criterion_id in sorted(criterion_ids - set(result_map)):
        errors.append(f"missing result for criterion_id: {criterion_id}")

    checked_results: list[dict[str, Any]] = []
    required_blockers: list[str] = []
    optional_failures: list[str] = []
    for criterion in criteria:
        criterion_id = criterion.get("id")
        required = criterion.get("required") is True
        raw_result = result_map.get(criterion_id)
        if raw_result is None:
            checked_results.append(
                {
                    "criterion_id": criterion_id,
                    "required": required,
                    "status": "NOT_TESTED",
                    "evidence": [],
                    "evidence_valid": False,
                }
            )
            if required:
                required_blockers.append(f"{criterion_id}: missing result")
            continue

        status = raw_result.get("status")
        if status not in VALID_STATUSES:
            errors.append(
                f"criterion {criterion_id} has invalid status; expected one of "
                f"{sorted(VALID_STATUSES)}"
            )
            status = "NOT_TESTED"
        raw_evidence = raw_result.get("evidence", [])
        if raw_evidence is None:
            raw_evidence = []
        if not isinstance(raw_evidence, list):
            errors.append(f"criterion {criterion_id}.evidence must be an array")
            raw_evidence = []
        evidence_records: list[dict[str, Any]] = []
        evidence_valid = True
        for evidence_index, raw_evidence_item in enumerate(raw_evidence):
            if not isinstance(raw_evidence_item, dict):
                errors.append(
                    f"criterion {criterion_id}.evidence[{evidence_index}] "
                    "must be an object with a path"
                )
                evidence_valid = False
                continue
            checked, evidence_error = _path_record(
                raw_evidence_item,
                report_path.parent,
                label=f"criterion {criterion_id}.evidence[{evidence_index}]",
            )
            if evidence_error:
                errors.append(evidence_error)
                evidence_valid = False
            elif checked is not None:
                evidence_records.append(checked)

        reason = _reason_value(raw_result)
        if status == "PASS" and not evidence_records:
            errors.append(f"criterion {criterion_id} PASS requires file evidence")
            evidence_valid = False
        if status == "NOT_APPLICABLE" and reason is None:
            errors.append(
                f"criterion {criterion_id} NOT_APPLICABLE requires "
                "applicabilityreason"
            )
            evidence_valid = False

        if required:
            if status in {"FAIL", "UNCERTAIN", "NOT_TESTED"}:
                required_blockers.append(f"{criterion_id}: {status}")
            elif status == "PASS" and (not evidence_records or not evidence_valid):
                required_blockers.append(f"{criterion_id}: PASS lacks valid evidence")
            elif status == "NOT_APPLICABLE" and reason is None:
                required_blockers.append(
                    f"{criterion_id}: NOT_APPLICABLE lacks applicabilityreason"
                )
        elif status in {"FAIL", "UNCERTAIN", "NOT_TESTED"}:
            optional_failures.append(f"{criterion_id}: {status}")

        checked_results.append(
            {
                "criterion_id": criterion_id,
                "required": required,
                "status": status,
                "evidence": evidence_records,
                "evidence_valid": evidence_valid,
                "applicabilityreason": reason,
            }
        )

    if optional_failures:
        warnings.append(
            "optional criteria did not pass and do not mask required criteria: "
            + ", ".join(optional_failures)
        )

    report_artifacts: list[dict[str, Any]] = []
    raw_artifacts = report.get("artifacts")
    if not isinstance(raw_artifacts, list):
        errors.append("delivery report.artifacts must be an array of real file paths")
        raw_artifacts = []
    if not raw_artifacts:
        errors.append("delivery report.artifacts must contain at least one real file")
    seen_artifacts: set[str] = set()
    for index, raw_artifact in enumerate(raw_artifacts):
        checked, artifact_error = _path_record(
            raw_artifact,
            report_path.parent,
            label=f"delivery report.artifacts[{index}]",
        )
        if artifact_error:
            errors.append(artifact_error)
            continue
        assert checked is not None
        if checked["path"] in seen_artifacts:
            errors.append(f"duplicate artifact path: {checked['path']}")
        seen_artifacts.add(checked["path"])
        report_artifacts.append(checked)

    expected_artifacts: list[dict[str, Any]] = []
    for index, raw_spec in enumerate(contract_artifacts):
        expected, expected_error = _contract_artifact_record(
            raw_spec, contract_path.parent
        )
        if expected_error:
            errors.append(f"contract.required_artifacts[{index}]: {expected_error}")
        elif expected is not None:
            expected_artifacts.append(expected)
    report_artifact_paths = {item["path"] for item in report_artifacts}
    for expected in expected_artifacts:
        expected_path = expected["path"]
        if expected_path not in report_artifact_paths:
            errors.append(f"missing required artifact: {expected_path}")
        expected_hash = expected.get("sha256")
        if expected_hash is not None:
            matching = next(
                (
                    item
                    for item in report_artifacts
                    if item["path"] == expected_path
                ),
                None,
            )
            if matching is not None and (
                not _valid_hash(expected_hash)
                or matching["sha256"].lower() != expected_hash.lower()
            ):
                errors.append(f"required artifact sha256 mismatch: {expected_path}")

    required_pass = sum(
        1
        for result in checked_results
        if result["required"]
        and result["status"] == "PASS"
        and result["evidence_valid"]
        and bool(result["evidence"])
    )
    required_not_applicable = sum(
        1
        for result in checked_results
        if result["required"]
        and result["status"] == "NOT_APPLICABLE"
        and bool(result.get("applicabilityreason"))
    )
    required_total = sum(1 for criterion in criteria if criterion.get("required") is True)
    if errors or required_blockers:
        status = INCOMPLETE
    else:
        status = READY

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "gate": STRUCTURAL_GATE,
        "structural_gate_only": True,
        "visual_quality_proven": False,
        "actual_reading_proven": False,
        "user_taste_status": "NOT_EVALUATED",
        "user_taste_note": (
            "User taste is not known by this structural gate; that is distinct "
            "from an untested or failed technical criterion."
        ),
        "contract": {
            "path": str(contract_path.resolve(strict=False)),
            "criteria_count": len(criteria),
            "criteria": criterion_summary,
        },
        "required": {
            "total": required_total,
            "pass": required_pass,
            "not_applicable": required_not_applicable,
            "blockers": required_blockers,
        },
        "criteria": checked_results,
        "artifacts": report_artifacts,
        "errors": errors,
        "warnings": warnings,
    }


def run_gate(
    contract_path: Path,
    report_path: Path,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Run the structural gate and optionally write its JSON receipt."""

    errors: list[str] = []
    try:
        contract = load_json(contract_path)
    except InputError as exc:
        contract = {}
        errors.append(str(exc))
    try:
        report = load_json(report_path)
    except InputError as exc:
        report = {}
        errors.append(str(exc))
    result = _gate(
        contract,
        report,
        contract_path=contract_path,
        report_path=report_path,
    )
    result["errors"] = errors + result["errors"]
    if result["errors"]:
        result["status"] = INCOMPLETE
    if out_path is not None:
        write_json(out_path, result)
    return result


def write_json(path: Path, value: Any) -> None:
    """Write a finite, deterministic JSON document atomically."""

    payload = json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    )
    if str(path) == "-":
        sys.stdout.write(payload + "\n")
        return
    path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _print_command_result(result: dict[str, Any]) -> int:
    sys.stdout.write(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    return 0 if not result.get("errors") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory files and gate TaskContract delivery evidence. "
            "The gate proves structure and file presence only."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("inventory", "List files, sizes, and SHA-256 hashes."),
        ("files", "List files and sizes without hashing."),
    ):
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.add_argument("paths", nargs="+", help="Files or directories.")

    hash_parser = subparsers.add_parser("hash", help="Hash files with SHA-256.")
    hash_parser.add_argument("paths", nargs="+", help="Files or directories.")

    gate_parser = subparsers.add_parser(
        "gate",
        help="Run the fail-closed structural delivery gate.",
    )
    gate_parser.add_argument("--contract", required=True, type=Path, help="TaskContract JSON.")
    gate_parser.add_argument("--report", required=True, type=Path, help="Delivery report JSON.")
    gate_parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output gate receipt JSON, or '-' for stdout.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "inventory":
        return _print_command_result(inventory_files(arguments.paths, include_hash=True))
    if arguments.command == "files":
        return _print_command_result(inventory_files(arguments.paths, include_hash=False))
    if arguments.command == "hash":
        return _print_command_result(hash_files(arguments.paths))
    if arguments.command == "gate":
        try:
            result = run_gate(arguments.contract, arguments.report, arguments.out)
        except (OSError, TypeError, ValueError) as exc:
            result = {
                "schema_version": SCHEMA_VERSION,
                "status": INCOMPLETE,
                "gate": STRUCTURAL_GATE,
                "structural_gate_only": True,
                "visual_quality_proven": False,
                "actual_reading_proven": False,
                "user_taste_status": "NOT_EVALUATED",
                "errors": [f"cannot write gate receipt: {exc}"],
                "warnings": [],
            }
            if str(arguments.out) == "-":
                sys.stdout.write(json.dumps(result, indent=2) + "\n")
        if result["status"] == READY:
            return 0
        return 1
    parser.error(f"unknown command: {arguments.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
