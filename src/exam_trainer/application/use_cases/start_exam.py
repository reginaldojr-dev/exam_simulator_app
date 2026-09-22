from __future__ import annotations

from exam_trainer.domain.entities import ExamSession


class StartExam:
    def execute(self) -> ExamSession:
        raise NotImplementedError("Exam mode is not implemented yet.")
