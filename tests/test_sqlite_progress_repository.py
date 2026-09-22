from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from exam_trainer.adapters.persistence.sqlite_progress_repository import (
    SQLiteProgressRepository,
)
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.domain.entities import Attempt
from exam_trainer.domain.value_objects import Grade


class SQLiteProgressRepositoryTest(unittest.TestCase):
    def test_saves_and_loads_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = SQLiteProgressRepository(
                SQLiteStore(Path(temp_dir) / "trainer.sqlite3")
            )
            attempt = Attempt(exercise_id="echo_args")
            attempt.mark_submitted(datetime(2026, 9, 21, 12, 0, 0))
            attempt.mark_graded(Grade(passed=True, score=100))

            repository.save_attempt(attempt)

            attempts = repository.list_attempts()
            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0].exercise_id, "echo_args")
            self.assertEqual(attempts[0].grade, Grade(passed=True, score=100))

    def test_initializes_expected_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteStore(Path(temp_dir) / "trainer.sqlite3")

            store.initialize()

            with store.session() as connection:
                table_names = {
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }

            self.assertIn("settings", table_names)
            self.assertIn("exercises", table_names)
            self.assertIn("attempts", table_names)
            self.assertIn("progress", table_names)
            self.assertIn("training_sessions", table_names)
            self.assertIn("exam_sessions", table_names)
