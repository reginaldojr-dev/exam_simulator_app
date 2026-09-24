from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Mapping


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
