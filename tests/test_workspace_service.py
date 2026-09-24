from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from exam_trainer.application.workspace_service import WorkspaceService
from exam_trainer.domain.workspace import Workspace


class InMemoryConfigRepository:
    def __init__(self, workspace_path: Path | None = None) -> None:
        self.workspace_path = workspace_path

    def load_workspace_path(self) -> Path | None:
        return self.workspace_path

    def save_workspace_path(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path


class InMemoryWorkspaceFileSystem:
    def __init__(self, existing_paths: set[Path] | None = None) -> None:
        self.existing_paths = existing_paths or set()
        self.created_paths: list[Path] = []

    def exists(self, workspace: Workspace) -> bool:
        return workspace.path in self.existing_paths

    def ensure_exists(self, workspace: Workspace) -> None:
        self.created_paths.append(workspace.path)
        self.existing_paths.add(workspace.path)


class WorkspaceServiceTest(unittest.TestCase):
    def test_startup_state_requires_workspace_when_config_is_missing(self) -> None:
        service = WorkspaceService(
            config_repository=InMemoryConfigRepository(),
            workspace_file_system=InMemoryWorkspaceFileSystem(),
        )

        state = service.get_startup_state()

        self.assertFalse(state.has_workspace)
        self.assertIsNone(state.workspace_path)

    def test_startup_state_uses_existing_saved_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "exam-trainer"
            service = WorkspaceService(
                config_repository=InMemoryConfigRepository(workspace_path),
                workspace_file_system=InMemoryWorkspaceFileSystem({workspace_path}),
            )

            state = service.get_startup_state()

            self.assertTrue(state.has_workspace)
            self.assertEqual(state.workspace_path, workspace_path)

    def test_startup_state_requires_workspace_when_saved_path_no_longer_exists(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "exam-trainer"
            service = WorkspaceService(
                config_repository=InMemoryConfigRepository(workspace_path),
                workspace_file_system=InMemoryWorkspaceFileSystem(),
            )

            state = service.get_startup_state()

            self.assertFalse(state.has_workspace)
            self.assertIsNone(state.workspace_path)

    def test_configure_workspace_creates_and_saves_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "exam-trainer"
            config_repository = InMemoryConfigRepository()
            file_system = InMemoryWorkspaceFileSystem()
            service = WorkspaceService(config_repository, file_system)

            workspace = service.configure_workspace(workspace_path)

            self.assertEqual(workspace.path, workspace_path)
            self.assertEqual(config_repository.workspace_path, workspace_path)
            self.assertEqual(file_system.created_paths, [workspace_path])

