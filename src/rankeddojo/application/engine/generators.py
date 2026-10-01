from __future__ import annotations

import random
import string
from collections.abc import Callable
from dataclasses import dataclass

from rankeddojo.domain.grading import TestCase
from rankeddojo.domain.test_contract import ArgumentContract, ArgumentKind, TestContract


TestCaseGenerator = Callable[[int, TestContract | None], list[TestCase]]


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


def _fixed_cases(seed: int, contract: TestContract | None = None) -> list[TestCase]:
    return []


def _random_string_cases(seed: int, contract: TestContract | None = None) -> list[TestCase]:
    if contract is not None:
        _ensure_contract_shape("random_string", contract, (ArgumentKind.STRING,))
        return _contract_cases(seed, contract)
    rng = random.Random(seed)
    cases: list[TestCase] = []
    alphabet = string.ascii_lowercase + string.ascii_uppercase
    for offset in range(5):
        value = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 16)))
        cases.append(TestCase(args=(value,), seed=seed + offset))
    return cases


def _random_integer_cases(seed: int, contract: TestContract | None = None) -> list[TestCase]:
    if contract is not None:
        _ensure_contract_shape("random_integer", contract, (ArgumentKind.INTEGER,))
        return _contract_cases(seed, contract)
    rng = random.Random(seed)
    return [
        TestCase(args=(str(rng.randint(-1000, 1000)),), seed=seed + offset)
        for offset in range(5)
    ]


def _random_arguments_cases(seed: int, contract: TestContract | None = None) -> list[TestCase]:
    if contract is not None:
        return _contract_cases(seed, contract)
    rng = random.Random(seed)
    cases: list[TestCase] = []
    for offset in range(5):
        count = rng.randint(0, 5)
        args = tuple(f"arg{rng.randint(0, 99)}" for _ in range(count))
        cases.append(TestCase(args=args, seed=seed + offset))
    return cases


def _random_int_array_cases(seed: int, contract: TestContract | None = None) -> list[TestCase]:
    if contract is not None:
        _ensure_contract_shape("random_int_array", contract, (ArgumentKind.INTEGER_SEQUENCE,))
        return _contract_cases(seed, contract)
    rng = random.Random(seed)
    cases: list[TestCase] = []
    for offset in range(5):
        values = tuple(str(rng.randint(-50, 50)) for _ in range(rng.randint(1, 8)))
        cases.append(TestCase(args=values, seed=seed + offset))
    return cases


def _ensure_contract_shape(
    generator: str,
    contract: TestContract,
    allowed: tuple[ArgumentKind, ...],
) -> None:
    if len(contract.args) != 1 or contract.args[0].kind not in allowed:
        allowed_text = ", ".join(kind.value for kind in allowed)
        raise ValueError(f"Generator {generator} does not support this contract; expected: {allowed_text}.")


def _contract_cases(seed: int, contract: TestContract) -> list[TestCase]:
    rng = random.Random(seed)
    return [
        TestCase(args=_contract_args(rng, contract), seed=seed + offset)
        for offset in range(5)
    ]


def _contract_args(rng: random.Random, contract: TestContract) -> tuple[str, ...]:
    args: list[str] = []
    for spec in contract.args:
        args.extend(_argument_values(rng, spec))
    return tuple(args)


def _argument_values(rng: random.Random, spec: ArgumentContract) -> tuple[str, ...]:
    if spec.kind is ArgumentKind.STRING:
        return (_string_value(rng),)
    if spec.kind is ArgumentKind.INTEGER:
        return (str(rng.randint(spec.min_value, spec.max_value)),)
    if spec.kind is ArgumentKind.CHOICE:
        return (rng.choice(spec.values),)
    if spec.kind is ArgumentKind.INTEGER_SEQUENCE:
        count = rng.randint(spec.min_items, spec.max_items)
        values = tuple(str(rng.randint(spec.min_value, spec.max_value)) for _ in range(count))
        if spec.include_length_arg:
            return (str(count), *values)
        return values
    raise ValueError(f"Unsupported argument kind: {spec.kind}.")


def _string_value(rng: random.Random) -> str:
    words = (
        "alpha",
        "Beta",
        "hello world",
        "trim-me",
        "answer42",
        "two_words",
        "Codex",
        "edge.case",
    )
    return rng.choice(words)
