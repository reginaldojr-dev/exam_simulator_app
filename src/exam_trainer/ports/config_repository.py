from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ConfigRepository(Protocol):
    def load_workspace_path(self) -> Path | None:
        raise NotImplementedError

    def save_workspace_path(self, workspace_path: Path) -> None:
        raise NotImplementedError


class AppSettingsRepository(ConfigRepository, Protocol):
    """Configuração completa usada pelo coordinator (JsonAppConfigRepository)."""

    def load_editor_command(self) -> str:
        raise NotImplementedError

    def save_editor_command(self, editor_command: str) -> None:
        raise NotImplementedError

    def load_compiler_path(self) -> str | None:
        raise NotImplementedError

    def save_compiler_path(self, compiler_path: str | None) -> None:
        raise NotImplementedError

    def load_theme(self) -> str | None:
        raise NotImplementedError

    def save_theme(self, theme_key: str) -> None:
        raise NotImplementedError
