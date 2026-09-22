from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from exam_trainer.domain.grading import TestCase


Expectation = Callable[[TestCase], str]


@dataclass(frozen=True)
class ExpectationRegistry:
    _expectations: dict[str, Expectation]

    def get(self, identifier: str) -> Expectation:
        try:
            return self._expectations[identifier]
        except KeyError as error:
            raise KeyError(f"Unknown expectation: {identifier}.") from error


def default_expectation_registry() -> ExpectationRegistry:
    return ExpectationRegistry(
        {
            "literal": _literal,
            "reference_output": _reference_output,
            "echo_arguments": _echo_arguments,
            "sum_integers": _sum_integers,
        }
    )


def _literal(test_case: TestCase) -> str:
    return test_case.expected


def _reference_output(test_case: TestCase) -> str:
    return test_case.expected


def _echo_arguments(test_case: TestCase) -> str:
    return " ".join(test_case.args) + "\n"


def _sum_integers(test_case: TestCase) -> str:
    total = sum(int(value) for value in test_case.args)
    return f"{total}\n"
