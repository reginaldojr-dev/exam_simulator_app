from __future__ import annotations

from dataclasses import replace

from rankeddojo.application.engine.expectations import ExpectationRegistry
from rankeddojo.application.engine.generators import TestCaseGeneratorRegistry
from rankeddojo.domain.exercise_definition import ExerciseDefinition
from rankeddojo.domain.grading import TestCase


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
        if definition.tests.contract is not None:
            for test_case in fixed_cases:
                self._validate_contract(test_case, definition.tests.contract)
        generated_cases = [] if definition.tests.generator == "fixed_cases" else generator(
            seed,
            definition.tests.contract,
        )
        all_cases = [*fixed_cases, *generated_cases]
        return [
            replace(test_case, expected=expectation(test_case))
            for test_case in all_cases
        ]

    @staticmethod
    def _validate_contract(test_case: TestCase, contract) -> None:
        from rankeddojo.domain.test_contract import ArgumentKind

        index = 0
        for spec in contract.args:
            if spec.kind in (ArgumentKind.STRING, ArgumentKind.INTEGER, ArgumentKind.CHOICE):
                if index >= len(test_case.args):
                    raise ValueError("Fixed test case has fewer args than tests.contract requires.")
                value = test_case.args[index]
                if spec.kind is ArgumentKind.INTEGER:
                    int(value)
                elif spec.kind is ArgumentKind.CHOICE and value not in spec.values:
                    raise ValueError(f"Fixed test case value {value!r} is not allowed by tests.contract.")
                index += 1
                continue
            if spec.kind is ArgumentKind.INTEGER_SEQUENCE:
                remaining = test_case.args[index:]
                if spec.include_length_arg:
                    if not remaining:
                        raise ValueError("Fixed test case is missing integer sequence length arg.")
                    count = int(remaining[0])
                    values = remaining[1:]
                    if count != len(values):
                        raise ValueError("Fixed test case integer sequence length arg does not match values.")
                else:
                    values = remaining
                if not spec.min_items <= len(values) <= spec.max_items:
                    raise ValueError("Fixed test case integer sequence size is outside tests.contract bounds.")
                for value in values:
                    int(value)
                index = len(test_case.args)
        if index != len(test_case.args):
            raise ValueError("Fixed test case has more args than tests.contract allows.")
