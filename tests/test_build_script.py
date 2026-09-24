from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def _load_build_module():
    spec = importlib.util.spec_from_file_location("project_build_script", ROOT / "build.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _PolicyBlocked(OSError):
    winerror = 4551


class BuildScriptLaunchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.build = _load_build_module()

    def test_policy_block_is_reported_as_successful_build(self) -> None:
        output = io.StringIO()
        with mock.patch.object(self.build, "EXE_PATH", ROOT / "build.py"), \
             mock.patch.object(self.build.subprocess, "Popen", side_effect=_PolicyBlocked("blocked")), \
             contextlib.redirect_stdout(output):
            code = self.build.run_executable()

        text = output.getvalue()
        self.assertEqual(code, self.build.EXIT_LAUNCH_BLOCKED)
        self.assertIn("Build concluído com sucesso.", text)
        self.assertIn("política de Controle de Aplicativo", text)
        self.assertNotIn("Traceback", text)

    def test_other_launch_errors_are_reported_without_traceback(self) -> None:
        output = io.StringIO()
        with mock.patch.object(self.build, "EXE_PATH", ROOT / "build.py"), \
             mock.patch.object(self.build.subprocess, "Popen", side_effect=PermissionError("denied")), \
             contextlib.redirect_stdout(output):
            code = self.build.run_executable()

        self.assertEqual(code, self.build.EXIT_LAUNCH_BLOCKED)
        self.assertIn("Não foi possível abrir o executável", output.getvalue())


class BuildScriptInputsTest(unittest.TestCase):
    """Hash, ignorados e troca segura do exe, num projeto falso em pasta temporária."""

    def setUp(self) -> None:
        self.build = _load_build_module()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for relative in (
            "src/exam_trainer/main.py",
            "src/exam_trainer/adapters/workspace/local.py",
            "examples/packs/demo/pack.json",
            "README.md",
            "pyproject.toml",
            "Exam Trainer.spec",
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relative, encoding="utf-8")
        build = self.build
        dist = self.root / "dist"
        patches = {
            "ROOT": self.root,
            "BUILD_DIR": self.root / "build",
            "DIST_DIR": dist,
            "STAGING_DIR": self.root / "build" / "_staging",
            "SPEC_FILE": self.root / "Exam Trainer.spec",
            "EXE_PATH": dist / build.EXE_NAME,
            "STATE_FILE": dist / ".build_state.json",
            "SOURCE_DIRS": (self.root / "src", self.root / "examples"),
            "SOURCE_FILES": (self.root / "Exam Trainer.spec", self.root / "pyproject.toml", self.root / "README.md"),
        }
        for name, value in patches.items():
            patcher = mock.patch.object(build, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def write(self, relative: str, text: str = "x") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def inputs(self) -> set[str]:
        return {path.relative_to(self.root).as_posix() for path in self.build.iter_build_inputs()}

    def test_local_folder_is_ignored_only_at_root(self) -> None:
        self.write("_local/workspace/training/x/x.c")
        self.write("src/exam_trainer/__pycache__/main.cpython-313.pyc")
        inputs = self.inputs()
        self.assertIn("src/exam_trainer/adapters/workspace/local.py", inputs)
        self.assertFalse(any(item.startswith("_local/") for item in inputs))
        self.assertFalse(any("__pycache__" in item for item in inputs))

    def test_private_packs_folder_does_not_change_the_hash(self) -> None:
        before = self.build.calculate_source_hash()
        self.write("_local/packs/rank02-original/level0/x/exercise.json", "private")
        self.assertEqual(before, self.build.calculate_source_hash())
        self.write("src/exam_trainer/new_module.py")
        self.assertNotEqual(before, self.build.calculate_source_hash())

    def test_environment_versions_are_part_of_the_hash(self) -> None:
        before = self.build.calculate_source_hash()
        with mock.patch.object(self.build, "environment_fingerprint", return_value={"pyinstaller": "0.0"}):
            self.assertNotEqual(before, self.build.calculate_source_hash())

    def _fake_pyinstaller(self, returncode: int, content: str = "new exe"):
        build = self.build

        def run(command, cwd=None):
            if returncode == 0:
                dist = Path(command[command.index("--distpath") + 1])
                dist.mkdir(parents=True, exist_ok=True)
                (dist / build.EXE_NAME).write_text(content, encoding="utf-8")
            return mock.Mock(returncode=returncode)

        return mock.patch.object(build.subprocess, "run", side_effect=run)

    def test_failed_build_keeps_the_previous_executable(self) -> None:
        self.build.EXE_PATH.parent.mkdir(parents=True)
        self.build.EXE_PATH.write_text("old exe", encoding="utf-8")
        with self._fake_pyinstaller(returncode=1), contextlib.redirect_stdout(io.StringIO()) as out:
            code = self.build.main(["--force"])
        self.assertNotEqual(code, 0)
        self.assertEqual(self.build.EXE_PATH.read_text(encoding="utf-8"), "old exe")
        self.assertIn("anterior foi mantido", out.getvalue())

    def test_successful_build_replaces_and_then_skips_until_something_changes(self) -> None:
        with self._fake_pyinstaller(returncode=0) as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.build.main([]), 0)
            self.assertEqual(self.build.EXE_PATH.read_text(encoding="utf-8"), "new exe")
            self.assertEqual(run.call_count, 1)
            self.assertEqual(self.build.main([]), 0)  # nada mudou: não chama PyInstaller
            self.assertEqual(run.call_count, 1)
            self.assertEqual(self.build.main(["--force"]), 0)
            self.assertEqual(run.call_count, 2)
            self.write("examples/packs/demo/level0/new.json")
            self.assertEqual(self.build.main([]), 0)
            self.assertEqual(run.call_count, 3)

    def test_run_without_changes_opens_without_rebuilding(self) -> None:
        with self._fake_pyinstaller(returncode=0) as run, contextlib.redirect_stdout(io.StringIO()):
            self.build.main([])
            with mock.patch.object(self.build.subprocess, "Popen") as popen:
                self.assertEqual(self.build.main(["--run"]), 0)
        self.assertEqual(run.call_count, 1)
        popen.assert_called_once()

    def test_exe_in_use_is_reported_and_new_build_is_kept_aside(self) -> None:
        with self._fake_pyinstaller(returncode=0), \
             mock.patch.object(self.build.os, "replace", side_effect=PermissionError("in use")), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            code = self.build.main([])
        self.assertEqual(code, self.build.EXIT_REPLACE_FAILED)
        self.assertIn("Feche o app", out.getvalue())
        self.assertFalse(self.build.STATE_FILE.exists())

    def test_spec_bundles_docs_and_never_the_local_folder(self) -> None:
        spec = (ROOT / "Exam Trainer.spec").read_text(encoding="utf-8")
        self.assertIn("('README.md', '.')", spec)
        self.assertIn("exam_trainer/resources", spec)
        self.assertNotIn("('_local'", spec)


if __name__ == "__main__":
    unittest.main()

