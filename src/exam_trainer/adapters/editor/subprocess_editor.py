from __future__ import annotations

import subprocess
import shutil
import sys
from pathlib import Path

from exam_trainer.ports.editor_port import EditorLaunchError

__all__ = [
    "EditorLaunchError",
    "SubprocessEditor",
    "SubprocessEditorFactory",
    "editor_display_name",
    "resolve_known_editor",
    "validate_editor_executable",
]


class SubprocessEditor:
    def __init__(self, executable: str, display_name: str | None = None) -> None:
        self._executable = executable
        self.display_name = display_name or executable

    def open_directory(self, directory: Path) -> None:
        try:
            subprocess.Popen(
                [self._executable, str(directory)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            raise EditorLaunchError(
                f"Could not open {directory} with {self.display_name}: {error}"
            ) from error


def editor_display_name(executable: str) -> str:
    lowered = executable.lower()
    if "code" in Path(executable).stem.lower():
        return "VS Code"
    if "zed" in lowered:
        return "Zed"
    if "cursor" in lowered:
        return "Cursor"
    return Path(executable).stem or executable


def resolve_known_editor(name: str) -> str | None:
    key = name.lower()
    commands = {
        "vs code": ("code", "Code.exe"),
        "zed": ("zed", "Zed.exe"),
        "cursor": ("cursor", "Cursor.exe"),
    }.get(key, (name,))

    for command in commands:
        resolved = shutil.which(command)
        if resolved and Path(resolved).is_file():
            return resolved

    if sys.platform == "win32":
        roots = [
            Path.home() / "AppData" / "Local" / "Programs",
            Path("C:/Program Files"),
            Path("C:/Program Files (x86)"),
        ]
        patterns = {
            "vs code": ("Microsoft VS Code/Code.exe", "VS Code/Code.exe"),
            "zed": ("Zed/Zed.exe",),
            "cursor": ("Cursor/Cursor.exe",),
        }.get(key, ())
        for root in roots:
            for pattern in patterns:
                candidate = root / pattern
                if candidate.is_file():
                    return str(candidate)
    return None


def validate_editor_executable(executable: str | Path) -> Path:
    path = Path(executable)
    if not path.exists():
        raise EditorLaunchError(f"Editor executable does not exist: {path}")
    if not path.is_file():
        raise EditorLaunchError(f"Editor executable must be a file: {path}")
    return path


class SubprocessEditorFactory:
    """Implementação padrão de `EditorFactory` (application/ports) via subprocess."""

    def display_name(self, command: str) -> str:
        return editor_display_name(command)

    def validate(self, command: str) -> Path:
        return validate_editor_executable(command)

    def create(self, executable: str) -> SubprocessEditor:
        return SubprocessEditor(executable, editor_display_name(executable))

    def resolve_known(self, label: str) -> str | None:
        return resolve_known_editor(label)
