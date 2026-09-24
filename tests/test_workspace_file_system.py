from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from exam_trainer.adapters.filesystem.local_workspace_file_system import (
    LocalWorkspaceFileSystem,
)
from exam_trainer.domain.workspace import Workspace, WorkspaceError


class LocalWorkspaceFileSystemTest(unittest.TestCase):
    def test_creates_workspace_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Workspace.from_path(Path(temp_dir) / "exam-trainer")
            file_system = LocalWorkspaceFileSystem()

            file_system.ensure_exists(workspace)

            self.assertTrue(workspace.path.is_dir())

    def test_rejects_existing_file_as_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "exam-trainer"
            file_path.write_text("not a directory", encoding="utf-8")
            workspace = Workspace.from_path(file_path)
            file_system = LocalWorkspaceFileSystem()

            with self.assertRaises(WorkspaceError):
                file_system.ensure_exists(workspace)

