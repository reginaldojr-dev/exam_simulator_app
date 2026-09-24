"""Runtime Java: valida JDK (`javac` + `java`), compila classes e executa a main."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from exam_trainer.adapters.runtime.process import run_process
from exam_trainer.domain.exercise_definition import PROGRAM_OUTPUT
from exam_trainer.ports.compiler_port import CompilationResult
from exam_trainer.ports.runtime_port import PreparedProgram, ProcessOutcome, ProgramSpec, RuntimeDescriptor

PROBE_TIMEOUT_SECONDS = 10


class JavaRuntime:
    language = "java"
    display_name = "Java/JDK"
    descriptor = RuntimeDescriptor(
        language=language,
        display_name=display_name,
        file_extensions=(".java",),
        execution_types=(PROGRAM_OUTPUT,),
        function_harness="none",
        main_class_required=True,
    )

    def __init__(self, manual_javac: str | None = None, java_candidates: tuple[str, ...] = ("java",)) -> None:
        self._manual_javac = manual_javac
        self._java_candidates = java_candidates
        self._detected_javac: str | None = None
        self._detected_java: str | None = None

    def is_ready(self) -> bool:
        return self._detected_javac is not None and self._detected_java is not None

    def check_available(self) -> bool:
        return self._find() is not None

    def current_tool(self) -> str | None:
        if self._detected_javac and self._detected_java:
            return f"{self._detected_javac} | {self._detected_java}"
        return self._manual_javac

    def redetect(self) -> str | None:
        self._detected_javac = None
        self._detected_java = None
        found = self._find()
        return None if found is None else f"{found[0]} | {found[1]}"

    def configure_manual(self, path: Path) -> str:
        javac = str(path)
        if not self._valid_tool((javac,), "-version"):
            raise ValueError("javac inválido. Selecione um compilador Java de um JDK.")
        java = self._java_near_javac(Path(javac)) or self._find_java()
        if java is None:
            raise ValueError("Java/JDK não encontrado: javac existe, mas java não foi localizado.")
        self._manual_javac = javac
        self._detected_javac = javac
        self._detected_java = java
        return f"{javac} | {java}"

    def prepare(self, spec: ProgramSpec, build_dir: Path, name: str) -> PreparedProgram:
        tools = self._find()
        if tools is None:
            return PreparedProgram(
                success=False,
                build=CompilationResult(success=False, output="Java/JDK não encontrado. Configure um JDK compatível."),
            )
        javac, java = tools
        build_dir.mkdir(parents=True, exist_ok=True)
        sources = [spec.main_source, *spec.extra_sources]
        command = (javac, "-d", str(build_dir), *(str(source) for source in sources))
        completed = subprocess.run(list(command), capture_output=True, text=True, check=False)
        output = completed.stdout + completed.stderr
        build = CompilationResult(
            success=completed.returncode == 0,
            output=output,
            command=command,
            executable_path=build_dir if completed.returncode == 0 else None,
        )
        if not build.success:
            return PreparedProgram(success=False, build=build)
        main_class = spec.entry or spec.main_source.stem
        return PreparedProgram(success=True, build=build, argv=(java, "-cp", str(build_dir), main_class), cwd=build_dir)

    def run(
        self,
        program: PreparedProgram,
        args: tuple[str, ...],
        stdin: str,
        timeout_seconds: int,
    ) -> ProcessOutcome:
        return run_process([*program.argv, *args], stdin, timeout_seconds, program.cwd, encoding="utf-8")

    def _find(self) -> tuple[str, str] | None:
        if self._detected_javac is not None and self._detected_java is not None:
            return self._detected_javac, self._detected_java
        javac = self._find_javac()
        if javac is None:
            return None
        java = self._java_near_javac(Path(javac)) or self._find_java()
        if java is None:
            return None
        self._detected_javac = javac
        self._detected_java = java
        return javac, java

    def _find_javac(self) -> str | None:
        candidates = [self._manual_javac] if self._manual_javac else []
        candidates.append("javac")
        for candidate in candidates:
            if candidate is None:
                continue
            resolved = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
            if resolved and self._valid_tool((resolved,), "-version"):
                return resolved
        return None

    def _find_java(self) -> str | None:
        for candidate in self._java_candidates:
            resolved = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
            if resolved and self._valid_tool((resolved,), "-version"):
                return resolved
        return None

    @staticmethod
    def _java_near_javac(javac: Path) -> str | None:
        java = javac.with_name("java.exe" if javac.suffix.lower() == ".exe" else "java")
        if java.is_file() and JavaRuntime._valid_tool((str(java),), "-version"):
            return str(java)
        return None

    @staticmethod
    def _valid_tool(command: tuple[str, ...], *args: str) -> bool:
        try:
            completed = subprocess.run(
                [*command, *args],
                capture_output=True,
                text=True,
                check=False,
                timeout=PROBE_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0
