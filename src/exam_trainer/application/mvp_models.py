from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from exam_trainer.domain.exercise_definition import ExerciseDefinition
from exam_trainer.domain.grading import GradingResult
from exam_trainer.domain.pack_definition import DEFAULT_LANGUAGE, PackDefinition
from exam_trainer.domain.progress import ProgressEntry

__all__ = [
    "DEFAULT_LANGUAGE",
    "ExerciseRef",
    "ProgressEntry",
    "ActiveExercise",
    "CorrectionOutcome",
]


@dataclass(frozen=True)
class ExerciseRef:
    pack: PackDefinition
    level_id: str
    definition: ExerciseDefinition
    content_path: Path


# `ProgressEntry` é uma regra pura (domain/progress.py); reexportada aqui para não
# quebrar quem já importa de `application.mvp_models` (ADR 0007).


@dataclass(frozen=True)
class ActiveExercise:
    ref: ExerciseRef
    exercise_workspace_path: Path
    subject_text: str
    submission_path: Path
    had_existing_submission: bool


@dataclass(frozen=True)
class CorrectionOutcome:
    result: GradingResult
    trace_path: Path
    attempts_count: int
