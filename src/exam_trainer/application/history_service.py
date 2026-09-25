from __future__ import annotations

from dataclasses import dataclass

from exam_trainer.domain.activity_identity import ActivityIdentity
from exam_trainer.domain.attempt_modes import LEGACY_PACK_ID
from exam_trainer.ports.progress_repository import TrainerProgressRepository


@dataclass(frozen=True)
class HistoryQuery:
    pack_id: str | None = None
    activity_id: str | None = None
    session_id: str | None = None
    policy: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class HistoryEntry:
    identity: ActivityIdentity
    policy: str
    status: str
    passed: bool | None
    score: float | None
    submitted_at: str | None
    session_id: str | None
    attempt_id: str


class HistoryService:
    """Read-only history projection. Rules stay in policies/application."""

    def __init__(self, progress_repository: TrainerProgressRepository) -> None:
        self._progress_repository = progress_repository

    def query(self, filters: HistoryQuery = HistoryQuery()) -> list[HistoryEntry]:
        rows = self._progress_repository.list_activity_attempts(
            pack_id=filters.pack_id,
            activity_id=filters.activity_id,
            session_id=filters.session_id,
            policy=filters.policy,
            status=filters.status,
        )
        return [self._entry(row) for row in rows]

    def timeline(self, filters: HistoryQuery = HistoryQuery()) -> list[HistoryEntry]:
        return self.query(filters)

    def exercise_rows(self, packs, list_exercises) -> list[dict[str, object]]:
        progress = self._progress_repository.progress_by_key()
        latest = self._progress_repository.latest_attempts()
        modes = self._progress_repository.modes_by_key()
        rows: list[dict[str, object]] = []
        shown: set[tuple[str, str]] = set()

        def row(pack_name: str, level: str, name: str, key: tuple[str, str]) -> dict[str, object]:
            entry = progress.get(key)
            status = "não feito"
            if entry is not None:
                status = "concluído" if entry.best_passed else "tentado"
            return {
                "pack": pack_name,
                "pack_id": key[0],
                "level": level,
                "name": name,
                "exercise_id": key[1],
                "activity_id": key[1],
                "activity_kind": "exercise",
                "status": status,
                "attempts": 0 if entry is None else entry.attempts_count,
                "latest_result": self._format_latest_result(latest.get(key, {})),
                "last_attempt_at": None if entry is None else entry.last_attempt_at,
                "modes": ", ".join(sorted(modes.get(key, set()))),
            }

        for pack in packs:
            for ref in list_exercises(pack.id):
                key = (pack.id, ref.definition.id)
                shown.add(key)
                rows.append(row(pack.name, ref.level_id, ref.definition.name, key))
        for key in sorted(self._progress_repository.attempt_keys() - shown):
            label = "(legado)" if key[0] == LEGACY_PACK_ID else f"{key[0]} (não instalado)"
            rows.append(row(label, "-", key[1], key))
        return rows

    def exam_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for history in self._progress_repository.list_exam_history():
            levels = self._progress_repository.list_exam_level_results(str(history["id"]))
            rows.append(
                {
                    **history,
                    "session_id": history["id"],
                    "policy": history.get("policy", "exam"),
                    "levels": levels,
                    "exercises": ", ".join(str(level["exercise_id"]) for level in levels),
                }
            )
        return rows

    @staticmethod
    def _entry(row: dict[str, object]) -> HistoryEntry:
        passed = row.get("passed")
        return HistoryEntry(
            identity=ActivityIdentity(
                pack_id=str(row["pack_id"]),
                activity_id=str(row.get("activity_id") or row["exercise_id"]),
                activity_kind=str(row.get("activity_kind") or "exercise"),
            ),
            policy=str(row.get("policy") or row.get("mode") or ""),
            status=str(row["status"]),
            passed=None if passed is None else bool(passed),
            score=None if row.get("score") is None else float(row["score"]),
            submitted_at=None if row.get("submitted_at") is None else str(row["submitted_at"]),
            session_id=None if row.get("session_id") is None else str(row["session_id"]),
            attempt_id=str(row["id"]),
        )

    @staticmethod
    def _format_latest_result(latest_attempt: dict[str, object]) -> str:
        if not latest_attempt:
            return "-"
        return "PASS" if bool(latest_attempt.get("passed")) else "FAIL"
