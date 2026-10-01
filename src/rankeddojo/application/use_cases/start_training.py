from __future__ import annotations

from rankeddojo.domain.entities import TrainingSession
from rankeddojo.domain.value_objects import TrainingMode


class StartTraining:
    def execute(self, mode: TrainingMode) -> TrainingSession:
        raise NotImplementedError("Training modes are not implemented yet.")
