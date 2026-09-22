from __future__ import annotations

from typing import Protocol

from exam_trainer.domain.entities import Attempt


class ProgressRepository(Protocol):
    def save_attempt(self, attempt: Attempt) -> None:
        raise NotImplementedError

    def list_attempts(self) -> list[Attempt]:
        raise NotImplementedError
