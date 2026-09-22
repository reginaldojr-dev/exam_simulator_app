from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from exam_trainer.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from exam_trainer.domain.exercise_definition import (
    ExerciseDefinition,
    ExecutionDefinition,
    LimitsDefinition,
    SubmissionDefinition,
    TestDefinition,
)


def definition() -> ExerciseDefinition:
    return ExerciseDefinition(
        id="echo_args",
        name="Echo Args",
        subject=Path("subject.md"),
        submission=SubmissionDefinition(filename="echo_args.c"),
        execution=ExecutionDefinition(type="program_output"),
        tests=TestDefinition(generator="random_arguments", expectation="echo_arguments"),
        limits=LimitsDefinition(timeout_seconds=2),
    )


class ExerciseWorkspaceTest(unittest.TestCase):
    def test_prepares_subject_and_submission_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            workspace = root / "workspace"
            content.mkdir()
            (content / "subject.md").write_text("# Subject\n", encoding="utf-8")

            prepared = LocalExerciseWorkspace().prepare(
                definition(),
                exercise_content_path=content,
                workspace_root=workspace,
            )

            self.assertEqual(prepared.subject_path.read_text(encoding="utf-8"), "# Subject\n")
            self.assertTrue(prepared.submission_path.is_file())
            self.assertFalse(prepared.had_existing_submission)

    def test_preserves_existing_submission_unless_overwrite_is_true(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            workspace = root / "workspace"
            content.mkdir()
            (content / "subject.md").write_text("# Subject\n", encoding="utf-8")
            exercise_workspace = workspace / "echo_args"
            exercise_workspace.mkdir(parents=True)
            submission = exercise_workspace / "echo_args.c"
            submission.write_text("keep me", encoding="utf-8")

            prepared = LocalExerciseWorkspace().prepare(
                definition(),
                exercise_content_path=content,
                workspace_root=workspace,
            )

            self.assertTrue(prepared.had_existing_submission)
            self.assertEqual(submission.read_text(encoding="utf-8"), "keep me")

            LocalExerciseWorkspace().prepare(
                definition(),
                exercise_content_path=content,
                workspace_root=workspace,
                overwrite=True,
            )
            self.assertEqual(submission.read_text(encoding="utf-8"), "")
