from __future__ import annotations

import random
import string
from collections.abc import Callable
from dataclasses import dataclass

from exam_trainer.domain.grading import TestCase


TestCaseGenerator = Callable[[int], list[TestCase]]


@dataclass(frozen=True)
class TestCaseGeneratorRegistry:
    _generators: dict[str, TestCaseGenerator]

    def get(self, identifier: str) -> TestCaseGenerator:
        try:
            return self._generators[identifier]
        except KeyError as error:
            raise KeyError(f"Unknown test generator: {identifier}.") from error


def default_generator_registry() -> TestCaseGeneratorRegistry:
    return TestCaseGeneratorRegistry(
        {
            "fixed_cases": _fixed_cases,
            "random_string": _random_string_cases,
            "random_integer": _random_integer_cases,
            "random_arguments": _random_arguments_cases,
            "random_int_array": _random_int_array_cases,
        }
    )


def _fixed_cases(seed: int) -> list[TestCase]:
    return []


def _random_string_cases(seed: int) -> list[TestCase]:
    rng = random.Random(seed)
    cases: list[TestCase] = []
    alphabet = string.ascii_lowercase + string.ascii_uppercase
    for offset in range(5):
        value = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 16)))
        cases.append(TestCase(args=(value,), seed=seed + offset))
    return cases


def _random_integer_cases(seed: int) -> list[TestCase]:
    rng = random.Random(seed)
    return [
        TestCase(args=(str(rng.randint(-1000, 1000)),), seed=seed + offset)
        for offset in range(5)
    ]


def _random_arguments_cases(seed: int) -> list[TestCase]:
    rng = random.Random(seed)
    cases: list[TestCase] = []
    for offset in range(5):
        count = rng.randint(0, 5)
        args = tuple(f"arg{rng.randint(0, 99)}" for _ in range(count))
        cases.append(TestCase(args=args, seed=seed + offset))
    return cases


def _random_int_array_cases(seed: int) -> list[TestCase]:
    rng = random.Random(seed)
    cases: list[TestCase] = []
    for offset in range(5):
        values = tuple(str(rng.randint(-50, 50)) for _ in range(rng.randint(1, 8)))
        cases.append(TestCase(args=values, seed=seed + offset))
    return cases
