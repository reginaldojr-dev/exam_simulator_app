from __future__ import annotations

import contextlib
import importlib.util
import io
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


if __name__ == "__main__":
    unittest.main()
