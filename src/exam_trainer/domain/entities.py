from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from exam_trainer.domain.value_objects import AttemptStatus, Grade, TrainingMode


@dataclass(frozen=True)
class Exercise:
    id: str
    title: str
    rank: str | None = None
    pack_id: str | None = None


@dataclass
class Attempt:
    exercise_id: str
    id: UUID = field(default_factory=uuid4)
    status: AttemptStatus = AttemptStatus.CREATED
    grade: Grade | None = None
    submitted_at: datetime | None = None

    def mark_submitted(self, submitted_at: datetime) -> None:
        self.status = AttemptStatus.SUBMITTED
        self.submitted_at = submitted_at

    def mark_graded(self, grade: Grade) -> None:
        self.status = AttemptStatus.GRADED
        self.grade = grade


@dataclass
class TrainingSession:
    mode: TrainingMode
    id: UUID = field(default_factory=uuid4)
    attempts: list[Attempt] = field(default_factory=list)

    def add_attempt(self, attempt: Attempt) -> None:
        self.attempts.append(attempt)


@dataclass
class ExamSession:
    id: UUID = field(default_factory=uuid4)
    attempts: list[Attempt] = field(default_factory=list)
    finished_at: datetime | None = None

    @property
    def is_finished(self) -> bool:
        return self.finished_at is not None

    def finish(self, finished_at: datetime) -> None:
        self.finished_at = finished_at
