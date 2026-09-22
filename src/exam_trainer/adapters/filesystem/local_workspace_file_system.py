from __future__ import annotations

from exam_trainer.domain.workspace import Workspace, WorkspaceError


class LocalWorkspaceFileSystem:
    def exists(self, workspace: Workspace) -> bool:
        return workspace.path.is_dir()

    def ensure_exists(self, workspace: Workspace) -> None:
        if workspace.path.exists() and not workspace.path.is_dir():
            raise WorkspaceError(f"Workspace path is not a directory: {workspace.path}")
        workspace.path.mkdir(parents=True, exist_ok=True)
