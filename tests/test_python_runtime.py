"""Passo 6: runtime Python + pack autoral python-basics."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from exam_trainer.adapters.grader.generic_grader import GenericGrader
from exam_trainer.adapters.pack.local_pack_catalog import LocalPackCatalog
from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter
from exam_trainer.adapters.runtime.python_runtime import PythonRuntime
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry
from exam_trainer.domain.grading import GradingPolicy
from exam_trainer.ports.grader_port import GradingRequest
from exam_trainer.ports.runtime_port import LanguageRuntime, ProgramSpec

REPO = Path(__file__).resolve().parent.parent
PYTHON_BASICS = REPO / "examples" / "packs" / "python-basics"
SYSTEM_PYTHON = PythonRuntime().check_available()


class PythonRuntimeUnitTest(unittest.TestCase):
    def test_is_a_language_runtime(self) -> None:
        self.assertIsInstance(PythonRuntime(candidates=[]), LanguageRuntime)

    def test_no_candidates_means_not_available_and_no_crash(self) -> None:
        runtime = PythonRuntime(candidates=[("definitely-not-a-python",)])
        self.assertFalse(runtime.check_available())
        self.assertFalse(runtime.is_ready())
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "x.py"
            source.write_text("print(1)\n", encoding="utf-8")
            program = runtime.prepare(ProgramSpec(main_source=source), Path(temp_dir) / "build", "x")
        self.assertFalse(program.success)
        self.assertIn("Python", program.build.output)

    def test_manual_selection_rejects_non_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake = Path(temp_dir) / "python.exe"
            fake.write_text("not a program", encoding="utf-8")
            with self.assertRaises(ValueError):
                PythonRuntime(candidates=[]).configure_manual(fake)

    def test_pack_python_harness_is_refused(self) -> None:
        runtime = PythonRuntime(candidates=[])
        runtime._detected = sys.executable  # não roda nada: a recusa vem antes
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "x.py"
            source.write_text("", encoding="utf-8")
            program = runtime.prepare(ProgramSpec(main_source=source, harness=source), Path(temp_dir), "x")
        self.assertFalse(program.success)
        self.assertIn("harness", program.build.output)

    @unittest.skipUnless(SYSTEM_PYTHON, "no system Python")
    def test_never_uses_the_frozen_app_executable(self) -> None:
        interpreter = PythonRuntime().redetect()
        self.assertIsNotNone(interpreter)
        with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(sys, "executable", interpreter):
            self.assertIsNone(PythonRuntime.probe((interpreter,)))


@unittest.skipUnless(SYSTEM_PYTHON, "no system Python")
class PythonBasicsPackTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        shutil.copytree(PYTHON_BASICS, self.root / "bundled" / "python-basics")
        self.catalog = LocalPackCatalog(self.root / "managed", bundled_packs_dir=self.root / "bundled")
        self.runtime = PythonRuntime()
        self.grader = GenericGrader(RuntimeRegistry([self.runtime]))
        self.refs = {ref.definition.id: ref for ref in self.catalog.list_exercises("python-basics")}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def grade(self, exercise_id: str, code: str, policy: GradingPolicy | None = None):
        ref = self.refs[exercise_id]
        workspace = self.root / "ws" / exercise_id
        shutil.rmtree(workspace, ignore_errors=True)
        workspace.mkdir(parents=True)
        (workspace / ref.definition.submission.filename).write_text(code, encoding="utf-8")
        return self.grader.grade(
            GradingRequest(
                definition=ref.definition,
                exercise_path=ref.content_path,
                workspace_path=workspace,
                policy=policy or GradingPolicy.training(),
                seed=11,
            )
        )

    def test_pack_is_v2_python_and_imports(self) -> None:
        report = LocalPackImporter(self.root / "managed").inspect_pack(PYTHON_BASICS)
        self.assertEqual((report.pack.schema_version, report.pack.language), (2, "python"))
        self.assertEqual(report.exercise_count, 5)
        self.assertTrue(all(name.endswith(".py") for name in report.executable_files))
        kinds = {ref.definition.execution.type for ref in self.refs.values()}
        self.assertEqual(kinds, {"program_output", "function_call"})

    def test_references_pass(self) -> None:
        for exercise_id, ref in self.refs.items():
            if ref.definition.reference is None:
                continue
            code = (ref.content_path / ref.definition.reference.source).read_text(encoding="utf-8")
            with self.subTest(exercise_id):
                result = self.grade(exercise_id, code)
                self.assertTrue(result.passed, result.trace_data.as_text())

    def test_program_output_pass_and_fail(self) -> None:
        self.assertTrue(self.grade("count_args", "import sys\nprint(len(sys.argv) - 1)\n").passed)
        failed = self.grade("count_args", "import sys\nprint(len(sys.argv))\n")
        self.assertFalse(failed.passed)
        self.assertTrue(failed.test_results)

    def test_function_call_pass_and_fail_with_literal_cases(self) -> None:
        good = "def max_value(values):\n    best = None\n    for v in values:\n        if best is None or v > best:\n            best = v\n    return best\n"
        self.assertTrue(self.grade("max_value", good).passed)
        self.assertFalse(self.grade("max_value", "def max_value(values):\n    return values[0]\n").passed)

    def test_string_args_format(self) -> None:
        self.assertTrue(self.grade("reverse_text", "def reverse_text(text):\n    return ''.join(reversed(text))\n").passed)
        self.assertFalse(self.grade("reverse_text", "def reverse_text(text):\n    return text\n").passed)

    def test_syntax_error_is_a_preparation_failure(self) -> None:
        result = self.grade("add_numbers", "def add(a, b)\n    return a + b\n")
        self.assertFalse(result.passed)
        self.assertEqual(result.test_results, ())
        self.assertIn("SyntaxError", result.compile_output)

    def test_runtime_error_fails_with_traceback_in_stderr(self) -> None:
        result = self.grade("add_numbers", "def add(a, b):\n    return a / 0\n", GradingPolicy.exam())
        self.assertFalse(result.passed)
        self.assertEqual(result.test_results[0].exit_code, 1)
        self.assertIn("ZeroDivisionError", result.test_results[0].stderr)

    def test_missing_entry_function_fails(self) -> None:
        result = self.grade("add_numbers", "def plus(a, b):\n    return a + b\n", GradingPolicy.exam())
        self.assertFalse(result.passed)
        self.assertIn("function not found", result.test_results[0].stderr)

    def test_timeout(self) -> None:
        result = self.grade("count_args", "while True:\n    pass\n", GradingPolicy.exam())
        self.assertFalse(result.passed)
        self.assertTrue(result.test_results[0].timed_out)

    def test_runs_isolated(self) -> None:
        code = "import sys\nprint(len(sys.argv) - 1 if sys.flags.isolated and sys.flags.utf8_mode else -1)\n"
        self.assertTrue(self.grade("count_args", code).passed)

    def test_coordinator_trains_python_pack_with_language_preflight(self) -> None:
        from exam_trainer.adapters.editor.subprocess_editor import SubprocessEditor, SubprocessEditorFactory
        from exam_trainer.adapters.persistence.sqlite_progress_repository import SQLiteProgressRepository
        from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
        from exam_trainer.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
        from exam_trainer.application.use_cases.mvp_coordinator import MVPTrainerCoordinator

        (self.root / "workspace").mkdir()
        registry = RuntimeRegistry([self.runtime])
        coordinator = MVPTrainerCoordinator(
            pack_catalog=self.catalog,
            progress_repository=SQLiteProgressRepository(SQLiteStore(self.root / "db.sqlite3")),
            workspace=LocalExerciseWorkspace(),
            grader=GenericGrader(registry),
            editor=SubprocessEditor("definitely-not-used"),
            pack_importer=LocalPackImporter(self.root / "managed"),
            workspace_root=self.root / "workspace",
            runtimes=registry,
            editor_factory=SubprocessEditorFactory(),
        )
        self.assertTrue(coordinator.preflight_exam("python-basics").ok)
        active = coordinator.prepare_exercise(self.refs["shout_args"], overwrite=True)
        self.assertEqual(active.submission_path.name, "shout_args.py")
        active.submission_path.write_text('import sys\nprint(" ".join(a.upper() for a in sys.argv[1:]))\n', encoding="utf-8")
        outcome = coordinator.submit_training(active)
        self.assertTrue(outcome.result.passed, outcome.result.trace_data.as_text())
        self.assertTrue(coordinator._progress_repository.progress_by_exercise("python-basics")["shout_args"].best_passed)


if __name__ == "__main__":
    unittest.main()
