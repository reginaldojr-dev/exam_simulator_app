"""Runtime Python: usa o Python INSTALADO no sistema (nunca o Python embutido no exe).

- detecção: candidatos do PATH (`py -3` no Windows, `python3`, `python`) validados por um
  probe real (o processo precisa rodar e reportar versão >= 3.9);
- seleção manual nas Configurações (também passa pelo probe);
- preparação: checagem de sintaxe com `py_compile` (o .pyc vai para a pasta .build);
- execução: `python -I -B -X utf8` (modo isolado: ignora variáveis PYTHON*, site do usuário
  e o diretório atual no sys.path). Isso NÃO é sandbox: o código roda com as permissões do
  usuário;
- `function_call`: o harness é fornecido pelo APP (`python_harness.py`); o pack declara só
  `entry` e `args_format`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from exam_trainer.adapters.runtime import python_harness
from exam_trainer.adapters.runtime.process import run_process
from exam_trainer.ports.compiler_port import CompilationResult
from exam_trainer.ports.runtime_port import PreparedProgram, ProcessOutcome, ProgramSpec

MIN_VERSION = (3, 9)
PROBE_TIMEOUT_SECONDS = 10
ISOLATED_FLAGS = ("-I", "-B", "-X", "utf8")
PROBE_SCRIPT = "import sys; print(sys.executable); print('%d.%d' % sys.version_info[:2])"
SYNTAX_CHECK = (
    "import py_compile, sys; "
    "py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)"
)
HARNESS_NAME = "_exam_trainer_harness.py"


def default_candidates() -> list[tuple[str, ...]]:
    if sys.platform == "win32":
        return [("py", "-3"), ("python",), ("python3",)]
    return [("python3",), ("python",)]


class PythonRuntime:
    language = "python"
    display_name = "Python"

    def __init__(
        self,
        manual_python: str | None = None,
        candidates: list[tuple[str, ...]] | None = None,
    ) -> None:
        self._manual = manual_python
        self._candidates = candidates if candidates is not None else default_candidates()
        self._detected: str | None = None

    # --------------------------------------------------------- disponibilidade
    def is_ready(self) -> bool:
        return self._detected is not None

    def current_tool(self) -> str | None:
        return self._detected or self._manual

    def check_available(self) -> bool:
        return self._find() is not None

    def redetect(self) -> str | None:
        self._detected = None
        return self._find()

    def configure_manual(self, path: Path) -> str:
        interpreter = self.probe((str(path),))
        if interpreter is None:
            raise ValueError(
                f"Nenhum Python {MIN_VERSION[0]}.{MIN_VERSION[1]}+ utilizável foi encontrado nesse caminho."
            )
        self._manual = str(path)
        self._detected = interpreter
        return str(path)

    def _find(self) -> str | None:
        if self._detected is not None:
            return self._detected
        commands: list[tuple[str, ...]] = []
        if self._manual:
            commands.append((self._manual,))
        commands.extend(self._candidates)
        for command in commands:
            interpreter = self.probe(command)
            if interpreter is not None:
                self._detected = interpreter
                return interpreter
        return None

    @staticmethod
    def probe(command: tuple[str, ...]) -> str | None:
        """Roda o interpretador de verdade. Retorna o caminho absoluto dele, ou None."""
        executable = shutil.which(command[0]) or (command[0] if Path(command[0]).is_file() else None)
        if executable is None:
            return None
        if sys.platform == "win32" and not _looks_like_windows_executable(Path(executable)):
            return None
        if getattr(sys, "frozen", False) and Path(executable).resolve() == Path(sys.executable).resolve():
            return None  # nunca o próprio exe do app
        try:
            completed = subprocess.run(
                [executable, *command[1:], "-I", "-c", PROBE_SCRIPT],
                capture_output=True,
                text=True,
                timeout=PROBE_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        lines = completed.stdout.strip().splitlines()
        if completed.returncode != 0 or len(lines) < 2:
            return None
        try:
            version = tuple(int(part) for part in lines[-1].split("."))
        except ValueError:
            return None
        if version < MIN_VERSION:
            return None
        interpreter = lines[-2].strip()
        return interpreter if interpreter and Path(interpreter).is_file() else None

    # ------------------------------------------------------------- execução
    def prepare(self, spec: ProgramSpec, build_dir: Path, name: str) -> PreparedProgram:
        python = self._find()
        if python is None:
            return PreparedProgram(
                success=False,
                build=CompilationResult(success=False, output="Python não encontrado. Configure em Configurações > Python."),
            )
        if spec.harness is not None:
            return PreparedProgram(
                success=False,
                build=CompilationResult(success=False, output="Python não usa harness do pack (o app fornece o harness)."),
            )
        build_dir.mkdir(parents=True, exist_ok=True)
        command = (python, *ISOLATED_FLAGS, "-c", SYNTAX_CHECK, str(spec.main_source), str(build_dir / f"{name}.pyc"))
        check = run_process(list(command), "", PROBE_TIMEOUT_SECONDS, cwd=build_dir, encoding="utf-8")
        output = (check.stdout + check.stderr).strip()
        build = CompilationResult(
            success=check.exit_code == 0 and not check.timed_out,
            output=output or ("syntax check timed out" if check.timed_out else ""),
            command=("python", "-m", "py_compile", str(spec.main_source)),
        )
        if not build.success:
            return PreparedProgram(success=False, build=build)
        if spec.entry is None:
            argv = (python, *ISOLATED_FLAGS, str(spec.main_source))
        else:
            harness = build_dir / HARNESS_NAME
            harness.write_text(python_harness.HARNESS_SOURCE, encoding="utf-8")
            argv = (
                python,
                *ISOLATED_FLAGS,
                str(harness),
                str(spec.main_source),
                spec.entry,
                spec.args_format or "json",
            )
        return PreparedProgram(success=True, build=build, argv=argv, cwd=build_dir)

    def run(
        self,
        program: PreparedProgram,
        args: tuple[str, ...],
        stdin: str,
        timeout_seconds: int,
    ) -> ProcessOutcome:
        return run_process([*program.argv, *args], stdin, timeout_seconds, program.cwd, encoding="utf-8")


def _looks_like_windows_executable(path: Path) -> bool:
    if path.suffix.lower() != ".exe":
        return True
    try:
        with path.open("rb") as handle:
            return handle.read(2) == b"MZ"
    except OSError:
        return False
