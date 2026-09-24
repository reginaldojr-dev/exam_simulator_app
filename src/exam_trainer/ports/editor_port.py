from __future__ import annotations

from pathlib import Path
from typing import Protocol


class EditorLaunchError(RuntimeError):
    pass


class EditorPort(Protocol):
    def open_directory(self, directory: Path) -> None:
        raise NotImplementedError


class EditorFactory(Protocol):
    """Cria e valida editores a partir do comando configurado pelo usuário.

    A application (`MVPTrainerCoordinator`) conhece só esta fronteira; quem decide QUAL
    editor concreto existe (subprocess, presets conhecidos no disco etc.) é o adapter.
    """

    def display_name(self, command: str) -> str:
        raise NotImplementedError

    def validate(self, command: str) -> Path:
        """Valida o executável. Levanta `EditorLaunchError` se inválido."""
        raise NotImplementedError

    def create(self, executable: str) -> EditorPort:
        raise NotImplementedError

    def resolve_known(self, label: str) -> str | None:
        """Resolve um preset conhecido (ex.: "VS Code") para um caminho instalado, se houver."""
        raise NotImplementedError
