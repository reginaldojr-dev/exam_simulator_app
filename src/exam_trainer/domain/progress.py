from __future__ import annotations

from dataclasses import dataclass

from exam_trainer.domain.activity_identity import DEFAULT_ACTIVITY_KIND, ActivityIdentity


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
