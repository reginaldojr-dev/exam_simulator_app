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
    ) -> CompilationResult:
        raise NotImplementedError


class ConfigurableCompilerPort(CompilerPort, Protocol):
    """Compilador com detecção e seleção manual (usado pelo CRuntime nas Configurações)."""

    def cached_compiler(self) -> str | None:
        """Compilador já validado nesta execução (sem rodar processo)."""
        raise NotImplementedError

    def current_compiler(self) -> str | None:
        raise NotImplementedError

    def redetect(self) -> str | None:
        raise NotImplementedError

    def validate_compiler(self, compiler_path: str | Path) -> bool:
        raise NotImplementedError

    def set_manual_compiler(self, compiler_path: str | Path | None) -> None:
        raise NotImplementedError
