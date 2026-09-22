from __future__ import annotations

from datetime import datetime
import unittest

from exam_trainer.domain.entities import Attempt, ExamSession
from exam_trainer.domain.services import ProgressionService
from exam_trainer.domain.value_objects import Grade


class DomainFoundationTest(unittest.TestCase):
    def test_grade_rejects_score_outside_percentage_range(self) -> None:
        with self.assertRaises(ValueError):
            Grade(passed=False, score=101)

    def test_attempt_can_be_marked_as_graded(self) -> None:
        attempt = Attempt(exercise_id="exercise-1")
        grade = Grade(passed=True, score=100)

        attempt.mark_graded(grade)

        self.assertEqual(attempt.grade, grade)

    def test_exam_session_can_be_finished(self) -> None:
        exam_session = ExamSession()
        finished_at = datetime(2026, 9, 17, 12, 0, 0)

        exam_session.finish(finished_at)

        self.assertTrue(exam_session.is_finished)
        self.assertEqual(exam_session.finished_at, finished_at)

    def test_progression_service_records_only_graded_attempts(self) -> None:
        service = ProgressionService()
        ungraded_attempt = Attempt(exercise_id="exercise-1")
        graded_attempt = Attempt(exercise_id="exercise-2")
        graded_attempt.mark_graded(Grade(passed=True))

        self.assertFalse(service.should_record_attempt(ungraded_attempt))
        self.assertTrue(service.should_record_attempt(graded_attempt))
