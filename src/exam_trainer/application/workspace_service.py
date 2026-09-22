from __future__ import annotations

from pathlib import Path

from exam_trainer.application.dto import StartupState
from exam_trainer.domain.workspace import Workspace
from exam_trainer.application.use_cases.initialize_application import (
    InitializeApplication,
)
from exam_trainer.ports.config_repository import ConfigRepository
from exam_trainer.ports.workspace_port import WorkspacePort


class WorkspaceService(InitializeApplication):
    def __init__(
        self,
        config_repository: ConfigRepository,
        workspace_file_system: WorkspacePort,
    ) -> None:
        super().__init__(
            config_repository=config_repository,
            workspace_port=workspace_file_system,
        )

    def get_startup_state(self) -> StartupState:
        return super().get_startup_state()

    def configure_workspace(self, selected_directory: Path | str) -> Workspace:
        return super().configure_workspace(selected_directory)
