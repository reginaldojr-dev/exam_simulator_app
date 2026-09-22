from __future__ import annotations

from datetime import datetime

from exam_trainer.domain.entities import ExamSession


class FinishExam:
    def execute(self, exam_session: ExamSession) -> ExamSession:
        exam_session.finish(datetime.now())
        return exam_session
