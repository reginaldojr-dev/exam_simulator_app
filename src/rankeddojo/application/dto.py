from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StartupState:
    has_workspace: bool
    workspace_path: Path | None
