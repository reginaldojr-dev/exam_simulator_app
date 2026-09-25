from __future__ import annotations

from dataclasses import dataclass

DEFAULT_ACTIVITY_KIND = "exercise"


@dataclass(frozen=True, order=True)
class ActivityIdentity:
    """Stable identity for progress/history across activity kinds."""

    pack_id: str
    activity_id: str
    activity_kind: str = DEFAULT_ACTIVITY_KIND

    @classmethod
    def exercise(cls, pack_id: str, exercise_id: str) -> "ActivityIdentity":
        return cls(pack_id=pack_id, activity_id=exercise_id)
