"""C runtime: compile with the detected/configured compiler and run the binary."""

from __future__ import annotations

import sys
from pathlib import Path

from rankeddojo.adapters.runtime.process import run_process
from rankeddojo.domain.exercise_definition import FUNCTION_CALL, PROGRAM_OUTPUT
from rankeddojo.ports.compiler_port import CompilerPort, ConfigurableCompilerPort
from rankeddojo.ports.runtime_port import PreparedProgram, ProcessOutcome, ProgramSpec, RuntimeDescriptor


class CRuntime:
    language = "c"
    display_name = "Compilador C"
    descriptor = RuntimeDescriptor(
        language=language,
        display_name=display_name,
        file_extensions=(".c", ".h"),
        execution_types=(PROGRAM_OUTPUT, FUNCTION_CALL),
        function_harness="pack",
    )

    def __init__(self, compiler: CompilerPort, manager: ConfigurableCompilerPort | None = None) -> None:
        """`compiler` compiles; optional `manager` is the same compiler with detection/selection.

        Without `manager`, such as in an isolated grader test, configuration
        functions are unavailable, but prepare/run still works.
        """
        self._compiler = compiler
        self._manager = manager

    # ----------------------------------------------------------- availability
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

    # --------------------------------------------------------------- execution
    def prepare(self, spec: ProgramSpec, build_dir: Path, name: str) -> PreparedProgram:
        sources = [*([spec.harness] if spec.harness is not None else []), spec.main_source, *spec.extra_sources]
        build_dir.mkdir(parents=True, exist_ok=True)
        executable = build_dir / (f"{name}.exe" if sys.platform == "win32" else name)
        compilation = self._compiler.compile(sources, executable, include_dirs=spec.include_dirs)
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
