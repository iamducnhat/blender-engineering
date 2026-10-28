#!/usr/bin/env python3
"""Exercise GitHub-style skill installation in isolated temporary homes.

The test intentionally uses the public ``npx skills`` client rather than
reimplementing its discovery rules. It always builds the local public archive
for the expected hash tree, then installs one skill at a time for Codex and
Claude Code. By default the extracted archive is also the CLI source; ``--source``
can replace only the CLI source with a GitHub repository or ref for a
post-publish check. No user's normal HOME, agent skill directory, npm cache, or
configuration file is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable


CLI_PACKAGE = "skills@1.7.4"
CLI_VERSION = "1.7.4"
EXPECTED_SKILLS = (
    "blender-engineering-animation",
    "blender-engineering-modeling",
)
AGENTS = ("codex", "claude-code")


class InstallTestError(RuntimeError):
    """Raised when the isolated installer contract is not met."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_tree(root: Path) -> dict[str, str]:
    """Hash regular files below a skill directory, following its root link."""

    if not root.exists():
        raise InstallTestError(f"installed skill path does not exist: {root}")
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise InstallTestError(f"installed skill path is not a directory: {root}")
    result: dict[str, str] = {}
    for path in sorted(resolved_root.rglob("*")):
        if path.is_symlink():
            target = path.resolve()
            if target.is_dir():
                raise InstallTestError(f"nested directory symlink is not portable: {path}")
            if not target.is_file():
                raise InstallTestError(f"broken installed symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(resolved_root).as_posix()
        result[relative] = _sha256(path.read_bytes())
    return result


def _source_files(root: Path) -> dict[str, str]:
    return _hash_tree(root)


def _isolated_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "NPM_CONFIG_CACHE": str(home / ".npm"),
            "NPM_CONFIG_USERCONFIG": str(home / ".npmrc"),
            "NPM_CONFIG_PREFIX": str(home / ".npm-global"),
            "NPM_CONFIG_UPDATE_NOTIFIER": "false",
            "NPM_CONFIG_FUND": "false",
            "DISABLE_TELEMETRY": "1",
            "DO_NOT_TRACK": "1",
        }
    )
    return env


def _run(command: list[str], *, cwd: Path, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        details = "\n".join(
            part.strip()
            for part in (result.stdout, result.stderr)
            if part and part.strip()
        )
        raise InstallTestError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{details[-4000:]}"
        )
    return result


def _extract_archive(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as archive:
        broken = archive.testzip()
        if broken is not None:
            raise InstallTestError(f"release archive failed CRC readback: {broken}")
        destination_root = destination.resolve()
        for member in archive.infolist():
            relative = PurePosixPath(member.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise InstallTestError(f"unsafe archive member: {member.filename}")
            target = (destination / Path(*relative.parts)).resolve()
            if os.path.commonpath((str(destination_root), str(target))) != str(destination_root):
                raise InstallTestError(f"archive member escapes extraction root: {member.filename}")
        archive.extractall(destination)


def _candidate_paths(project: Path, home: Path, skill_name: str) -> list[Path]:
    candidates: list[Path] = []
    for base in (project, home):
        for container in (
            Path(".agents/skills"),
            Path(".codex/skills"),
            Path(".claude/skills"),
        ):
            candidate = base / container / skill_name
            if candidate.exists() or candidate.is_symlink():
                candidates.append(candidate)
    return candidates


def _validate_install(
    *,
    source_skill: Path,
    candidates: Iterable[Path],
    scenario_root: Path,
    require_symlink: bool,
) -> dict[str, object]:
    expected = _source_files(source_skill)
    if not expected:
        raise InstallTestError(f"source skill is empty: {source_skill}")
    candidates = list(candidates)
    if not candidates:
        raise InstallTestError(f"no installed candidate found for {source_skill.name}")

    candidate_records: list[dict[str, object]] = []
    saw_symlink = False
    for candidate_index, candidate in enumerate(candidates):
        is_root_symlink = candidate.is_symlink()
        saw_symlink = saw_symlink or is_root_symlink
        resolved = candidate.resolve()
        actual = _hash_tree(candidate)
        if actual != expected:
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            changed = sorted(
                path for path in set(expected) & set(actual) if expected[path] != actual[path]
            )
            raise InstallTestError(
                f"installed hash mismatch for {candidate}; missing={missing}, extra={extra}, changed={changed}"
            )

        portable_copy = scenario_root / "portable" / f"{candidate_index:02d}-{candidate.name}"
        portable_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(resolved, portable_copy, symlinks=False)
        portable_hashes = _hash_tree(portable_copy)
        if portable_hashes != expected:
            raise InstallTestError(f"reference/hash portability failed after copying {candidate}")

        candidate_records.append(
            {
                "path": candidate.relative_to(scenario_root).as_posix()
                if candidate.is_relative_to(scenario_root)
                else str(candidate),
                "resolved_path": str(resolved),
                "root_is_symlink": is_root_symlink,
                "file_count": len(actual),
                "reference_files_checked": sum(
                    1 for path in expected if path.startswith(("references/", "scripts/", "assets/"))
                ),
            }
        )

    if require_symlink and not saw_symlink:
        raise InstallTestError(
            "default multi-agent installation produced no symlink; inspect the CLI behavior before changing this test"
        )
    return {
        "candidate_count": len(candidate_records),
        "symlink_observed": saw_symlink,
        "candidates": candidate_records,
        "source_file_count": len(expected),
    }


def _build_source_archive(repo_root: Path, temp_root: Path) -> tuple[Path, Path, dict[str, object]]:
    tools_dir = repo_root / "tools"
    sys.path.insert(0, str(tools_dir))
    try:
        import package_release
    finally:
        sys.path.pop(0)
    archive_path = temp_root / "blender-engineering-test.zip"
    receipt = package_release.build_package(repo_root, archive_path, "0.1.0-test")
    source_root = temp_root / "source"
    _extract_archive(archive_path, source_root)
    return archive_path, source_root, receipt


def run_install_test(
    *,
    timeout: int = 180,
    keep_temp: bool = False,
    source: str | None = None,
) -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[1]
    temp_root = Path(tempfile.mkdtemp(prefix="blender-engineering-install-test-"))
    try:
        archive_path, source_root, package_receipt = _build_source_archive(repo_root, temp_root)
        source_ref = source if source is not None else str(source_root)
        if not source_ref.strip():
            raise InstallTestError("--source must not be empty")
        home_probe = temp_root / "version-home"
        home_probe.mkdir()
        version_env = _isolated_env(home_probe)
        npx = shutil.which("npx")
        if npx is None:
            raise InstallTestError("npx is not available on PATH")
        version_result = _run(
            [npx, "--yes", CLI_PACKAGE, "--version"],
            cwd=temp_root,
            env=version_env,
            timeout=timeout,
        )
        observed_version = version_result.stdout.strip().splitlines()[-1] if version_result.stdout.strip() else ""
        if observed_version != CLI_VERSION:
            raise InstallTestError(
                f"pinned CLI version mismatch: expected {CLI_VERSION}, observed {observed_version!r}"
            )

        list_result = _run(
            [npx, "--yes", CLI_PACKAGE, "add", source_ref, "--list"],
            cwd=temp_root,
            env=version_env,
            timeout=timeout,
        )
        listed = list_result.stdout + list_result.stderr
        for skill_name in EXPECTED_SKILLS:
            if skill_name not in listed:
                raise InstallTestError(f"source discovery did not list {skill_name}: {listed[-4000:]}")

        scenarios: list[dict[str, object]] = []
        for skill_name in EXPECTED_SKILLS:
            source_skill = source_root / "skills" / skill_name
            for mode in ("copy", "default"):
                scenario_root = temp_root / f"{skill_name}-{mode}"
                home = scenario_root / "home"
                project = scenario_root / "project"
                home.mkdir(parents=True)
                project.mkdir(parents=True)
                # The CLI uses the nearest project when it is present. This
                # marker remains inside the temporary test project.
                (project / ".git").mkdir()
                env = _isolated_env(home)
                command = [
                    npx,
                    "--yes",
                    CLI_PACKAGE,
                    "add",
                    source_ref,
                    "--skill",
                    skill_name,
                    "--agent",
                    "codex",
                    "claude-code",
                ]
                if mode == "copy":
                    command.append("--copy")
                command.append("-y")
                install_result = _run(command, cwd=project, env=env, timeout=timeout)
                candidates = _candidate_paths(project, home, skill_name)
                validation = _validate_install(
                    source_skill=source_skill,
                    candidates=candidates,
                    scenario_root=scenario_root,
                    require_symlink=mode == "default",
                )
                scenarios.append(
                    {
                        "skill": skill_name,
                        "mode": mode,
                        "agents": list(AGENTS),
                        "install_output_tail": install_result.stdout[-1000:],
                        **validation,
                    }
                )

        result = {
            "cli_package": CLI_PACKAGE,
            "cli_version": observed_version,
            "telemetry_disabled": True,
            "source": source_ref,
            "source_layout": package_receipt.get("source_layout"),
            "archive_sha256": package_receipt["archive"]["sha256"],
            "source_discovery": {
                "skills": list(EXPECTED_SKILLS),
                "list_command_passed": True,
            },
            "scenarios": scenarios,
        }
        if keep_temp:
            result["temporary_root"] = str(temp_root)
        return result
    finally:
        if not keep_temp:
            shutil.rmtree(temp_root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=180, help="timeout per npx command in seconds")
    parser.add_argument("--keep-temp", action="store_true", help="retain the isolated test directory for inspection")
    parser.add_argument(
        "--source",
        help=(
            "source passed as one argv value to npx skills (for example "
            "iamducnhat/blender-engineering@v0.1.0); defaults to the extracted local archive"
        ),
    )
    parser.add_argument("--report", type=Path, help="optional JSON report path")
    args = parser.parse_args(argv)
    try:
        result = run_install_test(timeout=args.timeout, keep_temp=args.keep_temp, source=args.source)
    except (OSError, subprocess.SubprocessError, InstallTestError, zipfile.BadZipFile) as exc:
        print(f"isolated install test failed: {exc}", file=sys.stderr)
        return 1
    encoded = json.dumps(result, indent=2, ensure_ascii=False)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
