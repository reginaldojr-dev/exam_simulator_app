from __future__ import annotations

from pathlib import Path

from exam_trainer.domain.exercise_definition import ExerciseDefinition
from exam_trainer.ports.exercise_workspace_port import (
    ExerciseWorkspacePort,
    PreparedExerciseWorkspace,
)


class PrepareExerciseWorkspace:
    def __init__(self, workspace: ExerciseWorkspacePort) -> None:
        self._workspace = workspace

    def execute(
        self,
        definition: ExerciseDefinition,
        exercise_content_path: Path,
        workspace_root: Path,
        overwrite: bool = False,
    ) -> PreparedExerciseWorkspace:
        return self._workspace.prepare(
            definition=definition,
            exercise_content_path=exercise_content_path,
            workspace_root=workspace_root,
            overwrite=overwrite,
        )
