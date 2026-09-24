from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath


class WorkspaceError(ValueError):
    """Raised when a workspace path is not usable."""


@dataclass(frozen=True)
class Workspace:
    """Regra pura: um caminho de workspace não pode ser vazio.

    `path` é tipado como `PurePath` (sem I/O). Expandir `~` e resolver o caminho é
    trabalho de quem chama `from_path` (application/adapters), usando `pathlib.Path`
    concreto antes de entregar o valor aqui — o domain nunca importa `Path`.
    """

    path: PurePath

    @classmethod
    def from_path(cls, path: PurePath | str) -> "Workspace":
        if not str(path).strip():
            raise WorkspaceError("Workspace path cannot be empty.")
        normalized_path = path if isinstance(path, PurePath) else PurePath(path)
        return cls(path=normalized_path)
