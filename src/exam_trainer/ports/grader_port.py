from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from exam_trainer.domain.exercise_definition import ExerciseDefinition
from exam_trainer.domain.grading import GradingPolicy, GradingResult


@dataclass(frozen=True)
class GradingRequest:
    definition: ExerciseDefinition
    exercise_path: Path
    workspace_path: Path
    policy: GradingPolicy
    seed: int | None = None


class GraderPort(Protocol):
    def grade(self, request: GradingRequest) -> GradingResult:
        raise NotImplementedError
