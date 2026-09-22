from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from exam_trainer.adapters.compiler.system_c_compiler import SystemCCompiler
from exam_trainer.adapters.editor.subprocess_editor import (
    EditorLaunchError,
    SubprocessEditor,
    validate_editor_executable,
)


class ProbeCompiler(SystemCCompiler):
    def __init__(self, candidates: list[Path], valid: set[str]) -> None:
        super().__init__()
        self._test_candidates = candidates
        self._valid = valid

    def _candidate_paths(self) -> list[Path]:
        return sorted(self._test_candidates, key=self._candidate_priority)

    def _is_compatible_compiler(self, compiler: Path) -> bool:
        return str(compiler) in self._valid


class WindowsIntegrationAdaptersTest(unittest.TestCase):
    def test_prefers_llvm_mingw_over_other_clang(self) -> None:
        msvc_clang = Path("C:/Program Files/LLVM/bin/clang.exe")
        mingw_clang = Path("C:/Users/junio/AppData/Local/Microsoft/WinGet/Packages/llvm-mingw/bin/clang.exe")
        compiler = ProbeCompiler([msvc_clang, mingw_clang], {str(mingw_clang)})

        self.assertEqual(compiler.find_compiler(), str(mingw_clang))

    def test_falls_back_to_gcc_when_clang_is_invalid(self) -> None:
        clang = Path("C:/Program Files/LLVM/bin/clang.exe")
        gcc = Path("C:/mingw64/bin/gcc.exe")
        compiler = ProbeCompiler([clang, gcc], {str(gcc)})

        self.assertEqual(compiler.find_compiler(), str(gcc))

    def test_manual_compiler_accepts_only_valid_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            valid = Path(temp_dir) / "clang.exe"
            invalid = Path(temp_dir) / "bad-clang.exe"
            valid.write_text("", encoding="utf-8")
            invalid.write_text("", encoding="utf-8")
            compiler = ProbeCompiler([invalid], {str(valid)})

            self.assertTrue(compiler.validate_compiler(valid))
            self.assertFalse(compiler.validate_compiler(invalid))

    def test_editor_rejects_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(EditorLaunchError):
                validate_editor_executable(temp_dir)

    def test_editor_accepts_executable_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / "Code.exe"
            executable.write_text("", encoding="utf-8")

            self.assertEqual(validate_editor_executable(executable), executable)

    def test_editor_passes_workspace_as_separate_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / "Code.exe"
            workspace = Path(temp_dir) / "workspace"
            executable.write_text("", encoding="utf-8")
            workspace.mkdir()

            with patch("exam_trainer.adapters.editor.subprocess_editor.subprocess.Popen") as popen:
                SubprocessEditor(str(executable), "VS Code").open_directory(workspace)

            popen.assert_called_once()
            self.assertEqual(popen.call_args.args[0], [str(executable), str(workspace)])


if __name__ == "__main__":
    unittest.main()
