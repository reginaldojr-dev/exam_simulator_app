"""Porta de runtime por linguagem.

Divisão de responsabilidades:
- o GRADER (GenericGrader) cuida de casos, expectations, comparação, fail-fast, trace,
  seeds e política;
- o RUNTIME cuida de disponibilidade, preparação (compilar / checar sintaxe / gerar
  harness), execução, stdout/stderr/exit code e timeout.

Nenhum runtime usa shell. Nenhum runtime oferece sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from exam_trainer.ports.compiler_port import CompilationResult


@dataclass(frozen=True)
class ProgramSpec:
    """O que precisa virar um programa executável (submissão ou referência)."""

    main_source: Path
    harness: Path | None = None  # harness fornecido pelo PACK (C)
    entry: str | None = None  # função chamada pelo harness do APP (Python)
    args_format: str | None = None
    extra_sources: tuple[Path, ...] = ()


@dataclass(frozen=True)
class PreparedProgram:
    success: bool
    build: CompilationResult  # comando + saída da preparação (vai para o trace)
    argv: tuple[str, ...] = ()  # prefixo do comando; os argumentos do caso vêm depois
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
    tool: str | None = None  # ex.: caminho do compilador / do interpretador
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
    display_name: str  # ex.: "Compilador C", "Python"

    def is_ready(self) -> bool:
        """Já validado nesta execução? NÃO roda processo externo (seguro na thread da UI)."""
        ...

    def check_available(self) -> bool:
        """Detecta/valida (pode rodar processos; chamar fora da thread da UI)."""
        ...

    def current_tool(self) -> str | None:
        """Ferramenta configurada/detectada, sem rodar processo."""
        ...

    def redetect(self) -> str | None: ...

    def configure_manual(self, path: Path) -> str:
        """Valida e grava a ferramenta escolhida pelo usuário. ValueError se inválida."""
        ...

    def prepare(self, spec: ProgramSpec, build_dir: Path, name: str) -> PreparedProgram: ...

    def run(
        self,
        program: PreparedProgram,
        args: tuple[str, ...],
        stdin: str,
        timeout_seconds: int,
    ) -> ProcessOutcome: ...
