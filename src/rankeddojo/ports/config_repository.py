from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ConfigRepository(Protocol):
    def load_workspace_path(self) -> Path | None:
        raise NotImplementedError

    def save_workspace_path(self, workspace_path: Path) -> None:
        raise NotImplementedError


class AppSettingsRepository(ConfigRepository, Protocol):
    """Complete configuration used by the coordinator (JsonAppConfigRepository)."""

    def load_editor_command(self) -> str:
        raise NotImplementedError

    def save_editor_command(self, editor_command: str) -> None:
        raise NotImplementedError

    def load_compiler_path(self) -> str | None:
        raise NotImplementedError

    def save_compiler_path(self, compiler_path: str | None) -> None:
        raise NotImplementedError

    def load_runtime_path(self, language: str) -> str | None:
        raise NotImplementedError

    def save_runtime_path(self, language: str, path: str | None) -> None:
        raise NotImplementedError

    def load_theme(self) -> str | None:
        raise NotImplementedError

    def save_theme(self, theme_key: str) -> None:
        raise NotImplementedError

    def load_ui_locale(self) -> str:
        raise NotImplementedError

    def save_ui_locale(self, locale: str) -> None:
        raise NotImplementedError

    def load_enabled_plugins(self) -> tuple[str, ...]:
        """Ids of plugins explicitly opted in (see `adapters/plugins/`).
        Absent or malformed in the config file -> empty tuple, never raises;
        an old config file without this key still loads normally."""
        raise NotImplementedError

    def save_enabled_plugins(self, plugin_ids: tuple[str, ...]) -> None:
        raise NotImplementedError
