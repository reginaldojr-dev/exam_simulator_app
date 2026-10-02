from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from rankeddojo.domain.activity_identity import ActivityIdentity
from rankeddojo.domain.attempt_modes import LEGACY_PACK_ID
from rankeddojo.domain.progress import ActivityProgress
from rankeddojo.ports.progress_repository import TrainerProgressRepository


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


@dataclass(frozen=True)
class AttemptSummary:
    attempt_id: str
    number: int
    activity_id: str
    activity_title: str
    pack_id: str
    policy: str
    status: str
    result: str
    submitted_at: str | None
    session_id: str | None
    score: float | None
    trace_available: bool = False
    failure_summary: str = ""


@dataclass(frozen=True)
class ActivityHistorySummary:
    pack_id: str
    activity_id: str
    title: str
    level: str
    status: ActivityProgress
    attempts_count: int
    latest_result: str
    latest_at: str | None
    attempts: tuple[AttemptSummary, ...] = ()


@dataclass(frozen=True)
class PackHistorySummary:
    pack_id: str
    name: str
    activities_count: int
    completed_count: int
    attempts_count: int
    latest_at: str | None
    activities: tuple[ActivityHistorySummary, ...] = ()


@dataclass(frozen=True)
class SessionActivitySummary:
    activity_id: str
    result: str
    attempts_count: int
    updated_at: str | None


@dataclass(frozen=True)
class SessionHistorySummary:
    session_id: str
    policy: str
    pack_id: str
    status: str
    finished_at: str | None
    duration_seconds: int | None
    score: float | None
    activities_count: int
    activities: tuple[SessionActivitySummary, ...] = ()


@dataclass(frozen=True)
class HistoryOverviewSummary:
    completed_activity_count: int
    attempted_activity_count: int
    attempt_count: int
    pack_count: int
    exam_session_count: int
    exam_passed_count: int
    exam_failed_count: int
    exam_timed_out_count: int
    exam_abandoned_count: int
    recent: tuple[HistoryEntry, ...]

    @property
    def completed(self) -> int:
        return self.completed_activity_count

    @property
    def attempted(self) -> int:
        return self.attempted_activity_count

    @property
    def attempts(self) -> int:
        return self.attempt_count

    @property
    def packs(self) -> int:
        return self.pack_count

    @property
    def exams(self) -> int:
        return self.exam_session_count


@dataclass(frozen=True)
class ExamHistorySummary:
    sessions: tuple[SessionHistorySummary, ...]
    passed_count: int
    failed_count: int
    timed_out_count: int
    abandoned_count: int


@dataclass(frozen=True)
class TrainingVolumeSummary:
    total_attempts: int
    daily_counts: tuple[int, ...]


@dataclass(frozen=True)
class RecentSessionSummary:
    kind: str
    pack_id: str
    timestamp: str | None
    result: str
    activities_count: int
    attempts_count: int = 0
    completed_count: int = 0


@dataclass(frozen=True)
class LearningHistorySummary:
    language: str
    current_level: int
    completed_count: int
    total_count: int
    current_activity_id: str | None


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

    def overview(self, filters: HistoryQuery = HistoryQuery()) -> HistoryOverviewSummary:
        progress = list(self._progress_repository.progress_by_key().values())
        attempts = self.query(filters)
        if filters.pack_id is not None:
            progress = [entry for entry in progress if entry.pack_id == filters.pack_id]
        completed = sum(1 for entry in progress if entry.best_passed)
        attempted = sum(1 for entry in progress if entry.attempts_count > 0)
        packs = len({entry.pack_id for entry in progress} | {entry.identity.pack_id for entry in attempts})
        exam_rows = self._progress_repository.list_exam_history()
        if filters.pack_id is not None:
            exam_rows = [row for row in exam_rows if str(row.get("rank") or row.get("pack_id") or "") == filters.pack_id]
        exams = len(exam_rows)
        exam_statuses = [str(row.get("status") or "").lower() for row in exam_rows]
        if filters.policy is not None and filters.policy != "exam":
            exams = 0
            exam_statuses = []
        return HistoryOverviewSummary(
            completed_activity_count=completed,
            attempted_activity_count=attempted,
            attempt_count=len(attempts),
            pack_count=packs,
            exam_session_count=exams,
            exam_passed_count=exam_statuses.count("passed") + exam_statuses.count("completed"),
            exam_failed_count=exam_statuses.count("failed"),
            exam_timed_out_count=exam_statuses.count("timed_out") + exam_statuses.count("timeout"),
            exam_abandoned_count=exam_statuses.count("abandoned"),
            recent=tuple(attempts[:5]),
        )

    def pack_summaries(self, packs, list_exercises) -> tuple[PackHistorySummary, ...]:
        return tuple(
            summary
            for pack in packs
            if (summary := self.pack_summary(pack.id, packs, list_exercises)) is not None
        )

    def pack_summary(self, pack_id: str, packs, list_exercises) -> PackHistorySummary | None:
        pack = next((candidate for candidate in packs if candidate.id == pack_id), None)
        if pack is None:
            return None
        activities = tuple(self._activity_summary(pack.id, ref) for ref in list_exercises(pack.id))
        latest_values = [activity.latest_at for activity in activities if activity.latest_at]
        return PackHistorySummary(
            pack_id=pack.id,
            name=pack.name,
            activities_count=len(activities),
            completed_count=sum(1 for activity in activities if activity.status == ActivityProgress.COMPLETED),
            attempts_count=sum(activity.attempts_count for activity in activities),
            latest_at=max(latest_values) if latest_values else None,
            activities=activities,
        )

    def activity_summary(self, pack_id: str, activity_id: str, packs, list_exercises) -> ActivityHistorySummary | None:
        for ref in list_exercises(pack_id):
            if ref.definition.id == activity_id:
                return self._activity_summary(pack_id, ref, include_attempts=True)
        return None

    def session_summaries(self) -> tuple[SessionHistorySummary, ...]:
        sessions: list[SessionHistorySummary] = []
        for row in self._progress_repository.list_exam_history():
            levels = self._progress_repository.list_exam_level_results(str(row["id"]))
            activities = tuple(
                SessionActivitySummary(
                    activity_id=str(level.get("activity_id") or level.get("exercise_id")),
                    result="PASS" if bool(level.get("passed")) else "FAIL",
                    attempts_count=int(level.get("attempts_count") or 0),
                    updated_at=None if level.get("updated_at") is None else str(level["updated_at"]),
                )
                for level in levels
            )
            score = row.get("final_score")
            sessions.append(
                SessionHistorySummary(
                    session_id=str(row["id"]),
                    policy=str(row.get("policy") or "exam"),
                    pack_id=str(row.get("rank") or row.get("pack_id") or ""),
                    status=str(row.get("status") or ""),
                    finished_at=None if row.get("finished_at") is None else str(row["finished_at"]),
                    duration_seconds=None if row.get("used_seconds") is None else int(row["used_seconds"]),
                    score=None if score is None else float(score),
                    activities_count=len(activities),
                    activities=activities,
                )
            )
        return tuple(sessions)

    def exam_summaries(self) -> tuple[SessionHistorySummary, ...]:
        return tuple(session for session in self.session_summaries() if session.policy == "exam")

    def exam_summary(self) -> ExamHistorySummary:
        sessions = self.exam_summaries()
        statuses = [session.status.lower() for session in sessions]
        return ExamHistorySummary(
            sessions=sessions,
            passed_count=sum(status in {"passed", "completed"} for status in statuses),
            failed_count=statuses.count("failed"),
            timed_out_count=sum(status in {"timed_out", "timeout"} for status in statuses),
            abandoned_count=statuses.count("abandoned"),
        )

    def training_volume(self, days: int = 14) -> TrainingVolumeSummary:
        rows = self._progress_repository.list_activity_attempts(policy="training")
        today = date.today()
        start = today - timedelta(days=max(days - 1, 0))
        counts = [0] * max(days, 0)
        for row in rows:
            submitted_at = row.get("submitted_at")
            if not submitted_at:
                continue
            try:
                submitted_date = datetime.fromisoformat(str(submitted_at)).date()
            except ValueError:
                continue
            offset = (submitted_date - start).days
            if 0 <= offset < len(counts):
                counts[offset] += 1
        return TrainingVolumeSummary(total_attempts=len(rows), daily_counts=tuple(counts))

    def recent_sessions(self, limit: int = 5) -> tuple[RecentSessionSummary, ...]:
        recent: list[RecentSessionSummary] = []
        for session in self.exam_summaries():
            result = session.status or "-"
            recent.append(
                RecentSessionSummary(
                    kind="EXAM",
                    pack_id=session.pack_id,
                    timestamp=session.finished_at,
                    result=result,
                    activities_count=session.activities_count,
                )
            )

        training_rows = self._progress_repository.list_activity_attempts(policy="training")
        by_pack: dict[str, list[dict]] = {}
        for row in training_rows:
            by_pack.setdefault(str(row.get("pack_id") or ""), []).append(row)
        for pack_id, rows in by_pack.items():
            latest = max((str(row.get("submitted_at")) for row in rows if row.get("submitted_at")), default=None)
            completed = sum(1 for row in rows if row.get("passed") is True or row.get("passed") == 1)
            recent.append(
                RecentSessionSummary(
                    kind="TRAIN",
                    pack_id=pack_id,
                    timestamp=latest,
                    result="completed" if completed else "attempted",
                    activities_count=len({str(row.get("activity_id") or row.get("exercise_id") or "") for row in rows}),
                    attempts_count=len(rows),
                    completed_count=completed,
                )
            )
        recent.sort(key=lambda item: item.timestamp or "", reverse=True)
        return tuple(recent[: max(limit, 0)])

    def training_summaries(self) -> tuple[SessionHistorySummary, ...]:
        rows = getattr(self._progress_repository, "list_training_sessions", lambda: [])()
        return tuple(
            SessionHistorySummary(
                session_id=str(row["id"]),
                policy="training",
                pack_id=str(row.get("rank") or row.get("pack_id") or ""),
                status=str(row.get("status") or ""),
                finished_at=None if row.get("finished_at") is None else str(row["finished_at"]),
                duration_seconds=None,
                score=None,
                activities_count=0,
                activities=(),
            )
            for row in rows
        )

    def exercise_rows(self, packs, list_exercises) -> list[dict[str, object]]:
        progress = self._progress_repository.progress_by_key()
        latest = self._progress_repository.latest_attempts()
        modes = self._progress_repository.modes_by_key()
        rows: list[dict[str, object]] = []
        shown: set[tuple[str, str]] = set()

        def row(pack_name: str, level: str, name: str, key: tuple[str, str]) -> dict[str, object]:
            entry = progress.get(key)
            status = ActivityProgress.NOT_STARTED
            if entry is not None:
                status = ActivityProgress.COMPLETED if entry.best_passed else ActivityProgress.ATTEMPTED
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

    def _activity_summary(self, pack_id: str, ref, include_attempts: bool = False) -> ActivityHistorySummary:
        key = (pack_id, ref.definition.id)
        progress = self._progress_repository.progress_by_key().get(key)
        latest = self._progress_repository.latest_attempts().get(key, {})
        status = ActivityProgress.NOT_STARTED
        if progress is not None:
            status = ActivityProgress.COMPLETED if progress.best_passed else ActivityProgress.ATTEMPTED
        attempts = self._attempt_summaries(pack_id, ref.definition.id, ref.definition.name) if include_attempts else ()
        return ActivityHistorySummary(
            pack_id=pack_id,
            activity_id=ref.definition.id,
            title=ref.definition.name,
            level=ref.level_id,
            status=status,
            attempts_count=0 if progress is None else progress.attempts_count,
            latest_result=self._format_latest_result(latest),
            latest_at=None if progress is None else progress.last_attempt_at,
            attempts=attempts,
        )

    def _attempt_summaries(self, pack_id: str, activity_id: str, title: str) -> tuple[AttemptSummary, ...]:
        rows = self._progress_repository.list_activity_attempts(pack_id=pack_id, activity_id=activity_id)
        summaries: list[AttemptSummary] = []
        total = len(rows)
        for index, row in enumerate(rows):
            passed = row.get("passed")
            result = "-" if passed is None else ("PASS" if bool(passed) else "FAIL")
            summaries.append(
                AttemptSummary(
                    attempt_id=str(row["id"]),
                    number=total - index,
                    activity_id=activity_id,
                    activity_title=title,
                    pack_id=pack_id,
                    policy=str(row.get("policy") or row.get("mode") or ""),
                    status=str(row.get("status") or ""),
                    result=result,
                    submitted_at=None if row.get("submitted_at") is None else str(row["submitted_at"]),
                    session_id=None if row.get("session_id") is None else str(row["session_id"]),
                    score=None if row.get("score") is None else float(row["score"]),
                    trace_available=False,
                    failure_summary="" if result != "FAIL" else str(row.get("status") or "FAIL"),
                )
            )
        return tuple(summaries)

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
