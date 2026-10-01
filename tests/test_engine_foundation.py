from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rankeddojo.adapters.compiler.system_c_compiler import SystemCCompiler
from rankeddojo.adapters.grader.generic_c_grader import GenericCGrader
from rankeddojo.application.engine.expectations import default_expectation_registry
from rankeddojo.application.engine.generators import default_generator_registry
from rankeddojo.application.engine.test_case_service import TestCaseService
from rankeddojo.domain.exercise_definition import (
    ExerciseDefinition,
    ExecutionDefinition,
    LimitsDefinition,
    SubmissionDefinition,
    TestCaseDefinition,
    TestDefinition,
)
from rankeddojo.domain.grading import GradingPolicy
from rankeddojo.ports.compiler_port import CompilationResult
from rankeddojo.ports.grader_port import GradingRequest


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
        *,
        include_dirs: tuple[Path, ...] = (),
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

    def test_compiler_reports_unavailable_when_no_candidate_can_be_resolved(self) -> None:
        """Hermetic: an explicit candidate that does not exist, combined
        with no Windows WinGet fallback available, must report unavailable
        regardless of what is actually installed on the host machine."""
        compiler = SystemCCompiler(candidates=("definitely-not-a-c-compiler",))

        with patch.object(compiler, "_windows_winget_candidates", return_value=[]):
            self.assertFalse(compiler.is_available())

    def test_compiler_reports_available_via_windows_winget_fallback(self) -> None:
        """Hermetic: nothing resolvable via `shutil.which`, but the
        Windows WinGet fallback resolves a compiler that passes
        compatibility probing -- must report available. Runs identically
        on Windows with a real GCC installed, on Windows without one, and
        on Linux CI, because both `shutil.which` and the fallback itself
        are mocked; no real compiler is ever invoked.
        """
        compiler = SystemCCompiler(candidates=("definitely-not-a-c-compiler",))
        fake_compiler_path = Path("C:/fake/winget/gcc.exe")

        with patch(
            "rankeddojo.adapters.compiler.system_c_compiler.shutil.which",
            return_value=None,
        ), patch.object(
            compiler,
            "_windows_winget_candidates",
            return_value=[fake_compiler_path],
        ), patch.object(
            Path,
            "is_file",
            return_value=True,
        ), patch.object(
            compiler,
            "_is_compatible_compiler",
            return_value=True,
        ):
            self.assertTrue(compiler.is_available())
            self.assertEqual(compiler.find_compiler(), str(fake_compiler_path))

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
