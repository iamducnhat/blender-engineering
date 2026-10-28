"""Check the published layout, resource links, and release reproducibility."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit
import zipfile


REPO_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "tools" / "package_release.py").is_file()
)
SPEC = importlib.util.spec_from_file_location(
    "be_release_structure", REPO_ROOT / "tools" / "package_release.py"
)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)


class ReleaseStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.archive = self.directory / "release.zip"
        self.receipt = release.build_package(REPO_ROOT, self.archive, "0.1.0-test")

    def test_public_boundary_and_member_readback(self) -> None:
        with zipfile.ZipFile(self.archive) as archive:
            self.assertIsNone(archive.testzip())
            names = set(archive.namelist())
            self.assertIn(".github/workflows/validate.yml", names)
            self.assertIn("requirements-dev.txt", names)
            self.assertIn("tools/package_release.py", names)
            self.assertIn("tools/test_install.py", names)
            for skill in release.EXPECTED_SKILLS:
                self.assertIn(f"skills/{skill}/SKILL.md", names)
                self.assertIn(f"skills/{skill}/references/research-playbook.md", names)
            for name in names:
                components = set(Path(name).parts)
                self.assertFalse(
                    components & {"plugin", "investigation", "captures", "private", "raw", "__pycache__"},
                    name,
                )
                self.assertFalse(name.startswith("/"), name)
                self.assertNotIn("..", Path(name).parts)
                self.assertGreater(len(archive.read(name)), 0, name)
        self.assertFalse(self.receipt["quality"]["quality_certified"])

    def test_extracted_public_checkout_rebuilds_identical_archive(self) -> None:
        extracted = self.directory / "public"
        with zipfile.ZipFile(self.archive) as archive:
            archive.extractall(extracted)
        second = self.directory / "rebuilt.zip"
        receipt = release.build_package(extracted, second, "0.1.0-test")
        self.assertEqual(receipt["source_layout"], "root")
        self.assertEqual(
            hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            hashlib.sha256(second.read_bytes()).hexdigest(),
        )

    def test_markdown_resource_links_exist_in_published_layout(self) -> None:
        failures = []
        with zipfile.ZipFile(self.archive) as archive:
            names = set(archive.namelist())
            root = self.directory / "links"
            archive.extractall(root)
            for name in sorted(names):
                if not name.endswith(".md"):
                    continue
                body = archive.read(name).decode("utf-8")
                for match in re.finditer(r"!?\[[^\]]*\]\(([^)\n]+)\)", body):
                    target = match.group(1).strip()
                    if target.startswith("<"):
                        target = target[1 : target.index(">")]
                    else:
                        target = target.split(' "', 1)[0]
                    parsed = urlsplit(target)
                    if parsed.scheme or parsed.netloc or not parsed.path:
                        continue
                    resolved = (root / name).parent / unquote(parsed.path)
                    if not resolved.resolve().is_relative_to(root.resolve()):
                        failures.append(f"{name}: link escapes package: {target}")
                    elif not resolved.exists():
                        failures.append(f"{name}: missing link target: {target}")
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
