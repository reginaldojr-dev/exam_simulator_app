"""Runtime port per programming language.

Responsibility split:
- the GRADER (GenericGrader) handles cases, expectations, comparison, fail-fast,
  trace, seeds, and policy;
- the RUNTIME handles availability, preparation (compile / syntax check /
  harness generation), execution, stdout/stderr/exit code, and timeout.

No runtime uses a shell. No runtime provides a sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from exam_trainer.ports.compiler_port import CompilationResult


@dataclass(frozen=True)
class ProgramSpec:
    """What must become an executable program: submission or reference."""

    main_source: Path
    harness: Path | None = None  # harness provided by the pack (C)
    entry: str | None = None  # function called by the app harness (Python)
    args_format: str | None = None
    extra_sources: tuple[Path, ...] = ()
    include_dirs: tuple[Path, ...] = ()


@dataclass(frozen=True)
class PreparedProgram:
    success: bool
    build: CompilationResult  # preparation command + output; included in trace
    argv: tuple[str, ...] = ()  # command prefix; case arguments are appended later
    cwd: Path | None = None


@dataclass(frozen=True)
class ProcessOutcome:
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class RuntimeStatus:
    language: str
    display_name: str
    supported: bool
    available: bool
    checked: bool = False
    tool: str | None = None  # e.g. compiler/interpreter path
    message: str = ""
    details: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RuntimeDescriptor:
    language: str
    display_name: str
    file_extensions: tuple[str, ...]
    execution_types: tuple[str, ...]
    function_harness: str
    args_formats: tuple[str, ...] = ()
    main_class_required: bool = False


@runtime_checkable
class LanguageRuntime(Protocol):
    language: str
    display_name: str  # e.g. "C compiler", "Python"

    def is_ready(self) -> bool:
        """Already validated in this run? Does NOT spawn a process; safe on the UI thread."""
        ...

    def check_available(self) -> bool:
        """Detect/validate availability; may spawn processes, so call outside the UI thread."""
        ...

    def current_tool(self) -> str | None:
        """Configured/detected tool without spawning a process."""
        ...

    def redetect(self) -> str | None: ...

    def configure_manual(self, path: Path) -> str:
        """Validate and save the user-selected tool. Raises ValueError if invalid."""
        ...

    def prepare(self, spec: ProgramSpec, build_dir: Path, name: str) -> PreparedProgram: ...

    def run(
        self,
        program: PreparedProgram,
        args: tuple[str, ...],
        stdin: str,
        timeout_seconds: int,
    ) -> ProcessOutcome: ...
