from __future__ import annotations

import random
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from exam_trainer.application.engine.expectations import (
    ExpectationRegistry,
    default_expectation_registry,
)
from exam_trainer.application.engine.generators import (
    TestCaseGeneratorRegistry,
    default_generator_registry,
)
from exam_trainer.application.engine.test_case_service import TestCaseService
from exam_trainer.application.engine.trace_builder import TraceBuilder
from exam_trainer.domain.grading import GradingResult, TestResult
from exam_trainer.ports.compiler_port import CompilationResult, CompilerPort
from exam_trainer.ports.grader_port import GraderPort, GradingRequest


class GenericCGrader:
    def __init__(
        self,
        compiler: CompilerPort,
        generator_registry: TestCaseGeneratorRegistry | None = None,
        expectation_registry: ExpectationRegistry | None = None,
    ) -> None:
        self._compiler = compiler
        self._test_case_service = TestCaseService(
            generator_registry or default_generator_registry(),
            expectation_registry or default_expectation_registry(),
        )

    def grade(self, request: GradingRequest) -> GradingResult:
        seed = request.seed if request.seed is not None else random.SystemRandom().randint(1, 2**31)
        definition = request.definition
        trace = TraceBuilder()
        trace.add_environment(definition, request.workspace_path)

        source_file = request.workspace_path / definition.submission.filename
        trace.add_collected_file(source_file)
        if not source_file.is_file():
            return self._failed_result(
                trace,
                seed,
                f"Expected submission file not found: {source_file}",
            )

        try:
            source_files = self._source_files_for_request(request, source_file)
        except ValueError as error:
            return self._failed_result(trace, seed, str(error))

        build_dir = request.workspace_path / ".build"
        build_dir.mkdir(parents=True, exist_ok=True)
        executable_path = build_dir / self._executable_name(definition.id)
        compilation = self._compiler.compile(source_files, executable_path)
        trace.add_compilation(compilation)
        if not compilation.success or compilation.executable_path is None:
            result = GradingResult(
                passed=False,
                compile_output=compilation.output,
                seed=seed,
                trace_data=trace.build(),
            )
            return result

        test_cases = self._test_case_service.build_cases(definition, seed)
        reference_executable_path: Path | None = None
        if definition.execution.type == "reference_compare":
            try:
                reference_sources = self._reference_source_files_for_request(request)
            except ValueError as error:
                return self._failed_result(trace, seed, str(error))

            reference_executable_path = build_dir / self._executable_name(
                f"{definition.id}_reference"
            )
            reference_compilation = self._compiler.compile(
                reference_sources,
                reference_executable_path,
            )
            trace.add_compilation(reference_compilation)
            if (
                not reference_compilation.success
                or reference_compilation.executable_path is None
            ):
                return self._failed_result(
                    trace,
                    seed,
                    f"Reference failed to compile:\n{reference_compilation.output}",
                )
            test_cases = [
                self._case_with_reference_output(
                    reference_compilation.executable_path,
                    test_case,
                    definition.limits.timeout_seconds,
                )
                for test_case in test_cases
            ]
        test_results: list[TestResult] = []
        for index, test_case in enumerate(test_cases, start=1):
            test_result = self._run_test_case(
                compilation.executable_path,
                test_case,
                definition.limits.timeout_seconds,
            )
            test_results.append(test_result)
            trace.add_test_result(index, test_result)
            if request.policy.fail_fast and not test_result.passed:
                break

        passed = all(result.passed for result in test_results) and bool(test_results)
        grading_result = GradingResult(
            passed=passed,
            compile_output=compilation.output,
            test_results=tuple(test_results),
            stderr="\n".join(result.stderr for result in test_results if result.stderr),
            seed=seed,
            trace_data=trace.build(),
        )
        trace.add_final_result(grading_result)
        return GradingResult(
            passed=grading_result.passed,
            compile_output=grading_result.compile_output,
            test_results=grading_result.test_results,
            stderr=grading_result.stderr,
            seed=grading_result.seed,
            trace_data=trace.build(),
        )

    def _source_files_for_request(
        self,
        request: GradingRequest,
        source_file: Path,
    ) -> list[Path]:
        execution = request.definition.execution
        if execution.type == "program_output":
            return [source_file]

        if execution.type == "function_with_main":
            if execution.fixture is None:
                raise ValueError("Missing fixture declaration for function_with_main.")
            fixture_path = request.exercise_path / execution.fixture
            if not fixture_path.is_file():
                raise ValueError(f"Required fixture not found: {fixture_path}")
            return [fixture_path, source_file]

        if execution.type == "reference_compare":
            if execution.fixture is None:
                return [source_file]
            fixture_path = request.exercise_path / execution.fixture
            if not fixture_path.is_file():
                raise ValueError(f"Required fixture not found: {fixture_path}")
            return [fixture_path, source_file]

        raise ValueError(f"Unsupported execution type for grader: {execution.type}")

    def _reference_source_files_for_request(
        self,
        request: GradingRequest,
    ) -> list[Path]:
        execution = request.definition.execution
        if execution.reference is None:
            raise ValueError("Missing reference declaration for reference_compare.")
        reference_path = request.exercise_path / execution.reference
        if not reference_path.is_file():
            raise ValueError(f"Required reference not found: {reference_path}")
        if execution.fixture is None:
            return [reference_path]
        fixture_path = request.exercise_path / execution.fixture
        if not fixture_path.is_file():
            raise ValueError(f"Required fixture not found: {fixture_path}")
        return [fixture_path, reference_path]

    @staticmethod
    def _run_test_case(
        executable_path: Path,
        test_case,
        timeout_seconds: int,
    ) -> TestResult:
        try:
            completed = subprocess.run(
                [str(executable_path), *test_case.args],
                input=test_case.stdin,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout if isinstance(error.stdout, str) else ""
            stderr = error.stderr if isinstance(error.stderr, str) else ""
            return TestResult(
                test_case=test_case,
                passed=False,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
            )

        return TestResult(
            test_case=test_case,
            passed=completed.returncode == 0 and completed.stdout == test_case.expected,
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )

    @classmethod
    def _case_with_reference_output(
        cls,
        executable_path: Path,
        test_case,
        timeout_seconds: int,
    ):
        reference_result = cls._run_test_case(
            executable_path,
            replace(test_case, expected=""),
            timeout_seconds,
        )
        expected = reference_result.stdout
        if reference_result.stderr:
            expected += reference_result.stderr
        return replace(test_case, expected=expected)

    @staticmethod
    def _executable_name(exercise_id: str) -> str:
        suffix = ".exe" if sys.platform == "win32" else ""
        return f"{exercise_id}{suffix}"

    @staticmethod
    def _failed_result(
        trace: TraceBuilder,
        seed: int,
        message: str,
    ) -> GradingResult:
        trace.add_content_error(message)
        return GradingResult(
            passed=False,
            compile_output=message,
            seed=seed,
            trace_data=trace.build(),
        )
