#!/usr/bin/env python3
"""Validate that one installed skill is self-contained and publishable.

The validator intentionally uses only the Python standard library.  It checks
package boundaries, metadata, links, helper references, source imports, and
obvious private/research scaffolding.  It does not judge prose style or claim
that Blender, a target runtime, or a visual critic has actually run.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from urllib.parse import unquote


SCHEMA_VERSION = "0.1"
SKIP_DIRS = frozenset(
    {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)
TEXT_SUFFIXES = frozenset(
    {
        ".cfg",
        ".ini",
        ".js",
        ".json",
        ".md",
        ".py",
        ".sh",
        ".toml",
        ".ts",
        ".txt",
        ".yaml",
        ".yml",
    }
)
HOST_MODULES = frozenset(
    {
        "addon_utils",
        "aud",
        "bgl",
        "blender",
        "bmesh",
        "blf",
        "bpy",
        "freestyle",
        "gpu",
        "idprop",
        "imbuf",
        "mathutils",
        "nodeitems_utils",
    }
)
RAW_RESEARCH_NAMES = frozenset(
    {
        "osint_report.md",
        "source_catalog.json",
        "source-catalog.json",
        "qa_sources.json",
        "qa-sources.json",
        "captures",
        "raw",
        "scrapes",
    }
)
RAW_RESEARCH_SUFFIXES = frozenset({".har", ".mhtml"})
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\n]+)\)")
HELPER_PATH_RE = re.compile(
    r"(?<![\w./-])((?:(?:\.\.?/)+)?(?:scripts|references|assets)/"
    r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)"
)
LOCAL_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:/Users/|/home/|/root/|/private/var/|"
    r"[A-Za-z]:[\\/]+Users[\\/]+)"
)
SECRET_PATTERNS = (
    re.compile(
        r"\b(?:sk-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9_-]{10,}|"
        r"github_pat_[A-Za-z0-9_-]{10,}|xox[baprs]-[A-Za-z0-9_-]{10,})\b"
    ),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{12,}"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)\s*"
        r"[:=]\s*['\"]?[A-Za-z0-9+/_.-]{8,}"
    ),
)
SCAFFOLD_RE = re.compile(r"\b(?:TODO|TBD|FIXME|IMPLEMENT_ME)\b")


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _error(code: str, message: str, path: Path | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    return item


def _read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _iter_package_files(root: Path) -> tuple[list[Path], list[dict[str, Any]]]:
    files: list[Path] = []
    errors: list[dict[str, Any]] = []
    try:
        candidates = sorted(root.rglob("*"), key=lambda item: str(item))
    except OSError as exc:
        return [], [_error("walk_failed", str(exc), root)]
    for path in candidates:
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        resolved = path.resolve(strict=False)
        if path.is_symlink() and not _within(resolved, root):
            errors.append(
                _error(
                    "external_symlink",
                    "symlink resolves outside the installed skill",
                    path,
                )
            )
            continue
        if path.is_file():
            files.append(path)
    return files, errors


def _frontmatter(skill_file: Path, text: str) -> tuple[dict[str, str], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, [
            _error(
                "missing_frontmatter",
                "SKILL.md must begin with a YAML frontmatter block",
                skill_file,
            )
        ]
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return {}, [
            _error(
                "unterminated_frontmatter",
                "frontmatter has no closing --- delimiter",
                skill_file,
            )
        ]
    metadata: dict[str, str] = {}
    for index, line in enumerate(lines[1:end], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", stripped)
        if not match:
            errors.append(
                _error(
                    "invalid_metadata",
                    f"frontmatter line {index} is not a simple key: value entry",
                    skill_file,
                )
            )
            continue
        key, raw_value = match.groups()
        raw_value = raw_value.strip()
        if (
            len(raw_value) >= 2
            and raw_value[0] == raw_value[-1]
            and raw_value[0] in {"'", '"'}
        ):
            raw_value = raw_value[1:-1]
        if key in metadata:
            errors.append(_error("duplicate_metadata", f"duplicate key: {key}", skill_file))
        metadata[key] = raw_value.strip()
    if not metadata.get("name"):
        errors.append(_error("missing_metadata_name", "metadata.name is required", skill_file))
    elif not re.fullmatch(r"[a-z0-9][a-z0-9-]*", metadata["name"]):
        errors.append(
            _error(
                "invalid_metadata_name",
                "metadata.name must use lowercase letters, digits, and hyphens",
                skill_file,
            )
        )
    if not metadata.get("description"):
        errors.append(
            _error("missing_metadata_description", "metadata.description is required", skill_file)
        )
    return metadata, errors


def _clean_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        # A Markdown title follows whitespace after the URL.  Paths in this
        # skill do not contain unescaped spaces, so the first token is enough.
        target = target.split()[0] if target.split() else ""
    target = unquote(target)
    target = target.split("#", 1)[0].split("?", 1)[0]
    return target


def _check_markdown_links(
    root: Path, markdown_files: Iterable[Path]
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    seen_helpers: set[tuple[Path, str]] = set()
    for markdown_file in markdown_files:
        text = _read_text(markdown_file)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for link_match in MARKDOWN_LINK_RE.finditer(line):
                target = _clean_link_target(link_match.group(1))
                if (
                    not target
                    or target.startswith("#")
                    or target.startswith("//")
                    or re.match(r"(?i)^(?:https?|mailto|data):", target)
                ):
                    continue
                destination = (markdown_file.parent / target).resolve(strict=False)
                if not _within(destination, root):
                    errors.append(
                        _error(
                            "link_outside_skill",
                            f"relative Markdown link escapes the installed skill: {target}",
                            markdown_file,
                        )
                    )
                elif not destination.exists():
                    errors.append(
                        _error(
                            "missing_markdown_link",
                            f"relative Markdown link does not exist: {target} "
                            f"(line {line_number})",
                            markdown_file,
                        )
                    )
            for helper_match in HELPER_PATH_RE.finditer(line):
                helper = helper_match.group(1).rstrip(".,;:")
                key = (markdown_file, helper)
                if key in seen_helpers:
                    continue
                seen_helpers.add(key)
                # Markdown links have document-relative semantics.  A bare
                # helper path in recipe prose is a package-root path, so a
                # nested reference can name scripts/foo.py or
                # references/bar.md without accidentally looking under
                # references/nested/.  Explicit ./ or ../ paths remain
                # document-relative and are still checked for escape.
                if helper.startswith("./") or helper.startswith("../"):
                    destination = (markdown_file.parent / helper).resolve(strict=False)
                else:
                    destination = (root / helper).resolve(strict=False)
                if not _within(destination, root):
                    errors.append(
                        _error(
                            "helper_outside_skill",
                            f"helper path escapes the installed skill: {helper}",
                            markdown_file,
                        )
                    )
                elif not destination.exists():
                    errors.append(
                        _error(
                            "missing_helper",
                            f"referenced helper path does not exist: {helper}",
                            markdown_file,
                        )
                    )
    return errors


def _check_text_policy(
    root: Path, files: Iterable[Path]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for path in files:
        relative_parts = {part.lower() for part in path.relative_to(root).parts}
        lower_name = path.name.lower()
        if lower_name in RAW_RESEARCH_NAMES or relative_parts & RAW_RESEARCH_NAMES:
            errors.append(
                _error(
                    "raw_research_bundle",
                    "raw OSINT/research capture is not release content",
                    path,
                )
            )
        if path.suffix.lower() in RAW_RESEARCH_SUFFIXES:
            errors.append(
                _error(
                    "raw_capture",
                    "raw browser/archive capture is not release content",
                    path,
                )
            )
        text = _read_text(path)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if LOCAL_PATH_RE.search(line):
                errors.append(
                    _error(
                        "private_local_path",
                        f"private or machine-specific path at line {line_number}",
                        path,
                    )
                )
            if SCAFFOLD_RE.search(line):
                errors.append(
                    _error(
                        "unfinished_scaffold",
                        f"unfinished scaffold marker at line {line_number}",
                        path,
                    )
                )
            for pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    errors.append(
                        _error(
                            "secret_like_value",
                            f"secret-like value at line {line_number}",
                            path,
                        )
                    )
                    break
    return errors, warnings


def _module_name(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.Import):
        return node.names[0].name.split(".", 1)[0]
    return (node.module or "").split(".", 1)[0]


def _check_python_sources(
    root: Path, python_files: Iterable[Path]
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    stdlib_modules = set(getattr(sys, "stdlib_module_names", ()))
    for path in python_files:
        text = _read_text(path)
        if text is None:
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            errors.append(
                _error(
                    "python_syntax",
                    f"cannot parse Python source: {exc.msg} at line {exc.lineno}",
                    path,
                )
            )
            continue
        relative_parts = set(path.relative_to(root).parts)
        # Tests may intentionally exercise an optional image library or import
        # a local helper by module name.  They are checked for syntax and
        # boundary escapes, but their test-only dependencies are not runtime
        # dependencies of the installed skill.
        test_source = "tests" in relative_parts
        optional_import_nodes: set[int] = set()
        for try_node in ast.walk(tree):
            if not isinstance(try_node, ast.Try):
                continue
            catches_import_error = any(
                handler.type is None
                or (
                    isinstance(handler.type, ast.Name)
                    and handler.type.id in {"ImportError", "ModuleNotFoundError"}
                )
                or (
                    isinstance(handler.type, ast.Tuple)
                    and any(
                        isinstance(item, ast.Name)
                        and item.id in {"ImportError", "ModuleNotFoundError"}
                        for item in handler.type.elts
                    )
                )
                for handler in try_node.handlers
            )
            if catches_import_error:
                optional_import_nodes.update(
                    id(child)
                    for child in ast.walk(try_node)
                    if isinstance(child, (ast.Import, ast.ImportFrom))
                )
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import) and not node.names:
                    continue
                module = _module_name(node)
                if isinstance(node, ast.ImportFrom) and node.level:
                    base = path.parent
                    for _ in range(max(0, node.level - 1)):
                        base = base.parent
                    if not _within(base.resolve(strict=False), root):
                        errors.append(
                            _error(
                                "relative_import_outside_skill",
                                "relative Python import escapes the installed skill",
                                path,
                            )
                        )
                    continue
                if (
                    module
                    and module not in stdlib_modules
                    and module not in HOST_MODULES
                    and not test_source
                    and id(node) not in optional_import_nodes
                ):
                    errors.append(
                        _error(
                            "undeclared_python_dependency",
                            f"Python import is not standard-library or Blender-hosted: {module}",
                            path,
                        )
                    )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"append", "insert"}:
                    for argument in node.args:
                        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                            if "../" in argument.value or "..\\" in argument.value:
                                errors.append(
                                    _error(
                                        "path_injection",
                                        "runtime path mutation points outside the skill",
                                        path,
                                    )
                                )
    return errors


def validate_package(skill_root: Path) -> dict[str, Any]:
    root = skill_root.resolve(strict=False)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not root.is_dir():
        errors.append(_error("missing_skill_root", "skill root is not a directory", root))
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "skill_root": str(root),
            "metadata": {},
            "checks": {"root": "FAIL"},
            "errors": errors,
            "warnings": warnings,
        }

    files, walk_errors = _iter_package_files(root)
    errors.extend(walk_errors)
    skill_file = root / "SKILL.md"
    if not skill_file.is_file():
        errors.append(_error("missing_skill_entrypoint", "SKILL.md is required", skill_file))
        metadata: dict[str, str] = {}
    else:
        skill_text = _read_text(skill_file)
        if skill_text is None:
            metadata = {}
            errors.append(_error("unreadable_skill_entrypoint", "SKILL.md is not UTF-8 text", skill_file))
        else:
            metadata, metadata_errors = _frontmatter(skill_file, skill_text)
            errors.extend(metadata_errors)
            if metadata.get("name") and metadata["name"] != root.name:
                warnings.append(
                    _error(
                        "metadata_name_directory_difference",
                        f"metadata.name {metadata['name']!r} differs from directory {root.name!r}",
                        skill_file,
                    )
                )

    markdown_files = [path for path in files if path.suffix.lower() == ".md"]
    errors.extend(_check_markdown_links(root, markdown_files))
    text_errors, text_warnings = _check_text_policy(root, files)
    errors.extend(text_errors)
    warnings.extend(text_warnings)
    python_files = [path for path in files if path.suffix.lower() == ".py"]
    errors.extend(_check_python_sources(root, python_files))

    checks = {
        "root": "PASS",
        "entrypoint": "PASS" if skill_file.is_file() else "FAIL",
        "metadata": "PASS"
        if skill_file.is_file()
        and not any(
            item["code"].startswith("missing_metadata")
            or item["code"].startswith("invalid_metadata")
            or item["code"] in {"duplicate_metadata", "missing_frontmatter", "unterminated_frontmatter"}
            for item in errors
        )
        else "FAIL",
        "relative_links_and_helpers": "PASS"
        if not any(
            item["code"]
            in {
                "link_outside_skill",
                "missing_markdown_link",
                "helper_outside_skill",
                "missing_helper",
            }
            for item in errors
        )
        else "FAIL",
        "source_dependencies": "PASS"
        if not any(
            item["code"]
            in {"python_syntax", "undeclared_python_dependency", "relative_import_outside_skill", "path_injection"}
            for item in errors
        )
        else "FAIL",
        "release_content": "PASS"
        if not any(
            item["code"]
            in {
                "private_local_path",
                "secret_like_value",
                "raw_research_bundle",
                "raw_capture",
                "unfinished_scaffold",
                "external_symlink",
            }
            for item in errors
        )
        else "FAIL",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not errors else "FAIL",
        "skill_root": str(root),
        "metadata": metadata,
        "files_checked": len(files),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def _write_json(path: Path, value: Any) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
    if str(path) == "-":
        sys.stdout.write(payload + "\n")
        return
    path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate one installed skill without external Python dependencies."
    )
    parser.add_argument("skill_root", type=Path, help="Installed skill directory.")
    parser.add_argument("--out", type=Path, help="Write the JSON receipt to this path or '-'.")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    result = validate_package(arguments.skill_root)
    if arguments.out is None:
        sys.stdout.write(
            json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            + "\n"
        )
    else:
        try:
            _write_json(arguments.out, result)
        except OSError as exc:
            sys.stderr.write(f"cannot write validation receipt: {exc}\n")
            return 2
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
