#!/usr/bin/env python3
"""Build a small, deterministic public Blender Engineering package archive.

The repository contains research and investigation material beside the public
skills. The authoring checkout may use plugin/skills while the public checkout
may use skills/ at its root. This tool uses an explicit source map so either
layout is normalized without importing unrelated research. It also reads the
archive back and writes a hash receipt. The receipt is an integrity record; it
is not a Blender quality claim.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


EXPECTED_SKILLS = (
    "blender-engineering-animation",
    "blender-engineering-modeling",
)
PACKAGE_VERSION = "0.1.0"

_EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "__pypackages__",
}
_EXCLUDED_SUFFIXES = {
    ".onnx",
    ".safetensors",
    ".ckpt",
    ".pt",
    ".pth",
    ".bin",
    ".pkl",
    ".pem",
    ".key",
}
_EXCLUDED_COMPONENTS = {
    "captures",
    "investigation",
    "private",
    "raw",
    "secrets",
    "snapshots",
    "weights",
}
_EXCLUDED_NAME_RE = re.compile(r"(?:^|[._-])(secret|token|credential|password)(?:$|[._-])", re.I)


class PackagingError(RuntimeError):
    """Raised when the public package boundary is not safe to build."""


@dataclass(frozen=True)
class PackageFile:
    source: Path
    archive_name: PurePosixPath


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalise_archive_name(name: str) -> PurePosixPath:
    candidate = PurePosixPath(name)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PackagingError(f"unsafe archive path: {name}")
    return candidate


def _should_exclude(path: Path, *, relative_parts: Iterable[str] | None = None) -> bool:
    # Do not inspect the absolute path here: macOS temporary directories live
    # below /private, which is a valid filesystem location rather than a
    # package-private marker. Callers pass path components relative to the
    # selected package source.
    parts = {part.lower() for part in (relative_parts if relative_parts is not None else (path.name,))}
    if parts & {name.lower() for name in _EXCLUDED_COMPONENTS}:
        return True
    if path.name.startswith(".") and path.name in {".env", ".env.local"}:
        return True
    if _EXCLUDED_NAME_RE.search(path.name):
        return True
    return path.suffix.lower() in _EXCLUDED_SUFFIXES


def _iter_tree(source: Path, archive_prefix: str) -> Iterable[PackageFile]:
    if not source.is_dir():
        raise PackagingError(f"required package directory is missing: {source}")
    prefix = _normalise_archive_name(archive_prefix)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in _EXCLUDED_DIRECTORY_NAMES for part in relative.parts):
            continue
        if path.is_symlink():
            raise PackagingError(f"symlink is not portable in package input: {path}")
        if not path.is_file() or _should_exclude(path, relative_parts=relative.parts):
            continue
        archive_name = _normalise_archive_name(str(prefix / PurePosixPath(relative.as_posix())))
        yield PackageFile(path, archive_name)


def _add_file(files: list[PackageFile], source: Path, archive_name: str, *, required: bool = True) -> None:
    if not source.exists():
        if required:
            raise PackagingError(f"required package file is missing: {source}")
        return
    if source.is_symlink():
        raise PackagingError(f"symlink is not portable in package input: {source}")
    if not source.is_file():
        raise PackagingError(f"package input is not a file: {source}")
    if _should_exclude(source, relative_parts=(source.name,)):
        raise PackagingError(f"package input is excluded by the public boundary: {source}")
    files.append(PackageFile(source, _normalise_archive_name(archive_name)))


def _add_tree(files: list[PackageFile], source: Path, archive_prefix: str, *, required: bool = False) -> None:
    if not source.exists():
        if required:
            raise PackagingError(f"required package directory is missing: {source}")
        return
    files.extend(_iter_tree(source, archive_prefix))


def _frontmatter_value(frontmatter: list[str], key: str) -> str | None:
    prefix = f"{key}:"
    for line in frontmatter:
        if not line.startswith(prefix):
            continue
        raw = line[len(prefix) :].strip()
        if not raw:
            return None
        try:
            if raw[0] in {"'", '"'}:
                value = ast.literal_eval(raw)
            else:
                value = raw
        except (SyntaxError, ValueError):
            value = raw.strip("\"'")
        return value if isinstance(value, str) else None
    return None


def _validate_skill_source(skill_root: Path) -> None:
    if not skill_root.is_dir():
        raise PackagingError(f"skill directory is missing: {skill_root}")
    skill_dirs = sorted(path.name for path in skill_root.iterdir() if path.is_dir() and not path.name.startswith("."))
    if tuple(skill_dirs) != tuple(sorted(EXPECTED_SKILLS)):
        raise PackagingError(
            "public package must contain exactly the two expected skills; "
            f"found {skill_dirs!r}"
        )
    for skill_name in EXPECTED_SKILLS:
        entrypoint = skill_root / skill_name / "SKILL.md"
        if not entrypoint.is_file():
            raise PackagingError(f"missing SKILL.md for {skill_name}: {entrypoint}")
        lines = entrypoint.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            raise PackagingError(f"{entrypoint} must start with YAML frontmatter")
        try:
            end = lines.index("---", 1)
        except ValueError as exc:
            raise PackagingError(f"{entrypoint} has unterminated frontmatter") from exc
        name = _frontmatter_value(lines[1:end], "name")
        description = _frontmatter_value(lines[1:end], "description")
        if name != skill_name or not description:
            raise PackagingError(
                f"{entrypoint} must declare name={skill_name!r} and a non-empty description"
            )


def _select_skill_layout(repo_root: Path) -> tuple[str, Path]:
    """Select the current authoring layout without mixing skill copies.

    During development the package lives under ``plugin/skills``. The public
    repository may normalize that directory to ``skills`` at its root. If both
    are present, validate both and use the normalized root as authoritative;
    silently merging divergent skill copies would make release contents
    ambiguous.
    """

    root_skills = repo_root / "skills"
    plugin_skills = repo_root / "plugin" / "skills"
    if root_skills.is_dir():
        _validate_skill_source(root_skills)
        if plugin_skills.is_dir():
            _validate_skill_source(plugin_skills)
        return "root", root_skills
    if plugin_skills.is_dir():
        _validate_skill_source(plugin_skills)
        return "plugin", plugin_skills
    raise PackagingError(
        "no supported skill layout found; expected skills/ or plugin/skills/"
    )


def _preferred_source(layout: str, repo_root: Path, relative: str) -> Path | None:
    """Return a public file/tree source for the selected layout."""

    root_path = repo_root / relative
    plugin_path = repo_root / "plugin" / relative
    candidates = (root_path, plugin_path) if layout == "root" else (plugin_path, root_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def collect_package_files(repo_root: Path) -> list[PackageFile]:
    """Return the explicit public source map in deterministic order."""

    layout, skill_root = _select_skill_layout(repo_root)
    plugin_root = repo_root / "plugin"

    files: list[PackageFile] = []
    _add_tree(files, skill_root, "skills", required=True)
    readme = _preferred_source(layout, repo_root, "README.md")
    agents = _preferred_source(layout, repo_root, "AGENTS.md")
    if readme is None:
        raise PackagingError("public package README.md is missing")
    if agents is None:
        raise PackagingError("public package AGENTS.md is missing")
    _add_file(files, readme, "README.md")
    _add_file(files, agents, "AGENTS.md")
    _add_file(files, repo_root / "LICENSE", "LICENSE")

    # Docs, validation, and tests follow the selected layout. The tool trees
    # are merged because the current authoring layout keeps the skill validator
    # under plugin/tools while the release helpers live at repository root.
    # Identical collisions are deduplicated below; divergent files fail closed.
    for directory_name in ("docs", "validation", "tests"):
        source = _preferred_source(layout, repo_root, directory_name)
        if source is not None:
            _add_tree(files, source, directory_name)
    tool_sources = (
        (repo_root / "tools", plugin_root / "tools")
        if layout == "root"
        else (plugin_root / "tools", repo_root / "tools")
    )
    for tool_source in tool_sources:
        _add_tree(files, tool_source, "tools")
    _add_file(files, repo_root / "tools" / "package_release.py", "tools/package_release.py")
    _add_file(files, repo_root / "tools" / "test_install.py", "tools/test_install.py")

    # These are repository metadata needed by the normalized public package.
    # They are explicit files rather than a broad .github/. root so unrelated
    # workflows, local configuration, or private automation cannot leak in.
    _add_file(files, repo_root / ".github" / "workflows" / "validate.yml", ".github/workflows/validate.yml")
    _add_file(files, repo_root / ".gitignore", ".gitignore")
    _add_file(files, repo_root / "requirements-dev.txt", "requirements-dev.txt")
    _add_file(files, repo_root / "pyproject.toml", "pyproject.toml", required=False)

    by_name: dict[PurePosixPath, PackageFile] = {}
    for package_file in files:
        if package_file.archive_name in by_name:
            other = by_name[package_file.archive_name]
            if other.source.read_bytes() == package_file.source.read_bytes():
                continue
            raise PackagingError(
                f"archive path collision: {other.source} and {package_file.source} "
                f"both map to {package_file.archive_name}"
            )
        by_name[package_file.archive_name] = package_file
    return [by_name[name] for name in sorted(by_name, key=str)]


def _write_archive(output: Path, files: list[PackageFile]) -> list[dict[str, object]]:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    members: list[dict[str, object]] = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for package_file in files:
            data = package_file.source.read_bytes()
            name = package_file.archive_name.as_posix()
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
            members.append(
                {
                    "path": name,
                    "size_bytes": len(data),
                    "sha256": _sha256(data),
                }
            )
    return members


def _readback(output: Path, members: list[dict[str, object]]) -> None:
    expected = {str(member["path"]): member for member in members}
    with zipfile.ZipFile(output, "r") as archive:
        broken = archive.testzip()
        if broken is not None:
            raise PackagingError(f"archive CRC/readback failure at {broken}")
        actual_names = set(archive.namelist())
        if actual_names != set(expected):
            raise PackagingError(
                f"archive member set changed during write: expected {len(expected)}, got {len(actual_names)}"
            )
        for name, member in expected.items():
            data = archive.read(name)
            if len(data) != int(member["size_bytes"]):
                raise PackagingError(f"archive size readback mismatch for {name}")
            if _sha256(data) != str(member["sha256"]):
                raise PackagingError(f"archive hash readback mismatch for {name}")


def build_package(repo_root: Path, output: Path, version: str = PACKAGE_VERSION) -> dict[str, object]:
    source_layout, _ = _select_skill_layout(repo_root)
    files = collect_package_files(repo_root)
    members = _write_archive(output, files)
    _readback(output, members)
    archive_sha256 = _sha256(output.read_bytes())
    receipt = {
        "schema_version": "1",
        "package": "blender-engineering",
        "package_version": version,
        "source_layout": source_layout,
        "archive": {
            "path": output.name,
            "size_bytes": output.stat().st_size,
            "sha256": archive_sha256,
        },
        "members": members,
        "readback": {
            "zip_testzip": None,
            "member_hashes_verified": True,
            "member_count": len(members),
        },
        "quality": {
            "quality_certified": False,
            "note": "Packaging integrity only; no Blender modeling or animation quality claim.",
        },
        "excluded_from_archive": [
            "investigation/",
            "raw browser captures and private research material",
            "model weights, caches, secrets, and generated delivery archives",
        ],
    }
    receipt_path = output.with_suffix(".receipt.json")
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/blender-engineering-v0.1.0.zip"),
        help="archive path (default: dist/blender-engineering-v0.1.0.zip)",
    )
    parser.add_argument("--version", default=PACKAGE_VERSION, help="package version written to the receipt")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else Path.cwd() / args.output
    try:
        receipt = build_package(repo_root, output, args.version)
    except (OSError, PackagingError, zipfile.BadZipFile) as exc:
        print(f"package release failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
