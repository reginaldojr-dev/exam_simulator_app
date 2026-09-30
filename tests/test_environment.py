"""Ensure `rankeddojo` comes from this repository.

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
        self.assertEqual(pyproject["project"]["scripts"]["rankeddojo"], "rankeddojo.main:main")
        # No leftover script entry under the pre-migration internal name.
        self.assertNotIn("exam_trainer", pyproject["project"]["scripts"])

    def test_rankeddojo_is_imported_from_this_checkout(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-c", "import rankeddojo, inspect; print(inspect.getfile(rankeddojo))"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            "rankeddojo is not importable. Run: python -m pip install -e . (inside .venv)\n" + completed.stderr,
        )
        origin = Path(completed.stdout.strip()).resolve()
        expected = (ROOT / "src" / "rankeddojo").resolve()
        self.assertEqual(
            origin.parent,
            expected,
            f"rankeddojo comes from {origin}, not {expected}. "
            "Another copy is installed: see README > Troubleshooting.",
        )

    def test_persistent_app_dir_name_is_rankeddojo(self) -> None:
        # Post-migration current value (see infrastructure/data_dir_migration.py
        # for the one-time move from the pre-migration "exam-trainer" directory).
        from rankeddojo.infrastructure.paths import APP_DIR_NAME

        self.assertEqual(APP_DIR_NAME, "rankeddojo")

    def test_legacy_app_dir_name_is_the_pre_migration_value(self) -> None:
        from rankeddojo.infrastructure.paths import APP_DIR_NAME, LEGACY_APP_DIR_NAME

        self.assertEqual(LEGACY_APP_DIR_NAME, "exam-trainer")
        self.assertNotEqual(LEGACY_APP_DIR_NAME, APP_DIR_NAME)

    def test_legacy_and_current_config_dirs_share_the_same_parent_and_differ_only_by_name(self) -> None:
        from rankeddojo.infrastructure.paths import legacy_user_config_dir, user_config_dir

        self.assertEqual(legacy_user_config_dir().parent, user_config_dir().parent)
        self.assertEqual(legacy_user_config_dir().name, "exam-trainer")
        self.assertEqual(user_config_dir().name, "rankeddojo")

    def test_user_themes_dir_uses_the_current_data_root(self) -> None:
        # Fase 5: the external-themes folder is not a separate root -- it is
        # "themes" under the same persistent data directory config.json and
        # the managed packs already use, never a hardcoded %APPDATA% path.
        from rankeddojo.infrastructure.paths import managed_packs_dir, user_config_dir, user_themes_dir

        self.assertEqual(user_themes_dir(), user_config_dir() / "themes")
        self.assertEqual(user_themes_dir().parent, managed_packs_dir().parent)

    def test_user_plugins_dir_uses_the_current_data_root(self) -> None:
        from rankeddojo.infrastructure.paths import managed_packs_dir, user_config_dir, user_plugins_dir

        self.assertEqual(user_plugins_dir(), user_config_dir() / "plugins")
        self.assertEqual(user_plugins_dir().parent, managed_packs_dir().parent)

    def test_no_tracked_source_imports_the_pre_migration_namespace(self) -> None:
        """Nothing under src/ or tests/ may still `import exam_trainer` or
        `from exam_trainer...`: the internal package is `rankeddojo` end to end
        after the namespace migration. `exam-trainer`/`exam_trainer` as plain
        strings (the legacy data dir name, historical docs) are a separate,
        allowed case -- this only checks actual Python import statements.
        """
        import ast

        offenders: list[str] = []
        for folder in ("src", "tests"):
            for path in (ROOT / folder).rglob("*.py"):
                if "__pycache__" in path.parts:
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        names = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        names = [node.module or ""]
                    else:
                        continue
                    if any(name == "exam_trainer" or name.startswith("exam_trainer.") for name in names):
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
        self.assertEqual(offenders, [], f"still imports the old exam_trainer namespace: {offenders}")


if __name__ == "__main__":
    unittest.main()
