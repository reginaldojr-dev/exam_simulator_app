from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TrainingMode(str, Enum):
    LEVEL = "level"
    RANDOM = "random"
    EXAM = "exam"


class AttemptStatus(str, Enum):
    CREATED = "created"
    SUBMITTED = "submitted"
    GRADED = "graded"


@dataclass(frozen=True)
class Grade:
    passed: bool
    score: float | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if self.score is not None and not 0 <= self.score <= 100:
            raise ValueError("Grade score must be between 0 and 100.")
