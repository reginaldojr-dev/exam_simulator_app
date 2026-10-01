"""Application use case: read one language's learning track together with
progress already recorded for it.

No Qt, no filesystem: this composes the pure `domain.learning` functions
with `ContentRegistry` (content) and `TrainerProgressRepository` (progress),
both already-existing sources of truth -- there is no second progress
store here, only a read against the one that exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from rankeddojo.application.engine.content_registry import ContentRegistry
from rankeddojo.domain.learning import (
    LearningActivityRef,
    LearningTrack,
    current_level,
    is_activity_unlocked,
    select_next_activity,
)
from rankeddojo.domain.progress import ActivityProgress
from rankeddojo.ports.progress_repository import TrainerProgressRepository


@dataclass(frozen=True)
class LearningTrackView:
    """Read-only snapshot of a track plus the progress derived against it."""

    track: LearningTrack
    completed_activity_ids: frozenset[str]
    current_level: int
    next_activity: LearningActivityRef | None


class GetLearningTrack:
    def __init__(
        self,
        content_registry: ContentRegistry,
        progress_repository: TrainerProgressRepository,
    ) -> None:
        self._content_registry = content_registry
        self._progress_repository = progress_repository

    def execute(self, language: str) -> LearningTrackView:
        track = self._content_registry.track(language)
        completed = self._completed_activity_ids(track)
        return LearningTrackView(
            track=track,
            completed_activity_ids=completed,
            current_level=current_level(track, completed),
            next_activity=select_next_activity(track, completed),
        )

    def _completed_activity_ids(self, track: LearningTrack) -> frozenset[str]:
        progress_by_key = self._progress_repository.progress_by_key()
        completed: set[str] = set()
        for ref in track.activities:
            entry = progress_by_key.get(ref.progress_key)
            if entry is not None and entry.status == ActivityProgress.COMPLETED.value:
                completed.add(ref.activity_id)
        return frozenset(completed)
