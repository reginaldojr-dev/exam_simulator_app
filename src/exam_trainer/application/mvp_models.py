from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from exam_trainer.domain.exercise_definition import ExerciseDefinition
from exam_trainer.domain.grading import GradingResult
from exam_trainer.domain.pack_definition import PackDefinition


@dataclass(frozen=True)
class ExerciseRef:
    pack: PackDefinition
    level_id: str
    definition: ExerciseDefinition
    content_path: Path


@dataclass(frozen=True)
class ProgressEntry:
    exercise_id: str
    status: str
    attempts_count: int
    last_attempt_at: str | None
    best_passed: bool
    best_score: float | None
    last_mode: str | None
    pack_id: str = ""


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
