from __future__ import annotations

from typing import Protocol

from exam_trainer.domain.workspace import Workspace


class WorkspacePort(Protocol):
    def exists(self, workspace: Workspace) -> bool:
        raise NotImplementedError

    def ensure_exists(self, workspace: Workspace) -> None:
        raise NotImplementedError
