from __future__ import annotations

from pathlib import Path
from typing import Protocol


class EditorLaunchError(RuntimeError):
    pass


class EditorPort(Protocol):
    def open_directory(self, directory: Path, *, reuse_window: bool = False) -> None:
        raise NotImplementedError

    def open_file(self, path: Path, *, reuse_window: bool = True) -> None:
        """Open a single file, adding it as a new tab of an already-open window
        when the editor supports that (see `reuse_window` on `open_directory`).

        Used to open the raw `trace.txt` in the user's configured editor --
        never inside RankedDojo's own window -- alongside the exercise files
        already open there.
        """
        raise NotImplementedError


class EditorFactory(Protocol):
    """Create and validate editors from the user-configured command.

    The application (`MVPTrainerCoordinator`) only knows this boundary; the
    adapter decides which concrete editor exists (subprocess, known presets on
    disk, and so on).
    """

    def display_name(self, command: str) -> str:
        raise NotImplementedError

    def validate(self, command: str) -> Path:
        """Validate the executable. Raises `EditorLaunchError` if invalid."""
        raise NotImplementedError

    def create(self, executable: str) -> EditorPort:
        raise NotImplementedError

    def resolve_known(self, label: str) -> str | None:
        """Resolve a known preset, such as "VS Code", to an installed path if available."""
        raise NotImplementedError

    def known_labels(self) -> tuple[str, ...]:
        """Stable, ordered labels of the known presets this factory can resolve."""
        raise NotImplementedError
