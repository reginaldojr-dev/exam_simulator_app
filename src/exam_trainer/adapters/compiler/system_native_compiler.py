from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from exam_trainer.ports.compiler_port import CompilationResult


class SystemNativeCompiler:
    def __init__(
        self,
        *,
        language_name: str,
        candidates: tuple[str, ...],
        probe_filename: str,
        probe_source: str,
        flags: tuple[str, ...] = (),
        manual_compiler: str | None = None,
    ) -> None:
        self._language_name = language_name
        self._candidates = candidates
        self._probe_filename = probe_filename
        self._probe_source = probe_source
        self._flags = flags
        self._manual_compiler = manual_compiler
        self._detected_compiler: str | None = None

    def is_available(self) -> bool:
        return self.find_compiler() is not None

    def cached_compiler(self) -> str | None:
        return self._detected_compiler

    def current_compiler(self) -> str | None:
        return self._detected_compiler or self._manual_compiler

    def find_compiler(self) -> str | None:
        if self._detected_compiler is not None:
            return self._detected_compiler
        for candidate in self._candidate_paths():
            if self._is_compatible_compiler(candidate):
                self._detected_compiler = str(candidate)
                return self._detected_compiler
        return None

    def redetect(self) -> str | None:
        self._detected_compiler = None
        return self.find_compiler()

    def set_manual_compiler(self, compiler_path: str | Path | None) -> None:
        self._manual_compiler = None if compiler_path is None else str(compiler_path)
        self._detected_compiler = None

    def validate_compiler(self, compiler_path: str | Path) -> bool:
        path = Path(compiler_path)
        try:
            is_file = path.is_file()
        except OSError:
            return False
        return is_file and self._is_compatible_compiler(path)

    def compile(self, source_files: list[Path], output_path: Path) -> CompilationResult:
        compiler = self.find_compiler()
        if compiler is None:
            return CompilationResult(
                success=False,
                output=f"Nenhum compilador {self._language_name} compatível foi encontrado.",
            )
        command = (
            compiler,
            *self._flags,
            *(str(source_file) for source_file in source_files),
            "-o",
            str(output_path),
        )
        completed = subprocess.run(list(command), capture_output=True, text=True, check=False)
        output = completed.stdout + completed.stderr
        return CompilationResult(
            success=completed.returncode == 0,
            output=output,
            command=command,
            executable_path=output_path if completed.returncode == 0 else None,
        )

    def _candidate_paths(self) -> list[Path]:
        candidates: list[Path] = []
        if self._manual_compiler:
            candidates.append(Path(self._manual_compiler))
        for candidate in self._candidates:
            resolved = shutil.which(candidate)
            if resolved is not None:
                candidates.append(Path(resolved))
        candidates.extend(self._windows_winget_candidates())

        unique: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate).lower()
            try:
                is_file = candidate.is_file()
            except OSError:
                is_file = False
            if key not in seen and is_file:
                unique.append(candidate)
                seen.add(key)
        return sorted(unique, key=lambda path: str(path).lower())

    def _windows_winget_candidates(self) -> list[Path]:
        if sys.platform != "win32":
            return []
        local_app_data = Path.home() / "AppData" / "Local"
        roots = [
            local_app_data / "Microsoft" / "WinGet" / "Packages",
            local_app_data / "Programs",
        ]
        matches: list[Path] = []
        for root in roots:
            if not root.is_dir():
                continue
            for name in self._candidates:
                exe = name if name.endswith(".exe") else f"{name}.exe"
                matches.extend(root.rglob(exe))
        return matches

    def _is_compatible_compiler(self, compiler: Path) -> bool:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / self._probe_filename
            executable = root / ("probe.exe" if sys.platform == "win32" else "probe")
            source.write_text(self._probe_source, encoding="utf-8")
            command = [str(compiler), *self._flags, str(source), "-o", str(executable)]
            try:
                completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                return False
            if completed.returncode != 0 or not executable.exists():
                return False
            try:
                probe = subprocess.run([str(executable)], capture_output=True, text=True, check=False, timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                return False
            return probe.returncode == 0 and probe.stdout == "OK\n"
