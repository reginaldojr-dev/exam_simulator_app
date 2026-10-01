from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rankeddojo.domain.exercise_definition import ExerciseDefinition
from rankeddojo.domain.grading import GradingOutcome, GradingResult
from rankeddojo.domain.pack_definition import DEFAULT_LANGUAGE, PackDefinition
from rankeddojo.domain.progress import ActivityProgress, ProgressEntry

__all__ = [
    "DEFAULT_LANGUAGE",
    "ExerciseRef",
    "ProgressEntry",
    "ActivityProgress",
    "GradingOutcome",
    "ActiveExercise",
    "CorrectionOutcome",
    "LastSessionSummary",
]


@dataclass(frozen=True)
class ExerciseRef:
    pack: PackDefinition
    level_id: str
    definition: ExerciseDefinition
    content_path: Path


# `ProgressEntry`/`ActivityProgress` (domain/progress.py) and `GradingOutcome`
# (domain/grading.py) are pure rules; re-exported here so adapters (e.g. UI)
# only import `application`, never `domain` directly (ADR 0007 / architecture
# boundary test).


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


@dataclass(frozen=True)
class LastSessionSummary:
    """The most recent *training* attempt across all packs, for the Home
    screen's "LAST SESSION" block. Built from attempt history + pack catalog
    data the application layer already exposes elsewhere (same building
    blocks `exercise_ref_for_activity`/`exercise_history_rows` use) -- no new
    persistence or schema. `pack_name`/`activity_name`/`language` fall back to
    the raw ids when the pack is no longer installed, rather than guessing.
    """

    pack_id: str
    pack_name: str
    activity_id: str
    activity_name: str
    language: str
    mode: str
    completed_count: int
    total_count: int
