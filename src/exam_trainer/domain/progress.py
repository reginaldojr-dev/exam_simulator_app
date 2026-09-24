from __future__ import annotations

from dataclasses import dataclass


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
