from __future__ import annotations

from rankeddojo.domain.entities import ExamSession


class StartExam:
    def execute(self) -> ExamSession:
        raise NotImplementedError("Exam mode is not implemented yet.")
