from __future__ import annotations

import json
import random
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from exam_trainer.adapters.compiler.system_c_compiler import SystemCCompiler
from exam_trainer.adapters.editor.subprocess_editor import SubprocessEditor
from exam_trainer.adapters.pack.local_pack_catalog import LocalPackCatalog
from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter
from exam_trainer.adapters.persistence.sqlite_progress_repository import SQLiteProgressRepository
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from exam_trainer.adapters.workspace.local_workspace import LocalWorkspace
from exam_trainer.application.use_cases.mvp_coordinator import MVPTrainerCoordinator
from exam_trainer.domain.grading import GradingResult, TraceData
from exam_trainer.ports.grader_port import GradingRequest


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class SwitchGrader:
    def __init__(self) -> None:
        self.passed = True

    def grade(self, request: GradingRequest) -> GradingResult:
        return GradingResult(passed=self.passed, seed=request.seed, trace_data=TraceData(("x",)))


def build_pack(root: Path, pack_id: str, levels: int, per_level: int = 1, duration_minutes: int | None = None) -> None:
    level_entries = []
    for level in range(levels):
        level_id = f"level{level}"
        level_entries.append({"id": level_id, "path": level_id})
        for index in range(per_level):
            exercise_id = f"ex_{level}_{index}"
            folder = root / level_id / exercise_id
            folder.mkdir(parents=True)
            (folder / "subject.md").write_text(exercise_id, encoding="utf-8")
            (folder / "exercise.json").write_text(
                json.dumps(
                    {
                        "id": exercise_id,
                        "name": exercise_id,
                        "subject": "subject.md",
                        "submission": {"filename": f"{exercise_id}.c"},
                        "execution": {"type": "program_output"},
                        "tests": {"generator": "random_arguments", "expectation": "echo_arguments"},
                    }
                ),
                encoding="utf-8",
            )
    pack: dict[str, object] = {"id": pack_id, "name": pack_id, "version": "1.0.0", "levels": level_entries}
    if duration_minutes is not None:
        pack["exam"] = {"duration_minutes": duration_minutes}
    (root / "pack.json").write_text(json.dumps(pack), encoding="utf-8")


class ExamRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.bundled = self.root / "bundled"
        build_pack(self.bundled / "eleven", "eleven", levels=11)
        build_pack(self.bundled / "wide", "wide", levels=2, per_level=4, duration_minutes=90)
        self.clock = FakeClock()
        self.grader = SwitchGrader()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def coordinator(self, rng: random.Random | None = None) -> MVPTrainerCoordinator:
        return MVPTrainerCoordinator(
            pack_catalog=LocalPackCatalog(self.root / "managed", bundled_packs_dir=self.bundled),
            progress_repository=SQLiteProgressRepository(SQLiteStore(self.root / "trainer.sqlite3")),
            workspace=LocalExerciseWorkspace(),
            grader=self.grader,
            editor=SubprocessEditor("definitely-not-used"),
            pack_importer=LocalPackImporter(self.root / "managed"),
            compiler=SystemCCompiler(candidates=("definitely-not-a-c-compiler",)),
            workspace_root=self.root / "workspace",
            workspace_port=LocalWorkspace(),
            clock=self.clock,
            rng=rng,
        )

    def _pass_current(self, coordinator: MVPTrainerCoordinator, state):
        active = coordinator.prepare_exam_exercise(coordinator.exam_ref(state), state, overwrite=True)
        return coordinator.submit_exam(state, active)[1]

    def test_levels_follow_pack_order_not_string_order(self) -> None:
        coordinator = self.coordinator()
        state = coordinator.start_exam("eleven")
        visited = []
        while state is not None:
            visited.append(coordinator.exam_ref(state).level_id)
            state = self._pass_current(coordinator, state)
        self.assertEqual(visited, [f"level{index}" for index in range(11)])

    def test_first_exercise_is_drawn_within_first_level(self) -> None:
        firsts = {
            self.coordinator(rng=random.Random(seed)).start_exam("wide").exercise_id
            for seed in range(30)
        }
        self.assertGreater(len(firsts), 1)
        self.assertTrue(all(exercise.startswith("ex_0_") for exercise in firsts))

    def test_fail_keeps_same_exercise(self) -> None:
        coordinator = self.coordinator()
        state = coordinator.start_exam("wide")
        self.grader.passed = False
        active = coordinator.prepare_exam_exercise(coordinator.exam_ref(state), state, overwrite=True)
        _, next_state = coordinator.submit_exam(state, active)
        self.assertEqual(next_state.exercise_id, state.exercise_id)
        self.assertEqual(next_state.level_index, 0)

    def test_duration_comes_from_pack_with_legacy_fallback(self) -> None:
        coordinator = self.coordinator()
        self.assertEqual(coordinator.start_exam("wide").duration_seconds, 90 * 60)
        self.assertEqual(coordinator.exam_duration_seconds("eleven"), 4 * 60 * 60)

    def test_closing_the_app_does_not_pause_the_clock(self) -> None:
        state = self.coordinator().start_exam("wide")
        self.clock.advance(20 * 60)

        reopened = self.coordinator().load_active_exam()

        self.assertEqual(reopened.id, state.id)
        self.assertEqual(reopened.remaining_seconds, 70 * 60)

    def test_deadline_passed_while_closed_finishes_as_timeout_with_partial_score(self) -> None:
        coordinator = self.coordinator()
        state = coordinator.start_exam("wide")
        state = self._pass_current(coordinator, state)
        self.clock.advance(91 * 60)

        reopened = self.coordinator()
        self.assertIsNone(reopened.load_active_exam())
        expired = reopened.pop_expired_exam()
        self.assertIsNotNone(expired)
        self.assertEqual(expired.id, state.id)
        history = reopened.list_exam_history()[0]
        self.assertEqual(history["status"], "timeout")
        self.assertEqual(history["final_score"], 50)
        self.assertIsNone(reopened.pop_expired_exam())

    def test_tick_does_not_write_to_database(self) -> None:
        coordinator = self.coordinator()
        state = coordinator.start_exam("wide")
        writes = []
        original = coordinator._progress_repository.save_active_exam
        coordinator._progress_repository.save_active_exam = lambda row: (writes.append(row), original(row))
        for _ in range(30):
            self.clock.advance(1)
            state = coordinator.tick_exam(state)
        self.assertEqual(writes, [])
        self.assertEqual(state.remaining_seconds, 90 * 60 - 30)

    def test_workspace_is_kept_until_the_exam_finishes(self) -> None:
        coordinator = self.coordinator()
        state = coordinator.start_exam("wide")
        coordinator.prepare_exam_exercise(coordinator.exam_ref(state), state, overwrite=True)
        session_dir = self.root / "workspace" / "exam" / state.id
        self.grader.passed = False
        active = coordinator.prepare_exam_exercise(coordinator.exam_ref(state), state)
        coordinator.submit_exam(state, active)
        self.assertTrue(session_dir.is_dir())
        coordinator.finish_exam(state, "abandoned")
        self.assertFalse(session_dir.exists())


class MigrationTest(unittest.TestCase):
    def test_legacy_active_exam_gets_deadline_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "trainer.sqlite3"
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE exam_sessions (
                    id TEXT PRIMARY KEY, rank TEXT, current_level INTEGER,
                    current_exercise_id TEXT, score REAL, remaining_seconds INTEGER,
                    seed INTEGER, status TEXT, workspace_path TEXT,
                    started_at TEXT, finished_at TEXT
                );
                INSERT INTO exam_sessions VALUES ('s1', 'wide', 0, 'ex_0_0', 0, 600, 1, 'active', '/tmp/x', '2026-01-01T10:00:00', NULL);
                """
            )
            connection.commit()
            connection.close()

            store = SQLiteStore(database)
            store.initialize()

            self.assertGreaterEqual(store.schema_version, 1)
            check = sqlite3.connect(database)
            row = check.execute("SELECT deadline_at, duration_seconds FROM exam_sessions").fetchone()
            check.close()
            deadline = datetime.fromisoformat(row[0])
            remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
            self.assertTrue(590 <= remaining <= 600)
            backups = list(Path(temp_dir).glob("trainer.sqlite3.bak-v0-*"))
            self.assertEqual(len(backups), 1)

            SQLiteStore(database).initialize()
            self.assertEqual(len(list(Path(temp_dir).glob("trainer.sqlite3.bak-*"))), 1)


if __name__ == "__main__":
    unittest.main()
