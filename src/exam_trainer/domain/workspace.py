from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WorkspaceError(ValueError):
    """Raised when a workspace path is not usable."""


@dataclass(frozen=True)
class Workspace:
    path: Path

    @classmethod
    def from_path(cls, path: Path | str) -> "Workspace":
        normalized_path = Path(path).expanduser()
        if not str(normalized_path).strip():
            raise WorkspaceError("Workspace path cannot be empty.")
        return cls(path=normalized_path)
