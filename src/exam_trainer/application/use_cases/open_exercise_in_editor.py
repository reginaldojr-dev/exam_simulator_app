from __future__ import annotations

from pathlib import Path

from exam_trainer.ports.editor_port import EditorPort


class OpenExerciseInEditor:
    def __init__(self, editor: EditorPort) -> None:
        self._editor = editor

    def execute(self, exercise_directory: Path) -> None:
        self._editor.open_directory(exercise_directory)
