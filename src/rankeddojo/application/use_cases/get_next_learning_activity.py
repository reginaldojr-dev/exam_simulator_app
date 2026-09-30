"""Application use case: the single next activity a learner should attempt
in one language's track, or `None` when there is nothing left (or nothing
built yet) for that language.

Thin composition over `GetLearningTrack` -- no extra logic, no Qt.
"""

from __future__ import annotations

from rankeddojo.application.use_cases.get_learning_track import GetLearningTrack
from rankeddojo.domain.learning import LearningActivityRef


class GetNextLearningActivity:
    def __init__(self, get_learning_track: GetLearningTrack) -> None:
        self._get_learning_track = get_learning_track

    def execute(self, language: str) -> LearningActivityRef | None:
        return self._get_learning_track.execute(language).next_activity
