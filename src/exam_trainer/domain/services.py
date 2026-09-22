from __future__ import annotations

from exam_trainer.domain.entities import Attempt


class ProgressionService:
    """Domain service responsible for future progression decisions."""

    def should_record_attempt(self, attempt: Attempt) -> bool:
        return attempt.grade is not None
