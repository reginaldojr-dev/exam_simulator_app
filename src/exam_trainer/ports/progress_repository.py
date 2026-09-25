from __future__ import annotations

from datetime import datetime
from typing import Protocol

from exam_trainer.domain.entities import Attempt
from exam_trainer.domain.grading import GradingResult
from exam_trainer.domain.progress import ProgressEntry


class ProgressRepository(Protocol):
    def save_attempt(self, attempt: Attempt) -> None:
        raise NotImplementedError

    def list_attempts(self) -> list[Attempt]:
        raise NotImplementedError


class TrainerProgressRepository(ProgressRepository, Protocol):
    """Interface usada pelo coordinator (SQLiteProgressRepository). Progresso por (pack, exercício)."""

    def save_grading_result(
        self,
        pack_id: str,
        exercise_id: str,
        result: GradingResult,
        mode: str,
        submitted_at: datetime | None = None,
        session_id: str | None = None,
    ) -> None:
        raise NotImplementedError

    def adopt_legacy_attempts(self, exercise_packs: dict[str, str]) -> int:
        raise NotImplementedError

    def list_progress(self, pack_id: str | None = None) -> list[ProgressEntry]:
        raise NotImplementedError

    def progress_by_exercise(self, pack_id: str) -> dict[str, ProgressEntry]:
        raise NotImplementedError

    def progress_by_key(self) -> dict[tuple[str, str], ProgressEntry]:
        raise NotImplementedError

    def attempts_count(
        self, pack_id: str, exercise_id: str, mode: str = "training", session_id: str | None = None
    ) -> int:
        raise NotImplementedError

    def latest_attempts(self) -> dict[tuple[str, str], dict[str, object]]:
        raise NotImplementedError

    def list_activity_attempts(
        self,
        pack_id: str | None = None,
        activity_id: str | None = None,
        session_id: str | None = None,
        policy: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        raise NotImplementedError

    def modes_by_key(self) -> dict[tuple[str, str], set[str]]:
        raise NotImplementedError

    def attempt_keys(self) -> set[tuple[str, str]]:
        raise NotImplementedError

    def save_active_exam(self, state: dict[str, object]) -> None:
        raise NotImplementedError

    def load_active_exam(self) -> dict[str, object] | None:
        raise NotImplementedError

    def finish_exam(self, session_id: str, status: str, final_score: float) -> None:
        raise NotImplementedError

    def list_exam_history(self) -> list[dict[str, object]]:
        raise NotImplementedError

    def record_exam_level_result(
        self, session_id: str, level_index: int, exercise_id: str, passed: bool, attempts_count: int
    ) -> None:
        raise NotImplementedError

    def list_exam_level_results(self, session_id: str) -> list[dict[str, object]]:
        raise NotImplementedError
