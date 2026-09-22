from __future__ import annotations

from pathlib import Path

from exam_trainer.application.dto import StartupState
from exam_trainer.domain.workspace import Workspace
from exam_trainer.ports.config_repository import ConfigRepository
from exam_trainer.ports.workspace_port import WorkspacePort


class InitializeApplication:
    def __init__(
        self,
        config_repository: ConfigRepository,
        workspace_port: WorkspacePort,
    ) -> None:
        self._config_repository = config_repository
        self._workspace_port = workspace_port

    def get_startup_state(self) -> StartupState:
        saved_path = self._config_repository.load_workspace_path()
        if saved_path is None:
            return StartupState(has_workspace=False, workspace_path=None)

        workspace = Workspace.from_path(saved_path)
        if not self._workspace_port.exists(workspace):
            return StartupState(has_workspace=False, workspace_path=None)

        return StartupState(has_workspace=True, workspace_path=workspace.path)

    def configure_workspace(self, selected_directory: Path | str) -> Workspace:
        workspace = Workspace.from_path(selected_directory)
        self._workspace_port.ensure_exists(workspace)
        self._config_repository.save_workspace_path(workspace.path)
        return workspace
