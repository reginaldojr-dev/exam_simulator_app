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


@dataclass(frozen=True)
class WorkspaceScope:
    kind: str
    pack_id: str | None = None
    session_id: str | None = None
    owner_id: str | None = None


class ExerciseWorkspacePort(Protocol):
    def root_for(self, workspace_root: Path, scope: WorkspaceScope) -> Path:
        raise NotImplementedError

    def prepare(
        self,
        definition: ExerciseDefinition,
        exercise_content_path: Path,
        workspace_root: Path,
        overwrite: bool = False,
    ) -> PreparedExerciseWorkspace:
        raise NotImplementedError

    def prepare_scoped(
        self,
        definition: ExerciseDefinition,
        exercise_content_path: Path,
        workspace_root: Path,
        scope: WorkspaceScope,
        overwrite: bool = False,
    ) -> PreparedExerciseWorkspace:
        raise NotImplementedError

    def move_directory(self, source: Path, target: Path) -> None:
        """Migra `source` para `target` (best-effort; nunca levanta). Usado para migrar
        layouts antigos de workspace sem apagar nada."""
        raise NotImplementedError

    def remove_directory(self, path: Path) -> None:
        """Remove `path` recursivamente, se existir. Usado para limpar sessões de prova
        encerradas."""
        raise NotImplementedError
