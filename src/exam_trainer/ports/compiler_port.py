from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CompilationResult:
    success: bool
    output: str = ""
    command: tuple[str, ...] = ()
    executable_path: Path | None = None


class CompilerPort(Protocol):
    def is_available(self) -> bool:
        raise NotImplementedError

    def compile(
        self,
        source_files: list[Path],
        output_path: Path,
        *,
        include_dirs: tuple[Path, ...] = (),
    ) -> CompilationResult:
        raise NotImplementedError


class ConfigurableCompilerPort(CompilerPort, Protocol):
    """Compiler with detection and manual selection, used by CRuntime in Settings."""

    def cached_compiler(self) -> str | None:
        """Compiler already validated in this run, without spawning a process."""
        raise NotImplementedError

    def current_compiler(self) -> str | None:
        raise NotImplementedError

    def redetect(self) -> str | None:
        raise NotImplementedError

    def validate_compiler(self, compiler_path: str | Path) -> bool:
        raise NotImplementedError

    def set_manual_compiler(self, compiler_path: str | Path | None) -> None:
        raise NotImplementedError
