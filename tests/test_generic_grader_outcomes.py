"""GenericGrader outcome classification: USER_FAILED vs CONTENT_ERROR vs PASSED.

Uses a fake LanguageRuntime double (no real compiler/subprocess involved) so
every path -- submission ok/wrong/uncompilable/crashing, reference
ok/uncompilable/crashing/timing out -- can be exercised deterministically.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from exam_trainer.adapters.grader.generic_grader import GenericGrader
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry
from exam_trainer.domain.exercise_definition import (
    FUNCTION_CALL,
    PROGRAM_OUTPUT,
    ExecutionDefinition,
    ExerciseDefinition,
    LimitsDefinition,
    ReferenceDefinition,
    SubmissionDefinition,
    TestCaseDefinition,
    TestDefinition,
)
from exam_trainer.domain.grading import GradingOutcome, GradingPolicy
from exam_trainer.ports.compiler_port import CompilationResult
from exam_trainer.ports.grader_port import GradingRequest
from exam_trainer.ports.runtime_port import PreparedProgram, ProcessOutcome, ProgramSpec


class FakeRuntime:
    """LanguageRuntime double: outcomes are picked by role (submission/reference), not by reading source content."""

    language = "fake"
    display_name = "Fake"

    def __init__(self, submission: str = "ok", reference: str = "ok") -> None:
        # "ok" | "compile_fail" | "run_fail" | "timeout" | "mismatch" (submission only)
        self._submission = submission
        self._reference = reference

    def is_ready(self) -> bool:
        return True

    def check_available(self) -> bool:
        return True

    def current_tool(self) -> str | None:
        return "fake"

    def redetect(self) -> str | None:
        return "fake"

    def configure_manual(self, path: Path) -> str:
        return str(path)

    def prepare(self, spec: ProgramSpec, build_dir: Path, name: str) -> PreparedProgram:
        is_reference = name.endswith("_reference")
        outcome = self._reference if is_reference else self._submission
        if outcome == "compile_fail":
            return PreparedProgram(success=False, build=CompilationResult(success=False, output="fake compile error"))
        role = "reference" if is_reference else "submission"
        return PreparedProgram(success=True, build=CompilationResult(success=True, output=""), argv=(role,))

    def run(
        self,
        program: PreparedProgram,
        args: tuple[str, ...],
        stdin: str,
        timeout_seconds: int,
    ) -> ProcessOutcome:
        is_reference = program.argv[0] == "reference"
        outcome = self._reference if is_reference else self._submission
        if outcome == "timeout":
            return ProcessOutcome(timed_out=True)
        if outcome == "run_fail":
            return ProcessOutcome(stdout="", stderr="boom", exit_code=1)
        if outcome == "mismatch":
            return ProcessOutcome(stdout="WRONG\n", stderr="", exit_code=0)
        return ProcessOutcome(stdout=" ".join(args) + "\n", stderr="", exit_code=0)


def _definition(with_reference: bool = True) -> ExerciseDefinition:
    return ExerciseDefinition(
        id="fake_ex",
        name="Fake Exercise",
        subject=Path("subject.md"),
        submission=SubmissionDefinition(filename="fake_ex.fake"),
        execution=ExecutionDefinition(type=PROGRAM_OUTPUT),
        tests=TestDefinition(
            generator="fixed_cases",
            expectation="reference_output" if with_reference else "literal",
            cases=(TestCaseDefinition(args=("a", "b"), expected="a b\n"),),
        ),
        limits=LimitsDefinition(timeout_seconds=2),
        reference=ReferenceDefinition(source=Path("reference.fake")) if with_reference else None,
        language="fake",
    )


class GenericGraderOutcomeTest(unittest.TestCase):
    def _grade(self, definition: ExerciseDefinition, submission: str, reference: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            exercise_path = root / "exercise"
            workspace.mkdir()
            exercise_path.mkdir()
            (workspace / definition.submission.filename).write_text("", encoding="utf-8")
            if definition.reference is not None:
                (exercise_path / "reference.fake").write_text("", encoding="utf-8")

            grader = GenericGrader(RuntimeRegistry([FakeRuntime(submission=submission, reference=reference)]))
            return grader.grade(
                GradingRequest(
                    definition=definition,
                    exercise_path=exercise_path,
                    workspace_path=workspace,
                    policy=GradingPolicy.training(),
                    seed=1,
                )
            )

    # 1. submission compiles and passes -> PASSED
    def test_submission_ok_matches_reference_is_passed(self) -> None:
        result = self._grade(_definition(), submission="ok", reference="ok")
        self.assertIs(result.outcome, GradingOutcome.PASSED)
        self.assertTrue(result.passed)

    # 2. submission output diverges -> USER_FAILED
    def test_submission_output_mismatch_is_user_failed(self) -> None:
        result = self._grade(_definition(), submission="mismatch", reference="ok")
        self.assertIs(result.outcome, GradingOutcome.USER_FAILED)
        self.assertFalse(result.passed)

    # 3. submission does not compile -> USER_FAILED
    def test_submission_compile_failure_is_user_failed(self) -> None:
        result = self._grade(_definition(with_reference=False), submission="compile_fail", reference="ok")
        self.assertIs(result.outcome, GradingOutcome.USER_FAILED)
        self.assertFalse(result.passed)

    # 4. submission times out -> USER_FAILED
    def test_submission_timeout_is_user_failed(self) -> None:
        result = self._grade(_definition(), submission="timeout", reference="ok")
        self.assertIs(result.outcome, GradingOutcome.USER_FAILED)
        self.assertFalse(result.passed)

    # 4b. submission crashes (non-zero exit) -> USER_FAILED
    def test_submission_run_failure_is_user_failed(self) -> None:
        result = self._grade(_definition(), submission="run_fail", reference="ok")
        self.assertIs(result.outcome, GradingOutcome.USER_FAILED)
        self.assertFalse(result.passed)

    # 5. reference does not compile -> CONTENT_ERROR, never USER_FAILED
    def test_reference_compile_failure_is_content_error(self) -> None:
        result = self._grade(_definition(), submission="ok", reference="compile_fail")
        self.assertIs(result.outcome, GradingOutcome.CONTENT_ERROR)
        self.assertFalse(result.passed)
        self.assertIn("Reference failed to compile", result.compile_output)

    # 6. reference execution exit_code != 0 -> CONTENT_ERROR
    def test_reference_execution_failure_is_content_error(self) -> None:
        result = self._grade(_definition(), submission="ok", reference="run_fail")
        self.assertIs(result.outcome, GradingOutcome.CONTENT_ERROR)
        self.assertFalse(result.passed)

    # 7. reference times out -> CONTENT_ERROR
    def test_reference_timeout_is_content_error(self) -> None:
        result = self._grade(_definition(), submission="ok", reference="timeout")
        self.assertIs(result.outcome, GradingOutcome.CONTENT_ERROR)
        self.assertFalse(result.passed)

    # 8. harness/reference preparation is impossible to even start (bad execution plan) -> CONTENT_ERROR
    def test_missing_harness_declaration_is_content_error(self) -> None:
        definition = ExerciseDefinition(
            id="fake_fn",
            name="Fake Function",
            subject=Path("subject.md"),
            submission=SubmissionDefinition(filename="fake_fn.fake"),
            execution=ExecutionDefinition(type=FUNCTION_CALL),  # no harness, no entry declared
            tests=TestDefinition(generator="fixed_cases", expectation="literal", cases=(TestCaseDefinition(args=(), expected=""),)),
            limits=LimitsDefinition(timeout_seconds=2),
            language="fake",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            exercise_path = root / "exercise"
            workspace.mkdir()
            exercise_path.mkdir()
            (workspace / definition.submission.filename).write_text("", encoding="utf-8")

            grader = GenericGrader(RuntimeRegistry([FakeRuntime()]))
            result = grader.grade(
                GradingRequest(
                    definition=definition,
                    exercise_path=exercise_path,
                    workspace_path=workspace,
                    policy=GradingPolicy.training(),
                    seed=1,
                )
            )
            self.assertIs(result.outcome, GradingOutcome.CONTENT_ERROR)
            self.assertFalse(result.passed)

    def test_missing_submission_file_is_content_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = GradingRequest(
                definition=_definition(with_reference=False),
                exercise_path=root / "exercise",
                workspace_path=root / "workspace",
                policy=GradingPolicy.training(),
                seed=1,
            )
            request.workspace_path.mkdir()

            grader = GenericGrader(RuntimeRegistry([FakeRuntime()]))
            result = grader.grade(request)

            self.assertIs(result.outcome, GradingOutcome.CONTENT_ERROR)
            self.assertFalse(result.passed)
            self.assertIn("Expected submission file not found", result.compile_output)


if __name__ == "__main__":
    unittest.main()
