from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from exam_trainer.domain.exercise_definition import ExerciseDefinition


@dataclass(frozen=True)
class PreparedExerciseWorkspace:
    exercise_workspace_path: Path
    subject_path: Path
    submission_path: Path
    had_existing_submission: bool


class ExerciseWorkspacePort(Protocol):
    def prepare(
        self,
        definition: ExerciseDefinition,
        exercise_content_path: Path,
        workspace_root: Path,
        overwrite: bool = False,
    ) -> PreparedExerciseWorkspace:
        raise NotImplementedError
