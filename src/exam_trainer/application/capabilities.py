from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CapabilityRegistry:
    supported: frozenset[str]

    @classmethod
    def from_values(cls, values: Iterable[str]) -> "CapabilityRegistry":
        return cls(supported=frozenset(values))

    def supports(self, identifier: str) -> bool:
        return identifier in self.supported


class ExecutionRegistry(CapabilityRegistry):
    pass


class GeneratorRegistry(CapabilityRegistry):
    pass


class ExpectationRegistry(CapabilityRegistry):
    pass


@dataclass(frozen=True)
class ExerciseCapabilities:
    executions: ExecutionRegistry
    generators: GeneratorRegistry
    expectations: ExpectationRegistry


def default_exercise_capabilities() -> ExerciseCapabilities:
    return ExerciseCapabilities(
        executions=ExecutionRegistry.from_values(
            ("program_output", "function_with_main", "reference_compare", "custom")
        ),
        generators=GeneratorRegistry.from_values(
            (
                "fixed_cases",
                "random_string",
                "random_integer",
                "random_arguments",
                "random_int_array",
            )
        ),
        expectations=ExpectationRegistry.from_values(
            ("literal", "reference_output", "echo_arguments", "sum_integers")
        ),
    )
