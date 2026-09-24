from __future__ import annotations

from pathlib import Path

from exam_trainer.domain.exercise_definition import ExerciseDefinition
from exam_trainer.domain.grading import GradingResult, TestCase, TestResult, TraceData
from exam_trainer.ports.compiler_port import CompilationResult


class TraceBuilder:
    def __init__(self) -> None:
        self._lines: list[str] = []

    def add_environment(self, definition: ExerciseDefinition, workspace_path: Path) -> None:
        self._lines.extend(
            (
                "=== Exam Trainer Trace ===",
                f"Exercise: {definition.name} ({definition.id})",
                f"Execution: {definition.execution.type}"
                + (
                    f" (declared: {definition.execution.declared_type})"
                    if definition.execution.declared_type not in (None, definition.execution.type)
                    else ""
                ),
                f"Language: {definition.language}",
                f"Workspace: {workspace_path}",
                "",
            )
        )

    def add_collected_file(self, path: Path) -> None:
        self._lines.extend(("=== Collected File ===", str(path), ""))

    def add_compilation(self, result: CompilationResult) -> None:
        command = " ".join(result.command) if result.command else "(not executed)"
        self._lines.extend(
            (
                "=== Compilation ===",
                f"Command: {command}",
                "Output:",
                result.output.rstrip(),
                f"Result: {'PASS' if result.success else 'FAIL'}",
                "",
            )
        )

    def add_test_result(self, index: int, test_result: TestResult) -> None:
        test_case = test_result.test_case
        self._lines.extend(
            (
                f"=== Test {index} ===",
                f"Seed: {test_case.seed}",
                f"Args: {list(test_case.args)}",
                f"Stdin: {test_case.stdin!r}",
                f"Expected output: {test_case.expected!r}",
                f"Your output: {test_result.stdout!r}",
                f"Stderr: {test_result.stderr!r}",
                f"Exit code: {test_result.exit_code}",
                f"Timed out: {test_result.timed_out}",
                f"Result: {'PASS' if test_result.passed else 'FAIL'}",
                "",
            )
        )

    def add_content_error(self, message: str) -> None:
        self._lines.extend(("=== Content Error ===", message, ""))

    def add_missing_compiler(self, message: str) -> None:
        self._lines.extend(("=== Compiler Error ===", message, ""))

    def add_final_result(self, result: GradingResult) -> None:
        self._lines.extend(
            (
                "=== Final Result ===",
                f"Result: {'PASS' if result.passed else 'FAIL'}",
                "",
            )
        )

    def build(self) -> TraceData:
        return TraceData(lines=tuple(self._lines))

