"""Ensure `exam_trainer` comes from this repository.

Catches the case where an editable install from another project copy, such as
Documents/ChatGPT/exam_simullator, hijacks the import. Runs in a fresh process
from the project root, as a user would.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class EnvironmentTest(unittest.TestCase):
    def test_public_distribution_renamed_without_package_rename(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(pyproject["project"]["name"], "rankeddojo")
        self.assertIn("rankeddojo", pyproject["project"]["scripts"])
        self.assertEqual(pyproject["project"]["scripts"]["rankeddojo"], "exam_trainer.main:main")
        self.assertNotIn("exam-trainer", pyproject["project"]["scripts"])

    def test_exam_trainer_is_imported_from_this_checkout(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-c", "import exam_trainer, inspect; print(inspect.getfile(exam_trainer))"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            "exam_trainer is not importable. Run: python -m pip install -e . (inside .venv)\n" + completed.stderr,
        )
        origin = Path(completed.stdout.strip()).resolve()
        expected = (ROOT / "src" / "exam_trainer").resolve()
        self.assertEqual(
            origin.parent,
            expected,
            f"exam_trainer comes from {origin}, not {expected}. "
            "Another copy is installed: see README > Troubleshooting.",
        )

    def test_legacy_persistent_app_dir_name_is_preserved(self) -> None:
        from exam_trainer.infrastructure.paths import APP_DIR_NAME

        self.assertEqual(APP_DIR_NAME, "exam-trainer")


if __name__ == "__main__":
    unittest.main()
