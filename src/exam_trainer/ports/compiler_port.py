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
