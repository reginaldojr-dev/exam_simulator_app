from __future__ import annotations

from pathlib import Path
from typing import Protocol


class EditorPort(Protocol):
    def open_directory(self, directory: Path) -> None:
        raise NotImplementedError
