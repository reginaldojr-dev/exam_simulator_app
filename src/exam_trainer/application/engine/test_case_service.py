from __future__ import annotations

from dataclasses import replace

from exam_trainer.application.engine.expectations import ExpectationRegistry
from exam_trainer.application.engine.generators import TestCaseGeneratorRegistry
from exam_trainer.domain.exercise_definition import ExerciseDefinition
from exam_trainer.domain.grading import TestCase


class TestCaseService:
    def __init__(
        self,
        generator_registry: TestCaseGeneratorRegistry,
        expectation_registry: ExpectationRegistry,
    ) -> None:
        self._generator_registry = generator_registry
        self._expectation_registry = expectation_registry

    def build_cases(self, definition: ExerciseDefinition, seed: int) -> list[TestCase]:
        generator = self._generator_registry.get(definition.tests.generator)
        expectation = self._expectation_registry.get(definition.tests.expectation)
        fixed_cases = [
            TestCase(
                args=case.args,
                stdin=case.stdin,
                expected=case.expected or "",
                seed=seed + index,
            )
            for index, case in enumerate(definition.tests.cases)
        ]
        generated_cases = [] if definition.tests.generator == "fixed_cases" else generator(seed)
        all_cases = [*fixed_cases, *generated_cases]
        return [
            replace(test_case, expected=expectation(test_case))
            for test_case in all_cases
        ]
