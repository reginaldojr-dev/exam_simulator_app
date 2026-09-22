from __future__ import annotations

from uuid import UUID

from exam_trainer.domain.entities import ExamSession


class ResumeExam:
    def execute(self, exam_session_id: UUID) -> ExamSession:
        raise NotImplementedError("Exam resume is not implemented yet.")
