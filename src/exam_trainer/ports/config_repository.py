from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ConfigRepository(Protocol):
    def load_workspace_path(self) -> Path | None:
        raise NotImplementedError

    def save_workspace_path(self, workspace_path: Path) -> None:
        raise NotImplementedError
