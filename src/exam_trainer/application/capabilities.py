"""O que o motor sabe executar. O pack declara; o app decide se suporta.

Um pack que pede algo fora daqui é REJEITADO na importação (não "roda pela metade").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from exam_trainer.domain.exercise_definition import FUNCTION_CALL, PROGRAM_OUTPUT
from exam_trainer.ports.runtime_port import RuntimeDescriptor


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


# Quem fornece o harness de `function_call`:
HARNESS_FROM_PACK = "pack"  # o pack traz o arquivo (C: main.c que chama a função)
HARNESS_FROM_APP = "app"  # o app gera; o pack só declara entry + args_format (Python)


@dataclass(frozen=True)
class LanguageSupport:
    language: str
    executions: frozenset[str]
    function_harness: str = HARNESS_FROM_PACK
    args_formats: frozenset[str] = field(default_factory=frozenset)
    main_class_required: bool = False
    file_extensions: tuple[str, ...] = ()

    @classmethod
    def from_descriptor(cls, descriptor: RuntimeDescriptor) -> "LanguageSupport":
        return cls(
            language=descriptor.language,
            executions=frozenset(descriptor.execution_types),
            function_harness=descriptor.function_harness,
            args_formats=frozenset(descriptor.args_formats),
            main_class_required=descriptor.main_class_required,
            file_extensions=descriptor.file_extensions,
        )


@dataclass(frozen=True)
class ExerciseCapabilities:
    executions: ExecutionRegistry
    generators: GeneratorRegistry
    expectations: ExpectationRegistry
    languages: dict[str, LanguageSupport] = field(default_factory=dict)

    def language(self, identifier: str) -> LanguageSupport | None:
        return self.languages.get(identifier)

    def with_language(self, support: LanguageSupport) -> "ExerciseCapabilities":
        return ExerciseCapabilities(
            executions=self.executions,
            generators=self.generators,
            expectations=self.expectations,
            languages={**self.languages, support.language: support},
        )


C_LANGUAGE = LanguageSupport(
    language="c",
    executions=frozenset((PROGRAM_OUTPUT, FUNCTION_CALL)),
    function_harness=HARNESS_FROM_PACK,
)

PYTHON_LANGUAGE = LanguageSupport(
    language="python",
    executions=frozenset((PROGRAM_OUTPUT, FUNCTION_CALL)),
    function_harness=HARNESS_FROM_APP,
    args_formats=frozenset(("json", "str")),
)

CPP_LANGUAGE = LanguageSupport(
    language="cpp",
    executions=frozenset((PROGRAM_OUTPUT, FUNCTION_CALL)),
    function_harness=HARNESS_FROM_PACK,
    file_extensions=(".cpp", ".hpp", ".h"),
)

JAVA_LANGUAGE = LanguageSupport(
    language="java",
    executions=frozenset((PROGRAM_OUTPUT,)),
    function_harness="none",
    main_class_required=True,
    file_extensions=(".java",),
)

# Expectations "embutidas" por exercício. Continuam aceitas, mas packs novos devem
# preferir `reference_output` (solução de referência) ou `literal` (casos fixos).
LEGACY_BUILTIN_EXPECTATIONS = frozenset(("echo_arguments", "sum_integers"))


def default_exercise_capabilities() -> ExerciseCapabilities:
    return ExerciseCapabilities(
        executions=ExecutionRegistry.from_values(
            # tipos neutros + aliases do contrato v1
            (PROGRAM_OUTPUT, FUNCTION_CALL, "function_with_main", "reference_compare")
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
        languages={support.language: support for support in (C_LANGUAGE, CPP_LANGUAGE, PYTHON_LANGUAGE, JAVA_LANGUAGE)},
    )


def capabilities_from_runtime_descriptors(descriptors: Iterable[RuntimeDescriptor]) -> ExerciseCapabilities:
    base = default_exercise_capabilities()
    return ExerciseCapabilities(
        executions=base.executions,
        generators=base.generators,
        expectations=base.expectations,
        languages={
            descriptor.language: LanguageSupport.from_descriptor(descriptor)
            for descriptor in descriptors
        },
    )
