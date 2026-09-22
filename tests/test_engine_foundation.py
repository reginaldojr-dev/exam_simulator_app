from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from exam_trainer.adapters.compiler.system_c_compiler import SystemCCompiler
from exam_trainer.adapters.grader.generic_c_grader import GenericCGrader
from exam_trainer.application.engine.expectations import default_expectation_registry
from exam_trainer.application.engine.generators import default_generator_registry
from exam_trainer.application.engine.test_case_service import TestCaseService
from exam_trainer.domain.exercise_definition import (
    ExerciseDefinition,
    ExecutionDefinition,
    LimitsDefinition,
    SubmissionDefinition,
    TestCaseDefinition,
    TestDefinition,
)
from exam_trainer.domain.grading import GradingPolicy
from exam_trainer.ports.compiler_port import CompilationResult
from exam_trainer.ports.grader_port import GradingRequest


def definition() -> ExerciseDefinition:
    return ExerciseDefinition(
        id="echo_args",
        name="Echo Args",
        subject=Path("subject.md"),
        submission=SubmissionDefinition(filename="echo_args.c"),
        execution=ExecutionDefinition(type="program_output"),
        tests=TestDefinition(generator="random_arguments", expectation="echo_arguments"),
        limits=LimitsDefinition(timeout_seconds=2),
    )


class FailingCompiler:
    def is_available(self) -> bool:
        return True

    def compile(
        self,
        source_files: list[Path],
        output_path: Path,
    ) -> CompilationResult:
        return CompilationResult(
            success=False,
            output="compile failed",
            command=("cc", "file.c"),
        )


class EngineFoundationTest(unittest.TestCase):
    def test_generators_are_reproducible_by_seed(self) -> None:
        registry = default_generator_registry()
        generator = registry.get("random_string")

        self.assertEqual(generator(123), generator(123))
        self.assertNotEqual(generator(123), generator(124))

    def test_expectation_calculates_expected_output(self) -> None:
        service = TestCaseService(
            default_generator_registry(),
            default_expectation_registry(),
        )

        cases = service.build_cases(definition(), seed=10)

        self.assertTrue(cases)
        for test_case in cases:
            self.assertEqual(test_case.expected, " ".join(test_case.args) + "\n")

    def test_fixed_cases_are_preserved(self) -> None:
        service = TestCaseService(
            default_generator_registry(),
            default_expectation_registry(),
        )
        fixed_definition = ExerciseDefinition(
            id="fixed",
            name="Fixed",
            subject=Path("subject.md"),
            submission=SubmissionDefinition(filename="fixed.c"),
            execution=ExecutionDefinition(type="program_output"),
            tests=TestDefinition(
                generator="fixed_cases",
                expectation="literal",
                cases=(
                    TestCaseDefinition(
                        args=("one", "two"),
                        expected="one two\n",
                    ),
                ),
            ),
            limits=LimitsDefinition(timeout_seconds=2),
        )

        cases = service.build_cases(fixed_definition, seed=10)

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].args, ("one", "two"))
        self.assertEqual(cases[0].expected, "one two\n")

    def test_compiler_reports_unavailable_when_candidates_do_not_exist(self) -> None:
        compiler = SystemCCompiler(candidates=("definitely-not-a-c-compiler",))

        self.assertFalse(compiler.is_available())

    def test_grader_reports_missing_submission_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = GradingRequest(
                definition=definition(),
                exercise_path=root / "exercise",
                workspace_path=root / "workspace",
                policy=GradingPolicy.training(),
                seed=1,
            )
            request.workspace_path.mkdir()

            result = GenericCGrader(FailingCompiler()).grade(request)

            self.assertFalse(result.passed)
            self.assertIn("Expected submission file not found", result.compile_output)

    def test_grader_stops_on_compile_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "echo_args.c").write_text("invalid c", encoding="utf-8")
            request = GradingRequest(
                definition=definition(),
                exercise_path=root / "exercise",
                workspace_path=workspace,
                policy=GradingPolicy.training(),
                seed=1,
            )

            result = GenericCGrader(FailingCompiler()).grade(request)

            self.assertFalse(result.passed)
            self.assertEqual(result.compile_output, "compile failed")
            self.assertEqual(result.test_results, ())
