"""Guards for public-facing RankedDojo branding.

These tests protect against regressions of two kinds:

- the public product name (`RankedDojo`, the `rankeddojo` CLI command, the
  `RankedDojo.exe` build) disappearing from user-facing surfaces (README,
  public example packs, public UI strings);
- the internal/technical identity (`rankeddojo` package, `rankeddojo.main`
  entry point, `APP_DIR_NAME`) being accidentally renamed.

They intentionally avoid fragile global occurrence counts: each check targets
a specific, known file/string rather than "no leftover old name anywhere".
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "rankeddojo"


class ReadmeBrandingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_readme_presents_rankeddojo_as_the_app_name(self) -> None:
        self.assertTrue(self.readme.startswith("# RankedDojo"))

    def test_readme_prioritizes_the_public_rankeddojo_command(self) -> None:
        # The public command/executable must be introduced before the
        # internal `python -m rankeddojo.main` dev path.
        public_pos = self.readme.index("rankeddojo")
        internal_pos = self.readme.index("python -m rankeddojo.main")
        self.assertLess(
            public_pos,
            internal_pos,
            "README must show the public `rankeddojo` command before the "
            "internal `python -m rankeddojo.main` dev path",
        )

    def test_readme_labels_module_execution_as_internal(self) -> None:
        # The `python -m rankeddojo.main` snippet must be clearly
        # presented as internal/dev execution, not the product's public name.
        marker = "Execução alternativa a partir do código-fonte (uso interno/dev"
        self.assertIn(marker, self.readme)

    def test_readme_does_not_use_old_public_name(self) -> None:
        self.assertNotIn("Exam Trainer", self.readme)
        self.assertNotIn("EXAM TRAINER", self.readme)


class PublicExamplePackBrandingTest(unittest.TestCase):
    """Public example pack descriptions must reference RankedDojo, not the
    old product name."""

    PACKS = ("c-basics", "cpp-basics", "java-basics", "python-basics")

    def test_example_pack_descriptions_reference_rankeddojo(self) -> None:
        for pack in self.PACKS:
            pack_json = ROOT / "examples" / "packs" / pack / "pack.json"
            with self.subTest(pack=pack):
                content = pack_json.read_text(encoding="utf-8")
                self.assertIn("RankedDojo", content)
                self.assertNotIn("Exam Trainer", content)


class PublicUiBrandingTest(unittest.TestCase):
    """The Qt UI layer must not surface the old product name to users."""

    def test_ui_layer_has_no_old_public_branding_strings(self) -> None:
        ui_dir = SRC / "adapters" / "ui"
        offenders = []
        for path in ui_dir.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"EXAM TRAINER|Exam Trainer", text):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(
            offenders,
            [],
            f"old public branding found in UI source files: {offenders}",
        )


class InternalIdentityPreservedTest(unittest.TestCase):
    """Internal/technical identifiers must stay exactly as they are, even
    while the public branding is RankedDojo."""

    def test_app_dir_name_is_unchanged(self) -> None:
        paths_module = (SRC / "infrastructure" / "paths.py").read_text(encoding="utf-8")
        self.assertIn('APP_DIR_NAME = "rankeddojo"', paths_module)

    def test_package_namespace_is_unchanged(self) -> None:
        self.assertTrue((SRC / "main.py").is_file())
        self.assertEqual(SRC.name, "rankeddojo")

    def test_pyproject_keeps_internal_entry_point(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('rankeddojo = "rankeddojo.main:main"', pyproject)


if __name__ == "__main__":
    unittest.main()
