from __future__ import annotations

from exam_trainer.domain.entities import TrainingSession
from exam_trainer.domain.value_objects import TrainingMode


class StartTraining:
    def execute(self, mode: TrainingMode) -> TrainingSession:
        raise NotImplementedError("Training modes are not implemented yet.")
