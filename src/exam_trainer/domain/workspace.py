from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath


class WorkspaceError(ValueError):
    """Raised when a workspace path is not usable."""


@dataclass(frozen=True)
class Workspace:
    """Pure workspace rule: a workspace path cannot be empty.

    `path` is represented as `PurePath` and performs no I/O. Expanding `~` and
    resolving the concrete path belongs to the caller/application adapter before
    the value reaches the domain; the domain never imports `Path`.
    """

    path: PurePath

    @classmethod
    def from_path(cls, path: PurePath | str) -> "Workspace":
        if not str(path).strip():
            raise WorkspaceError("Workspace path cannot be empty.")
        normalized_path = path if isinstance(path, PurePath) else PurePath(path)
        return cls(path=normalized_path)
