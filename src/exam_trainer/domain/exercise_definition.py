from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath


@dataclass(frozen=True)
class SubmissionDefinition:
    filename: str


@dataclass(frozen=True)
class ExecutionDefinition:
    type: str
    fixture: PurePath | None = None
    reference: PurePath | None = None


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
