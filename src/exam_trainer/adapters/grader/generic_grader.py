"""Grader genérico: independente de linguagem.

GenericGrader -> ExecutionStrategy (quais arquivos) -> RuntimeRegistry (qual runtime)
-> LanguageRuntime (preparar/executar). Aqui ficam casos, expectations, comparação,
fail-fast, trace, seeds e política.
"""

from __future__ import annotations

import random
from dataclasses import replace

from exam_trainer.application.engine.execution import (
    ExecutionPlanError,
    ExecutionStrategy,
    default_execution_strategies,
    reference_spec,
)
from exam_trainer.application.engine.expectations import ExpectationRegistry, default_expectation_registry
from exam_trainer.application.engine.generators import TestCaseGeneratorRegistry, default_generator_registry
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry, UnsupportedLanguageError
from exam_trainer.application.engine.test_case_service import TestCaseService
from exam_trainer.application.engine.trace_builder import TraceBuilder
from exam_trainer.domain.grading import GradingResult, TestCase, TestResult
from exam_trainer.ports.grader_port import GradingRequest
from exam_trainer.ports.runtime_port import LanguageRuntime, PreparedProgram


class GenericGrader:
    def __init__(
        self,
        runtimes: RuntimeRegistry,
        generator_registry: TestCaseGeneratorRegistry | None = None,
        expectation_registry: ExpectationRegistry | None = None,
        strategies: dict[str, ExecutionStrategy] | None = None,
    ) -> None:
        self._runtimes = runtimes
        self._strategies = strategies or default_execution_strategies()
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
            return self._failed_result(trace, seed, f"Expected submission file not found: {source_file}")

        try:
            runtime = self._runtimes.get(definition.language)
            strategy = self._strategies.get(definition.execution.type)
            if strategy is None:
                raise ExecutionPlanError(f"Unsupported execution type for grader: {definition.execution.type}")
            submission_spec = strategy.submission(definition, request.exercise_path, source_file)
            reference = None if definition.reference is None else reference_spec(definition, request.exercise_path)
        except (UnsupportedLanguageError, ExecutionPlanError) as error:
            return self._failed_result(trace, seed, str(error))

        build_dir = request.workspace_path / ".build"
        program = runtime.prepare(submission_spec, build_dir, definition.id)
        trace.add_compilation(program.build)
        if not program.success:
            return GradingResult(
                passed=False,
                compile_output=program.build.output,
                seed=seed,
                trace_data=trace.build(),
            )

        test_cases = self._test_case_service.build_cases(definition, seed)
        timeout = definition.limits.timeout_seconds
        if reference is not None:
            reference_program = runtime.prepare(reference, build_dir, f"{definition.id}_reference")
            trace.add_compilation(reference_program.build)
            if not reference_program.success:
                return self._failed_result(
                    trace, seed, f"Reference failed to compile:\n{reference_program.build.output}"
                )
            test_cases = [
                self._case_with_reference_output(runtime, reference_program, case, timeout) for case in test_cases
            ]

        test_results: list[TestResult] = []
        for index, test_case in enumerate(test_cases, start=1):
            test_result = self._run_test_case(runtime, program, test_case, timeout)
            test_results.append(test_result)
            trace.add_test_result(index, test_result)
            if request.policy.fail_fast and not test_result.passed:
                break

        passed = all(result.passed for result in test_results) and bool(test_results)
        grading_result = GradingResult(
            passed=passed,
            compile_output=program.build.output,
            test_results=tuple(test_results),
            stderr="\n".join(result.stderr for result in test_results if result.stderr),
            seed=seed,
            trace_data=trace.build(),
        )
        trace.add_final_result(grading_result)
        return replace(grading_result, trace_data=trace.build())

    @staticmethod
    def _run_test_case(
        runtime: LanguageRuntime,
        program: PreparedProgram,
        test_case: TestCase,
        timeout_seconds: int,
    ) -> TestResult:
        outcome = runtime.run(program, test_case.args, test_case.stdin, timeout_seconds)
        if outcome.timed_out:
            return TestResult(
                test_case=test_case,
                passed=False,
                stdout=outcome.stdout,
                stderr=outcome.stderr,
                timed_out=True,
            )
        return TestResult(
            test_case=test_case,
            passed=outcome.exit_code == 0 and outcome.stdout == test_case.expected,
            stdout=outcome.stdout,
            stderr=outcome.stderr,
            exit_code=outcome.exit_code,
        )

    @classmethod
    def _case_with_reference_output(
        cls,
        runtime: LanguageRuntime,
        reference: PreparedProgram,
        test_case: TestCase,
        timeout_seconds: int,
    ) -> TestCase:
        result = cls._run_test_case(runtime, reference, replace(test_case, expected=""), timeout_seconds)
        expected = result.stdout
        if result.stderr:
            expected += result.stderr
        return replace(test_case, expected=expected)

    @staticmethod
    def _failed_result(trace: TraceBuilder, seed: int, message: str) -> GradingResult:
        trace.add_content_error(message)
        return GradingResult(passed=False, compile_output=message, seed=seed, trace_data=trace.build())
