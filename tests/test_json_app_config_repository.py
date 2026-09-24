from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from exam_trainer.adapters.persistence.json_app_config_repository import (
    JsonAppConfigRepository,
)


class JsonAppConfigRepositoryTest(unittest.TestCase):
    def test_returns_none_when_config_file_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = JsonAppConfigRepository(Path(temp_dir) / "config.json")

            self.assertIsNone(repository.load_workspace_path())

    def test_saves_and_loads_workspace_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config" / "config.json"
            workspace_path = Path(temp_dir) / "exam-trainer"
            repository = JsonAppConfigRepository(config_path)

            repository.save_workspace_path(workspace_path)

            self.assertEqual(repository.load_workspace_path(), workspace_path)

    def test_returns_none_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text("{invalid", encoding="utf-8")
            repository = JsonAppConfigRepository(config_path)

            self.assertIsNone(repository.load_workspace_path())

    def test_returns_none_when_workspace_path_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(json.dumps({"other": "value"}), encoding="utf-8")
            repository = JsonAppConfigRepository(config_path)

            self.assertIsNone(repository.load_workspace_path())

    def test_converts_file_uri_editor_path_to_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = JsonAppConfigRepository(Path(temp_dir) / "config.json")

            repository.save_editor_command(
                "file:///C:/Users/junio/AppData/Local/Programs/Microsoft%20VS%20Code/Code.exe"
            )

            self.assertEqual(
                repository.load_editor_command(),
                str(Path("C:/Users/junio/AppData/Local/Programs/Microsoft VS Code/Code.exe")),
            )

    def test_saves_and_loads_manual_compiler_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = JsonAppConfigRepository(Path(temp_dir) / "config.json")
            compiler = Path(temp_dir) / "clang.exe"

            repository.save_compiler_path(str(compiler))

            self.assertEqual(repository.load_compiler_path(), str(compiler))

