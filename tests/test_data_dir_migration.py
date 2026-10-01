"""Namespace migration: covers `migrate_legacy_data_dir`, which moves the
pre-`rankeddojo` data directory (`exam-trainer`) into the current one, once,
safely, and without ever deleting data on failure or on conflict.

Every test builds its own isolated legacy/target directories under a
`tempfile.TemporaryDirectory()` -- never the real `user_config_dir()` --
so nothing here touches the machine's actual RankedDojo data.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from rankeddojo.infrastructure.data_dir_migration import (
    DataDirMigrationStatus,
    migrate_legacy_data_dir,
)


def _write(path: Path, content: str = "data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class DataDirMigrationTest(unittest.TestCase):
    def test_nothing_to_migrate_when_neither_directory_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = migrate_legacy_data_dir(root / "exam-trainer", root / "rankeddojo")

            self.assertEqual(result.status, DataDirMigrationStatus.NOTHING_TO_MIGRATE)
            self.assertFalse((root / "rankeddojo").exists())

    def test_rename_migrates_legacy_into_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "exam-trainer"
            target = root / "rankeddojo"
            _write(legacy / "config.json", '{"theme": "terminal"}')
            _write(legacy / "packs" / "sample" / "pack.json", "{}")

            result = migrate_legacy_data_dir(legacy, target)

            self.assertEqual(result.status, DataDirMigrationStatus.MIGRATED_BY_RENAME)
            self.assertFalse(legacy.exists())
            self.assertEqual((target / "config.json").read_text(encoding="utf-8"), '{"theme": "terminal"}')
            self.assertTrue((target / "packs" / "sample" / "pack.json").is_file())

    def test_copy_fallback_migrates_and_removes_legacy_when_rename_is_not_possible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "exam-trainer"
            target = root / "rankeddojo"
            _write(legacy / "trainer.sqlite3", "binary-ish-content")
            _write(legacy / "themes" / "neon" / "theme.json", "{}")

            original_rename = Path.rename

            def _rename_only_fails_for_legacy(self: Path, target_path) -> None:  # noqa: ANN001
                if self == legacy:
                    raise OSError("simulated cross-device rename failure")
                return original_rename(self, target_path)

            Path.rename = _rename_only_fails_for_legacy  # type: ignore[assignment]
            try:
                result = migrate_legacy_data_dir(legacy, target)
            finally:
                Path.rename = original_rename  # type: ignore[assignment]

            self.assertEqual(result.status, DataDirMigrationStatus.MIGRATED_BY_COPY)
            self.assertFalse(legacy.exists())
            self.assertEqual((target / "trainer.sqlite3").read_text(encoding="utf-8"), "binary-ish-content")
            self.assertTrue((target / "themes" / "neon" / "theme.json").is_file())
            # No leftover staging folder.
            self.assertEqual(
                sorted(p.name for p in root.iterdir()),
                ["rankeddojo"],
            )

    def test_already_migrated_when_target_exists_and_legacy_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "rankeddojo"
            _write(target / "config.json", "current")

            result = migrate_legacy_data_dir(root / "exam-trainer", target)

            self.assertEqual(result.status, DataDirMigrationStatus.ALREADY_MIGRATED)
            self.assertEqual((target / "config.json").read_text(encoding="utf-8"), "current")

    def test_idempotent_second_call_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "exam-trainer"
            target = root / "rankeddojo"
            _write(legacy / "config.json", "original")

            first = migrate_legacy_data_dir(legacy, target)
            second = migrate_legacy_data_dir(legacy, target)

            self.assertEqual(first.status, DataDirMigrationStatus.MIGRATED_BY_RENAME)
            self.assertEqual(second.status, DataDirMigrationStatus.ALREADY_MIGRATED)
            self.assertEqual((target / "config.json").read_text(encoding="utf-8"), "original")

    def test_both_exist_preserves_both_and_reports_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "exam-trainer"
            target = root / "rankeddojo"
            _write(legacy / "config.json", "old")
            _write(target / "config.json", "new")

            result = migrate_legacy_data_dir(legacy, target)

            self.assertEqual(result.status, DataDirMigrationStatus.BOTH_EXIST_CONFLICT)
            self.assertEqual((legacy / "config.json").read_text(encoding="utf-8"), "old")
            self.assertEqual((target / "config.json").read_text(encoding="utf-8"), "new")

    def test_verification_failure_during_copy_preserves_legacy_and_does_not_create_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "exam-trainer"
            target = root / "rankeddojo"
            _write(legacy / "config.json", "important-data")

            original_rename = Path.rename

            def _fail_every_rename(self: Path, target_path) -> None:  # noqa: ANN001, ARG001
                raise OSError("simulated failure: rename never succeeds")

            import shutil as shutil_module

            original_copytree = shutil_module.copytree

            def _copytree_then_corrupt(src, dst, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
                original_copytree(src, dst, *args, **kwargs)
                # Corrupt the copy so `_verify_copy` must catch the mismatch.
                (Path(dst) / "config.json").write_text("corrupted", encoding="utf-8")

            Path.rename = _fail_every_rename  # type: ignore[assignment]
            shutil_module.copytree = _copytree_then_corrupt
            try:
                result = migrate_legacy_data_dir(legacy, target)
            finally:
                Path.rename = original_rename  # type: ignore[assignment]
                shutil_module.copytree = original_copytree

            self.assertEqual(result.status, DataDirMigrationStatus.FAILED)
            self.assertTrue(legacy.is_dir())
            self.assertEqual((legacy / "config.json").read_text(encoding="utf-8"), "important-data")
            self.assertFalse(target.exists())
            # No leftover staging folder either.
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["exam-trainer"])

    def test_default_arguments_use_the_real_legacy_and_current_paths(self) -> None:
        from rankeddojo.infrastructure.paths import legacy_user_config_dir, user_config_dir

        with tempfile.TemporaryDirectory() as tmp:
            # Neither directory exists under an isolated HOME/APPDATA, so this
            # only exercises that the defaults resolve to the real path
            # helpers without needing to touch the actual machine state.
            env_backup = dict(os.environ)
            try:
                os.environ["APPDATA"] = tmp
                os.environ["HOME"] = tmp
                result = migrate_legacy_data_dir()
            finally:
                os.environ.clear()
                os.environ.update(env_backup)

            self.assertIn(
                result.status,
                (DataDirMigrationStatus.NOTHING_TO_MIGRATE, DataDirMigrationStatus.ALREADY_MIGRATED),
            )
            self.assertIsInstance(legacy_user_config_dir(), Path)
            self.assertIsInstance(user_config_dir(), Path)


if __name__ == "__main__":
    unittest.main()
