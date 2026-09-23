"""Runtime C: compila com o compilador detectado/configurado e executa o binário."""

from __future__ import annotations

import sys
from pathlib import Path

from exam_trainer.adapters.runtime.process import run_process
from exam_trainer.ports.compiler_port import CompilerPort, ConfigurableCompilerPort
from exam_trainer.ports.runtime_port import PreparedProgram, ProcessOutcome, ProgramSpec


class CRuntime:
    language = "c"
    display_name = "Compilador C"

    def __init__(self, compiler: CompilerPort, manager: ConfigurableCompilerPort | None = None) -> None:
        """`compiler` compila; `manager` (opcional) é o mesmo compilador com detecção/seleção.

        Sem `manager` (ex.: grader isolado em testes) as funções de configuração ficam
        indisponíveis, mas preparar/executar funciona.
        """
        self._compiler = compiler
        self._manager = manager

    # --------------------------------------------------------- disponibilidade
    def is_ready(self) -> bool:
        if self._manager is None:
            return self._compiler.is_available()
        return self._manager.cached_compiler() is not None

    def check_available(self) -> bool:
        return self._compiler.is_available()

    def current_tool(self) -> str | None:
        return None if self._manager is None else self._manager.current_compiler()

    def redetect(self) -> str | None:
        if self._manager is None:
            return None
        return self._manager.redetect()

    def configure_manual(self, path: Path) -> str:
        if self._manager is None:
            raise ValueError("Este compilador não aceita seleção manual.")
        if not self._manager.validate_compiler(path):
            raise ValueError("Nenhum compilador C compatível com os exercícios foi encontrado nesse caminho.")
        self._manager.set_manual_compiler(str(path))
        return str(path)

    # ------------------------------------------------------------- execução
    def prepare(self, spec: ProgramSpec, build_dir: Path, name: str) -> PreparedProgram:
        sources = [*([spec.harness] if spec.harness is not None else []), spec.main_source, *spec.extra_sources]
        build_dir.mkdir(parents=True, exist_ok=True)
        executable = build_dir / (f"{name}.exe" if sys.platform == "win32" else name)
        compilation = self._compiler.compile(sources, executable)
        if not compilation.success or compilation.executable_path is None:
            return PreparedProgram(success=False, build=compilation)
        return PreparedProgram(success=True, build=compilation, argv=(str(compilation.executable_path),))

    def run(
        self,
        program: PreparedProgram,
        args: tuple[str, ...],
        stdin: str,
        timeout_seconds: int,
    ) -> ProcessOutcome:
        return run_process([*program.argv, *args], stdin, timeout_seconds, program.cwd)
