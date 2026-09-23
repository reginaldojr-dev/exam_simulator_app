from __future__ import annotations

from datetime import datetime
from uuid import UUID

from exam_trainer.adapters.persistence.migrations import rebuild_progress
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.application.mvp_models import ProgressEntry
from exam_trainer.domain.attempt_modes import ATTEMPT_MODES, LEGACY_PACK_ID, TRAINING_MODE
from exam_trainer.domain.entities import Attempt
from exam_trainer.domain.grading import GradingResult
from exam_trainer.domain.value_objects import AttemptStatus, Grade


class SQLiteProgressRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store
        self._store.initialize()

    def save_attempt(
        self,
        attempt: Attempt,
        pack_id: str = LEGACY_PACK_ID,
        mode: str = TRAINING_MODE,
    ) -> None:
        passed = None if attempt.grade is None else int(attempt.grade.passed)
        self._insert_attempt(
            attempt_id=str(attempt.id),
            pack_id=pack_id,
            exercise_id=attempt.exercise_id,
            status=attempt.status.value,
            passed=passed,
            score=None if attempt.grade is None else attempt.grade.score,
            message=None if attempt.grade is None else attempt.grade.message,
            submitted_at=None if attempt.submitted_at is None else attempt.submitted_at.isoformat(),
            mode=mode,
            session_id=None,
        )

    def save_grading_result(
        self,
        pack_id: str,
        exercise_id: str,
        result: GradingResult,
        mode: str,
        submitted_at: datetime | None = None,
        session_id: str | None = None,
    ) -> None:
        attempt = Attempt(exercise_id=exercise_id)
        attempt.mark_submitted(submitted_at or datetime.now())
        score = 100 if result.passed else 0
        attempt.mark_graded(Grade(passed=result.passed, score=score, message=f"seed={result.seed}"))
        self._insert_attempt(
            attempt_id=str(attempt.id),
            pack_id=pack_id,
            exercise_id=exercise_id,
            status=attempt.status.value,
            passed=int(result.passed),
            score=score,
            message=f"seed={result.seed}",
            submitted_at=attempt.submitted_at.isoformat() if attempt.submitted_at else None,
            mode=mode,
            session_id=session_id,
        )

    def _insert_attempt(self, **row: object) -> None:
        if row["mode"] not in ATTEMPT_MODES:
            raise ValueError(f"Unknown attempt mode: {row['mode']!r}")
        with self._store.session() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO attempts (
                    id, pack_id, exercise_id, status, passed, score, message,
                    submitted_at, mode, session_id
                )
                VALUES (
                    :attempt_id, :pack_id, :exercise_id, :status, :passed, :score, :message,
                    :submitted_at, :mode, :session_id
                )
                """,
                row,
            )
            if row["mode"] == TRAINING_MODE:
                # Só treino mexe no progresso pedagógico (ADR 0003).
                rebuild_progress(connection, str(row["pack_id"]), str(row["exercise_id"]))

    def adopt_legacy_attempts(self, exercise_packs: dict[str, str]) -> int:
        """Associa tentativas `_legacy` ao pack do catálogo (exercise_id -> pack_id único).

        Só recebe ids que existem em exatamente um pack instalado; o resto continua legado.
        Retorna quantas tentativas foram associadas.
        """
        if not exercise_packs:
            return 0
        adopted = 0
        with self._store.session() as connection:
            rows = connection.execute(
                "SELECT DISTINCT exercise_id FROM attempts WHERE pack_id = ?",
                (LEGACY_PACK_ID,),
            ).fetchall()
            for row in rows:
                pack_id = exercise_packs.get(row["exercise_id"])
                if pack_id is None:
                    continue
                cursor = connection.execute(
                    "UPDATE attempts SET pack_id = ? WHERE pack_id = ? AND exercise_id = ?",
                    (pack_id, LEGACY_PACK_ID, row["exercise_id"]),
                )
                adopted += cursor.rowcount
                rebuild_progress(connection, LEGACY_PACK_ID, row["exercise_id"])
                rebuild_progress(connection, pack_id, row["exercise_id"])
        return adopted

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

    def list_progress(self, pack_id: str | None = None) -> list[ProgressEntry]:
        """Progresso pedagógico (só treino), opcionalmente de um pack."""
        query = """
            SELECT pack_id, exercise_id, status, attempts_count, last_attempt_at,
                   best_passed, best_score, last_mode
            FROM progress
        """
        params: tuple[str, ...] = ()
        if pack_id is not None:
            query += " WHERE pack_id = ?"
            params = (pack_id,)
        with self._store.session() as connection:
            rows = connection.execute(query + " ORDER BY pack_id, exercise_id", params).fetchall()
        return [
            ProgressEntry(
                exercise_id=row["exercise_id"],
                status=row["status"],
                attempts_count=row["attempts_count"],
                last_attempt_at=row["last_attempt_at"],
                best_passed=bool(row["best_passed"]),
                best_score=row["best_score"],
                last_mode=row["last_mode"],
                pack_id=row["pack_id"],
            )
            for row in rows
        ]

    def progress_by_exercise(self, pack_id: str) -> dict[str, ProgressEntry]:
        return {entry.exercise_id: entry for entry in self.list_progress(pack_id)}

    def progress_by_key(self) -> dict[tuple[str, str], ProgressEntry]:
        return {(entry.pack_id, entry.exercise_id): entry for entry in self.list_progress()}

    def attempts_count(
        self,
        pack_id: str,
        exercise_id: str,
        mode: str = TRAINING_MODE,
        session_id: str | None = None,
    ) -> int:
        query = "SELECT COUNT(*) FROM attempts WHERE pack_id = ? AND exercise_id = ? AND mode = ?"
        params: tuple[str, ...] = (pack_id, exercise_id, mode)
        if session_id is not None:
            query += " AND session_id = ?"
            params += (session_id,)
        with self._store.session() as connection:
            return int(connection.execute(query, params).fetchone()[0])

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

    def latest_attempts(self) -> dict[tuple[str, str], dict[str, object]]:
        """Última tentativa (treino ou prova) de cada (pack_id, exercise_id)."""
        with self._store.session() as connection:
            rows = connection.execute(
                """
                SELECT a.pack_id, a.exercise_id, a.passed, a.submitted_at, a.mode
                FROM attempts a
                INNER JOIN (
                    SELECT pack_id, exercise_id, MAX(submitted_at) AS submitted_at
                    FROM attempts
                    GROUP BY pack_id, exercise_id
                ) latest
                ON latest.pack_id = a.pack_id
                AND latest.exercise_id = a.exercise_id
                AND latest.submitted_at = a.submitted_at
                """
            ).fetchall()
        return {(row["pack_id"], row["exercise_id"]): dict(row) for row in rows}

    def modes_by_key(self) -> dict[tuple[str, str], set[str]]:
        with self._store.session() as connection:
            rows = connection.execute(
                "SELECT DISTINCT pack_id, exercise_id, mode FROM attempts WHERE mode IS NOT NULL"
            ).fetchall()
        modes: dict[tuple[str, str], set[str]] = {}
        for row in rows:
            modes.setdefault((row["pack_id"], row["exercise_id"]), set()).add(row["mode"])
        return modes

    def attempt_keys(self) -> set[tuple[str, str]]:
        with self._store.session() as connection:
            rows = connection.execute("SELECT DISTINCT pack_id, exercise_id FROM attempts").fetchall()
        return {(row["pack_id"], row["exercise_id"]) for row in rows}
