from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Mapping


@dataclass(frozen=True)
class UsageCategory:
    functions: tuple[str, ...] = ()
    libraries: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()
    headers: tuple[str, ...] = ()
    apis: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not any((self.functions, self.libraries, self.imports, self.headers, self.apis, self.flags))


@dataclass(frozen=True)
class UsageConstraints:
    """Restrições declarativas/pedagógicas da activity.

    Elas são parte do contrato do conteúdo. O loader valida a forma; validators
    podem evoluir para aplicar subconjuntos verificáveis sem a UI fazer parsing
    de subject.
    """

    allowed: UsageCategory = field(default_factory=UsageCategory)
    forbidden: UsageCategory = field(default_factory=UsageCategory)
    constraints: tuple[str, ...] = ()
    style: tuple[str, ...] = ()
    behavior: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return (
            self.allowed.is_empty
            and self.forbidden.is_empty
            and not self.constraints
            and not self.style
            and not self.behavior
            and not self.notes
        )


@dataclass(frozen=True)
class ActivityIdentity:
    id: str
    type: str = "exercise"


@dataclass(frozen=True)
class ValidationStep:
    id: str
    validator: str
    strategy: str
    config: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationPlan:
    steps: tuple[ValidationStep, ...]

    @property
    def primary(self) -> ValidationStep:
        return self.steps[0]


@dataclass(frozen=True)
class ActivityDefinition:
    identity: ActivityIdentity
    title: str
    subject: PurePath
    language: str
    validation: ValidationPlan
    topics: tuple[str, ...] = ()
    usage: UsageConstraints = field(default_factory=UsageConstraints)
