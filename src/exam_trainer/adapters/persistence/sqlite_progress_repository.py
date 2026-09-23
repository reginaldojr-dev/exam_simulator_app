from __future__ import annotations

from datetime import datetime
from uuid import UUID

from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.application.mvp_models import ProgressEntry
from exam_trainer.domain.entities import Attempt
from exam_trainer.domain.grading import GradingResult
from exam_trainer.domain.value_objects import AttemptStatus, Grade


class SQLiteProgressRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store
        self._store.initialize()

    def save_attempt(self, attempt: Attempt) -> None:
        passed = None if attempt.grade is None else int(attempt.grade.passed)
        score = None if attempt.grade is None else attempt.grade.score
        message = None if attempt.grade is None else attempt.grade.message
        submitted_at = (
            None if attempt.submitted_at is None else attempt.submitted_at.isoformat()
        )

        with self._store.session() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO attempts (
                    id, exercise_id, status, passed, score, message, submitted_at, mode
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(attempt.id),
                    attempt.exercise_id,
                    attempt.status.value,
                    passed,
                    score,
                    message,
                    submitted_at,
                    None,
                ),
            )
            connection.execute(
                """
                INSERT INTO progress (
                    exercise_id, status, attempts_count, last_attempt_at,
                    best_passed, best_score, last_mode
                )
                VALUES (?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(exercise_id) DO UPDATE SET
                    status = excluded.status,
                    attempts_count = progress.attempts_count + 1,
                    last_attempt_at = excluded.last_attempt_at,
                    best_passed = MAX(progress.best_passed, excluded.best_passed),
                    best_score = CASE
                        WHEN progress.best_score IS NULL THEN excluded.best_score
                        WHEN excluded.best_score IS NULL THEN progress.best_score
                        ELSE MAX(progress.best_score, excluded.best_score)
                    END,
                    last_mode = excluded.last_mode
                """,
                (
                    attempt.exercise_id,
                    self._progress_status(attempt),
                    submitted_at,
                    0 if passed is None else passed,
                    score,
                    None,
                ),
            )

    def save_grading_result(
        self,
        exercise_id: str,
        result: GradingResult,
        mode: str,
        submitted_at: datetime | None = None,
    ) -> None:
        attempt = Attempt(exercise_id=exercise_id)
        attempt.mark_submitted(submitted_at or datetime.now())
        attempt.mark_graded(
            Grade(
                passed=result.passed,
                score=100 if result.passed else 0,
                message=f"seed={result.seed}",
            )
        )
        passed = int(result.passed)
        submitted_iso = attempt.submitted_at.isoformat() if attempt.submitted_at else None
        with self._store.session() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO attempts (
                    id, exercise_id, status, passed, score, message, submitted_at, mode
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(attempt.id),
                    exercise_id,
                    attempt.status.value,
                    passed,
                    100 if result.passed else 0,
                    f"seed={result.seed}",
                    submitted_iso,
                    mode,
                ),
            )
            connection.execute(
                """
                INSERT INTO progress (
                    exercise_id, status, attempts_count, last_attempt_at,
                    best_passed, best_score, last_mode
                )
                VALUES (?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(exercise_id) DO UPDATE SET
                    status = excluded.status,
                    attempts_count = progress.attempts_count + 1,
                    last_attempt_at = excluded.last_attempt_at,
                    best_passed = MAX(progress.best_passed, excluded.best_passed),
                    best_score = MAX(COALESCE(progress.best_score, 0), excluded.best_score),
                    last_mode = excluded.last_mode
                """,
                (
                    exercise_id,
                    "completed" if result.passed else "attempted",
                    submitted_iso,
                    passed,
                    100 if result.passed else 0,
                    mode,
                ),
            )

    def list_attempts(self) -> list[Attempt]:
        with self._store.session() as connection:
            rows = connection.execute(
                """
                SELECT id, exercise_id, status, passed, score, message, submitted_at
                FROM attempts
                ORDER BY submitted_at DESC
                """
            ).fetchall()

        attempts: list[Attempt] = []
        for row in rows:
            grade = None
            if row["passed"] is not None:
                grade = Grade(
                    passed=bool(row["passed"]),
                    score=row["score"],
                    message=row["message"] or "",
                )
            submitted_at = None
            if row["submitted_at"] is not None:
                submitted_at = datetime.fromisoformat(row["submitted_at"])
            attempts.append(
                Attempt(
                    exercise_id=row["exercise_id"],
                    id=UUID(row["id"]),
                    status=AttemptStatus(row["status"]),
                    grade=grade,
                    submitted_at=submitted_at,
                )
            )
        return attempts

    def list_progress(self) -> list[ProgressEntry]:
        with self._store.session() as connection:
            rows = connection.execute(
                """
                SELECT exercise_id, status, attempts_count, last_attempt_at,
                       best_passed, best_score, last_mode
                FROM progress
                ORDER BY exercise_id
                """
            ).fetchall()
        return [
            ProgressEntry(
                exercise_id=row["exercise_id"],
                status=row["status"],
                attempts_count=row["attempts_count"],
                last_attempt_at=row["last_attempt_at"],
                best_passed=bool(row["best_passed"]),
                best_score=row["best_score"],
                last_mode=row["last_mode"],
            )
            for row in rows
        ]

    def progress_by_exercise(self) -> dict[str, ProgressEntry]:
        return {entry.exercise_id: entry for entry in self.list_progress()}

    def attempts_count(self, exercise_id: str) -> int:
        entry = self.progress_by_exercise().get(exercise_id)
        return 0 if entry is None else entry.attempts_count

    def save_active_exam(self, state: dict[str, object]) -> None:
        with self._store.session() as connection:
            existing = connection.execute(
                "SELECT started_at FROM exam_sessions WHERE id = ?",
                (state["id"],),
            ).fetchone()
            started_at = (
                existing["started_at"]
                if existing is not None and existing["started_at"] is not None
                else state["started_at"]
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO exam_sessions (
                    id, rank, current_level, current_exercise_id, score,
                    remaining_seconds, seed, status, workspace_path,
                    started_at, finished_at, deadline_at, duration_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state["id"],
                    state["rank"],
                    state["current_level"],
                    state["current_exercise_id"],
                    state["score"],
                    state["remaining_seconds"],
                    state["seed"],
                    state["status"],
                    state["workspace_path"],
                    started_at,
                    state.get("finished_at"),
                    state.get("deadline_at"),
                    state.get("duration_seconds"),
                ),
            )

    def load_active_exam(self) -> dict[str, object] | None:
        with self._store.session() as connection:
            row = connection.execute(
                """
                SELECT id, rank, current_level, current_exercise_id, score,
                       remaining_seconds, seed, status, workspace_path,
                       started_at, finished_at, deadline_at, duration_seconds
                FROM exam_sessions
                WHERE status = 'active'
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()
        return None if row is None else dict(row)

    def finish_exam(self, session_id: str, status: str, final_score: float) -> None:
        finished_at = datetime.now().isoformat()
        with self._store.session() as connection:
            row = connection.execute(
                "SELECT rank, started_at FROM exam_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            used_seconds = None
            if row is not None and row["started_at"] is not None:
                used_seconds = int(
                    (
                        datetime.fromisoformat(finished_at)
                        - datetime.fromisoformat(row["started_at"])
                    ).total_seconds()
                )
            connection.execute(
                """
                UPDATE exam_sessions
                SET status = ?, score = ?, finished_at = ?
                WHERE id = ?
                """,
                (status, final_score, finished_at, session_id),
            )
            if row is not None:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO exam_history (
                        id, rank, final_score, status, used_seconds, finished_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session_id, row["rank"], final_score, status, used_seconds, finished_at),
                )

    def list_exam_history(self) -> list[dict[str, object]]:
        with self._store.session() as connection:
            rows = connection.execute(
                """
                SELECT id, rank, final_score, status, used_seconds, finished_at
                FROM exam_history
                ORDER BY finished_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def record_exam_level_result(
        self,
        session_id: str,
        level_index: int,
        exercise_id: str,
        passed: bool,
        attempts_count: int,
    ) -> None:
        with self._store.session() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO exam_level_results (
                    session_id, level_index, exercise_id, passed,
                    attempts_count, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    level_index,
                    exercise_id,
                    int(passed),
                    attempts_count,
                    datetime.now().isoformat(),
                ),
            )

    def list_exam_level_results(self, session_id: str) -> list[dict[str, object]]:
        with self._store.session() as connection:
            rows = connection.execute(
                """
                SELECT session_id, level_index, exercise_id, passed,
                       attempts_count, updated_at
                FROM exam_level_results
                WHERE session_id = ?
                ORDER BY level_index
                """,
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_attempts_by_exercise(self) -> dict[str, dict[str, object]]:
        with self._store.session() as connection:
            rows = connection.execute(
                """
                SELECT a.exercise_id, a.passed, a.submitted_at, a.mode
                FROM attempts a
                INNER JOIN (
                    SELECT exercise_id, MAX(submitted_at) AS submitted_at
                    FROM attempts
                    GROUP BY exercise_id
                ) latest
                ON latest.exercise_id = a.exercise_id
                AND latest.submitted_at = a.submitted_at
                """
            ).fetchall()
        return {row["exercise_id"]: dict(row) for row in rows}

    def modes_by_exercise(self) -> dict[str, set[str]]:
        with self._store.session() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT exercise_id, mode
                FROM attempts
                WHERE mode IS NOT NULL
                """
            ).fetchall()
        modes: dict[str, set[str]] = {}
        for row in rows:
            modes.setdefault(row["exercise_id"], set()).add(row["mode"])
        return modes

    @staticmethod
    def _progress_status(attempt: Attempt) -> str:
        if attempt.grade is None:
            return "attempted"
        return "completed" if attempt.grade.passed else "attempted"
