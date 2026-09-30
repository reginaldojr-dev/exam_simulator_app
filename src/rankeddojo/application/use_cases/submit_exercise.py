from __future__ import annotations

from pathlib import Path

from rankeddojo.domain.exercise_definition import ExerciseDefinition
from rankeddojo.domain.grading import GradingPolicy, GradingResult
from rankeddojo.ports.grader_port import GraderPort, GradingRequest


class SubmitExercise:
    def __init__(self, grader: GraderPort) -> None:
        self._grader = grader

    def execute(
        self,
        definition: ExerciseDefinition,
        exercise_path: Path,
        workspace_path: Path,
        policy: GradingPolicy,
        seed: int | None = None,
    ) -> GradingResult:
        request = GradingRequest(
            definition=definition,
            exercise_path=exercise_path,
            workspace_path=workspace_path,
            policy=policy,
            seed=seed,
        )
        return self._grader.grade(request)
