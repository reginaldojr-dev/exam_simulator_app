from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rankeddojo.domain.activity_identity import DEFAULT_ACTIVITY_KIND, ActivityIdentity


class ActivityProgress(str, Enum):
    """Locale-independent training progress for one activity (ADR pending).

    `ProgressEntry.status` is stored and read as these same string values
    (`"completed"` / `"attempted"`); this enum exists so application/UI code
    compares against a stable, typed value instead of a literal string -- and
    never against a translated label. Translation to a displayed string
    happens only at the UI boundary, never here.
    """

    COMPLETED = "completed"
    ATTEMPTED = "attempted"
    NOT_STARTED = "not_started"


@dataclass(frozen=True)
class ProgressEntry:
    exercise_id: str
    status: str
    attempts_count: int
    last_attempt_at: str | None
    best_passed: bool
    best_score: float | None
    last_mode: str | None
    pack_id: str = ""
    activity_kind: str = DEFAULT_ACTIVITY_KIND

    @property
    def activity_id(self) -> str:
        return self.exercise_id

    @property
    def identity(self) -> ActivityIdentity:
        return ActivityIdentity(
            pack_id=self.pack_id,
            activity_id=self.activity_id,
            activity_kind=self.activity_kind,
        )
