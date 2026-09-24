"""Modelo NEUTRO de exercício (independente de versão do JSON e de linguagem).

O loader normaliza o contrato v1 e o v2 para estas classes; o grader/runtime só
conhecem este modelo. Ver `resources/pack-contract.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath

from exam_trainer.domain.activity_definition import (
    ActivityDefinition,
    ActivityIdentity,
    ValidationPlan,
    ValidationStep,
)

# Tipos de execução neutros (o que o runtime precisa fazer com a submissão).
PROGRAM_OUTPUT = "program_output"
FUNCTION_CALL = "function_call"
EXECUTION_KINDS = (PROGRAM_OUTPUT, FUNCTION_CALL)

# Aliases do contrato v1 -> tipo neutro. Continuam aceitos (não removidos abruptamente).
LEGACY_EXECUTION_ALIASES = {
    "function_with_main": FUNCTION_CALL,
    "reference_compare": None,  # decidido pela presença de fixture (ver loader)
}


@dataclass(frozen=True)
class SubmissionDefinition:
    filename: str
    extra_files: tuple[PurePath, ...] = ()


@dataclass(frozen=True)
class ExecutionDefinition:
    """Como a submissão é executada.

    - `type`: tipo neutro (`program_output` | `function_call`);
    - `fixture`: harness fornecido pelo PACK (C: um main.c que chama a função);
    - `entry`/`args_format`: para linguagens em que o APP fornece o harness (Python):
      nome da função chamada e formato dos argumentos de cada caso;
    - `declared_type`: o tipo como estava no JSON (ex.: `function_with_main`, v1).
    """

    type: str
    fixture: PurePath | None = None
    reference: PurePath | None = None  # compat v1: mesmo valor de ExerciseDefinition.reference.source
    entry: str | None = None
    args_format: str | None = None
    declared_type: str | None = None

    @property
    def harness(self) -> PurePath | None:
        return self.fixture


@dataclass(frozen=True)
class ReferenceDefinition:
    """Solução de referência que gera a saída esperada (`expectation: reference_output`)."""

    source: PurePath
    harness: PurePath | None = None
    extra_files: tuple[PurePath, ...] = ()


@dataclass(frozen=True)
class TestCaseDefinition:
    args: tuple[str, ...] = ()
    stdin: str = ""
    expected: str | None = None


@dataclass(frozen=True)
class TestDefinition:
    generator: str
    expectation: str
    cases: tuple[TestCaseDefinition, ...] = ()


@dataclass(frozen=True)
class LimitsDefinition:
    timeout_seconds: int


@dataclass(frozen=True)
class ExerciseDefinition:
    id: str
    name: str
    subject: PurePath
    submission: SubmissionDefinition
    execution: ExecutionDefinition
    tests: TestDefinition
    limits: LimitsDefinition
    support_files: tuple[PurePath, ...] = ()
    reference: ReferenceDefinition | None = None
    topics: tuple[str, ...] = ()
    schema_version: int = 1
    language: str = "c"
    programming_language: str | None = None
    content_language: str = "pt-BR"
    activity_type: str = "exercise"
    validation_plan: ValidationPlan | None = None

    def __post_init__(self) -> None:
        if self.programming_language is None:
            object.__setattr__(self, "programming_language", self.language)
        elif self.language != self.programming_language:
            object.__setattr__(self, "language", self.programming_language)

    @property
    def activity(self) -> ActivityDefinition:
        plan = self.validation_plan or ValidationPlan(
            steps=(
                ValidationStep(
                    id="grade",
                    validator="program",
                    strategy=self.execution.type,
                    config={
                        "tests": self.tests.generator,
                        "expectation": self.tests.expectation,
                    },
                ),
            )
        )
        return ActivityDefinition(
            identity=ActivityIdentity(id=self.id, type=self.activity_type),
            title=self.name,
            subject=self.subject,
            language=self.programming_language or self.language,
            validation=plan,
            topics=self.topics,
        )

    @property
    def executable_files(self) -> tuple[PurePath, ...]:
        """Arquivos do pack que serão compilados/executados na correção."""
        files: list[PurePath] = []
        if self.execution.fixture is not None:
            files.append(self.execution.fixture)
        if self.reference is not None:
            files.append(self.reference.source)
            files.extend(self.reference.extra_files)
            if self.reference.harness is not None and self.reference.harness not in files:
                files.append(self.reference.harness)
        return tuple(files)
