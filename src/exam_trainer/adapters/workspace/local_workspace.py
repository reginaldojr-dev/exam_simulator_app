from __future__ import annotations

from exam_trainer.adapters.filesystem.local_workspace_file_system import (
    LocalWorkspaceFileSystem,
)


class LocalWorkspace(LocalWorkspaceFileSystem):
    """Filesystem-backed workspace adapter."""
