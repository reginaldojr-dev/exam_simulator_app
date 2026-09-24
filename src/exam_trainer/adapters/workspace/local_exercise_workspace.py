from __future__ import annotations

import shutil
from pathlib import Path

from exam_trainer.domain.exercise_definition import ExerciseDefinition
from exam_trainer.ports.exercise_workspace_port import PreparedExerciseWorkspace


class ExerciseWorkspaceError(RuntimeError):
    pass


class LocalExerciseWorkspace:
    def prepare(
        self,
        definition: ExerciseDefinition,
        exercise_content_path: Path,
        workspace_root: Path,
        overwrite: bool = False,
    ) -> PreparedExerciseWorkspace:
        exercise_workspace = workspace_root / definition.id
        exercise_workspace.mkdir(parents=True, exist_ok=True)

        source_subject = exercise_content_path / definition.subject
        if not source_subject.is_file():
            raise ExerciseWorkspaceError(f"Subject file not found: {source_subject}")

        subject_path = exercise_workspace / "subject.txt"
        subject_path.write_text(source_subject.read_text(encoding="utf-8"), encoding="utf-8")

        submission_path = exercise_workspace / definition.submission.filename
        had_existing_submission = submission_path.exists()
        if overwrite or not had_existing_submission:
            submission_path.write_text("", encoding="utf-8")

        for support_file in definition.support_files:
            source_support_file = exercise_content_path / support_file
            if not source_support_file.is_file():
                raise ExerciseWorkspaceError(
                    f"Support file not found: {source_support_file}"
                )
            target_support_file = exercise_workspace / support_file.name
            shutil.copy2(source_support_file, target_support_file)

        return PreparedExerciseWorkspace(
            exercise_workspace_path=exercise_workspace,
            subject_path=subject_path,
            submission_path=submission_path,
            had_existing_submission=had_existing_submission,
        )

    def move_directory(self, source: Path, target: Path) -> None:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
        except OSError:
            pass

    def remove_directory(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path)
