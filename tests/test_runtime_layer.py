"""Passo 5b: GenericGrader -> ExecutionStrategy -> RuntimeRegistry -> runtime."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PurePath

from exam_trainer.adapters.compiler.system_c_compiler import SystemCCompiler
from exam_trainer.adapters.grader.generic_grader import GenericGrader
from exam_trainer.adapters.runtime.c_runtime import CRuntime
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry, UnsupportedLanguageError
from exam_trainer.domain.exercise_definition import (
    ExecutionDefinition,
    ExerciseDefinition,
    LimitsDefinition,
    ReferenceDefinition,
    SubmissionDefinition,
    TestCaseDefinition,
    TestDefinition,
)
from exam_trainer.domain.grading import GradingPolicy
from exam_trainer.ports.compiler_port import CompilationResult
from exam_trainer.ports.grader_port import GradingRequest
from exam_trainer.ports.runtime_port import LanguageRuntime, PreparedProgram, ProcessOutcome, ProgramSpec


class ScriptedRuntime:
    """Runtime falso: o "programa" é o texto do arquivo; roda como função Python simples.

    Formatos do arquivo: `echo` (repete args), `upper` (args em maiúsculas), `sleep`
    (timeout), `crash` (exit 1), `broken` (falha na preparação).
    """

    language = "toy"
    display_name = "Toy"

    def __init__(self) -> None:
        self.prepared: list[ProgramSpec] = []
        self.runs = 0

    def is_ready(self) -> bool:
        return True

    def check_available(self) -> bool:
        return True

    def current_tool(self) -> str | None:
        return "toy"

    def redetect(self) -> str | None:
        return "toy"

    def configure_manual(self, path: Path) -> str:
        return str(path)

    def prepare(self, spec: ProgramSpec, build_dir: Path, name: str) -> PreparedProgram:
        self.prepared.append(spec)
        kind = spec.main_source.read_text(encoding="utf-8").strip()
        build = CompilationResult(success=kind != "broken", output="toy build", command=("toy", name))
        return PreparedProgram(success=build.success, build=build, argv=(kind,))

    def run(self, program: PreparedProgram, args: tuple[str, ...], stdin: str, timeout_seconds: int) -> ProcessOutcome:
        self.runs += 1
        kind = program.argv[0]
        if kind == "sleep":
            return ProcessOutcome(timed_out=True)
        if kind == "crash":
            return ProcessOutcome(stderr="boom", exit_code=1)
        text = " ".join(args)
        return ProcessOutcome(stdout=(text.upper() if kind == "upper" else text) + "\n", exit_code=0)


def toy_definition(**overrides: object) -> ExerciseDefinition:
    values: dict[str, object] = {
        "id": "toy",
        "name": "Toy",
        "subject": PurePath("subject.md"),
        "submission": SubmissionDefinition("solution.toy"),
        "execution": ExecutionDefinition(type="program_output"),
        "tests": TestDefinition(generator="random_arguments", expectation="reference_output"),
        "limits": LimitsDefinition(timeout_seconds=1),
        "reference": ReferenceDefinition(source=PurePath("reference.toy")),
        "language": "toy",
    }
    values.update(overrides)
    return ExerciseDefinition(**values)  # type: ignore[arg-type]


class GenericGraderTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.exercise = self.root / "exercise"
        self.workspace = self.root / "workspace"
        self.exercise.mkdir()
        self.workspace.mkdir()
        (self.exercise / "reference.toy").write_text("upper", encoding="utf-8")
        self.runtime = ScriptedRuntime()
        self.grader = GenericGrader(RuntimeRegistry([self.runtime]))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def grade(self, submission: str, policy: GradingPolicy | None = None, seed: int = 5, **overrides):
        (self.workspace / "solution.toy").write_text(submission, encoding="utf-8")
        return self.grader.grade(
            GradingRequest(
                definition=toy_definition(**overrides),
                exercise_path=self.exercise,
                workspace_path=self.workspace,
                policy=policy or GradingPolicy.training(),
                seed=seed,
            )
        )

    def test_runtime_is_a_language_runtime(self) -> None:
        self.assertIsInstance(self.runtime, LanguageRuntime)
        self.assertIsInstance(CRuntime(SystemCCompiler()), LanguageRuntime)

    def test_expected_output_comes_from_the_reference_program(self) -> None:
        self.assertTrue(self.grade("upper").passed)
        failed = self.grade("echo")
        self.assertFalse(failed.passed)
        self.assertEqual(self.runtime.prepared[-1].main_source.name, "reference.toy")

    def test_fail_fast_in_exam_and_full_run_in_training(self) -> None:
        exam = self.grade("echo", policy=GradingPolicy.exam())
        self.assertEqual(len(exam.test_results), 1)
        training = self.grade("echo", policy=GradingPolicy.training())
        self.assertGreater(len(training.test_results), 1)

    def test_timeout_and_runtime_error_are_failures(self) -> None:
        timeout = self.grade("sleep")
        self.assertFalse(timeout.passed)
        self.assertTrue(timeout.test_results[0].timed_out)
        crash = self.grade("crash")
        self.assertFalse(crash.passed)
        self.assertEqual(crash.test_results[0].exit_code, 1)

    def test_preparation_failure_stops_before_running(self) -> None:
        result = self.grade("broken")
        self.assertFalse(result.passed)
        self.assertEqual(result.test_results, ())
        self.assertEqual(self.runtime.runs, 0)

    def test_same_seed_same_cases(self) -> None:
        first = [case.test_case.args for case in self.grade("upper", seed=9).test_results]
        second = [case.test_case.args for case in self.grade("upper", seed=9).test_results]
        self.assertEqual(first, second)

    def test_literal_cases_without_reference(self) -> None:
        result = self.grade(
            "echo",
            reference=None,
            tests=TestDefinition(
                generator="fixed_cases",
                expectation="literal",
                cases=(TestCaseDefinition(args=("a", "b"), expected="a b\n"),),
            ),
        )
        self.assertTrue(result.passed)

    def test_unknown_language_is_a_clear_failure_not_a_crash(self) -> None:
        result = self.grade("upper", language="cobol")
        self.assertFalse(result.passed)
        self.assertIn("cobol", result.compile_output)
        with self.assertRaises(UnsupportedLanguageError):
            RuntimeRegistry().get("cobol")

    def test_missing_harness_is_reported(self) -> None:
        result = self.grade(
            "upper",
            execution=ExecutionDefinition(type="function_call", fixture=PurePath("missing/main.c")),
        )
        self.assertFalse(result.passed)
        self.assertIn("harness not found", result.compile_output)


@unittest.skipUnless(SystemCCompiler().is_available(), "no compatible C compiler")
class CRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        compiler = SystemCCompiler()
        self.runtime = CRuntime(compiler, manager=compiler)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def program(self, name: str, body: str) -> PreparedProgram:
        source = self.root / f"{name}.c"
        source.write_text(body, encoding="utf-8")
        return self.runtime.prepare(ProgramSpec(main_source=source), self.root / "build", name)

    def test_compiles_and_runs_without_shell(self) -> None:
        program = self.program(
            "echo",
            '#include <stdio.h>\nint main(int c, char **v){for(int i=1;i<c;i++)printf("%s|",v[i]);return 0;}\n',
        )
        self.assertTrue(program.success, program.build.output)
        self.assertTrue(self.runtime.is_ready())
        # argumento com metacaracteres de shell chega literal (nada de shell)
        outcome = self.runtime.run(program, ("a b", "$(echo x)", ";ls"), "", 2)
        self.assertEqual(outcome.stdout, "a b|$(echo x)|;ls|")
        self.assertEqual(outcome.exit_code, 0)

    def test_compile_error_timeout_and_exit_code(self) -> None:
        self.assertFalse(self.program("bad", "int main(void){ return x; }\n").success)
        loop = self.program("loop", "int main(void){ for(;;){} }\n")
        self.assertTrue(self.runtime.run(loop, (), "", 1).timed_out)
        crash = self.program("crash", "int main(void){ return 3; }\n")
        self.assertEqual(self.runtime.run(crash, (), "", 1).exit_code, 3)


class PreflightByLanguageTest(unittest.TestCase):
    def test_pack_language_without_runtime_is_blocked(self) -> None:
        from test_exam_rules import build_pack
        from exam_trainer.adapters.editor.subprocess_editor import SubprocessEditor, SubprocessEditorFactory
        from exam_trainer.adapters.pack.local_pack_catalog import LocalPackCatalog
        from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter
        from exam_trainer.adapters.persistence.sqlite_progress_repository import SQLiteProgressRepository
        from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
        from exam_trainer.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
        from exam_trainer.application.use_cases.mvp_coordinator import MVPTrainerCoordinator

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_pack(root / "bundled" / "cpack", "cpack", levels=1)
            (root / "workspace").mkdir()
            coordinator = MVPTrainerCoordinator(
                pack_catalog=LocalPackCatalog(root / "managed", bundled_packs_dir=root / "bundled"),
                progress_repository=SQLiteProgressRepository(SQLiteStore(root / "db.sqlite3")),
                workspace=LocalExerciseWorkspace(),
                grader=GenericGrader(RuntimeRegistry([ScriptedRuntime()])),
                editor=SubprocessEditor("definitely-not-used"),
                pack_importer=LocalPackImporter(root / "managed"),
                workspace_root=root / "workspace",
                runtimes=RuntimeRegistry([ScriptedRuntime()]),
                editor_factory=SubprocessEditorFactory(),
            )
            self.assertEqual(coordinator.pack_language("cpack"), "c")
            preflight = coordinator.preflight_exam("cpack")
            self.assertFalse(preflight.ok)
            self.assertIn("'c'", preflight.message)
            self.assertTrue(coordinator.preflight_runtime("toy").ok)


if __name__ == "__main__":
    unittest.main()
