from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from exam_trainer.adapters.compiler.system_c_compiler import SystemCCompiler
from exam_trainer.adapters.editor.subprocess_editor import SubprocessEditor
from exam_trainer.adapters.grader.generic_c_grader import GenericCGrader
from exam_trainer.adapters.pack.local_pack_catalog import LocalPackCatalog
from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter
from exam_trainer.adapters.persistence.sqlite_progress_repository import SQLiteProgressRepository
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from exam_trainer.adapters.workspace.local_workspace import LocalWorkspace
from exam_trainer.application.use_cases.mvp_coordinator import (
    MVPTrainerCoordinator,
    TrainingOptions,
)
from exam_trainer.domain.grading import GradingResult, TraceData
from exam_trainer.ports.grader_port import GradingRequest


class StaticGrader:
    def __init__(self, passed: bool) -> None:
        self.passed = passed

    def grade(self, request: GradingRequest) -> GradingResult:
        return GradingResult(
            passed=self.passed,
            seed=request.seed,
            trace_data=TraceData((f"Result: {self.passed}",)),
        )


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class InMemoryConfig:
    def __init__(self) -> None:
        self.workspace_path: Path | None = None
        self.editor_command = "code"

    def save_workspace_path(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path

    def load_editor_command(self) -> str:
        return self.editor_command

    def save_editor_command(self, editor_command: str) -> None:
        self.editor_command = editor_command


class MVPTrainerCoordinatorTest(unittest.TestCase):
    def _coordinator(
        self,
        temp_dir: str,
        passed: bool = True,
        config: InMemoryConfig | None = None,
        clock: "FakeClock | None" = None,
    ) -> MVPTrainerCoordinator:
        root = Path(temp_dir)
        return MVPTrainerCoordinator(
            pack_catalog=LocalPackCatalog(
                managed_packs_dir=root / "managed",
                bundled_packs_dir=Path(__file__).parent.parent / "examples" / "packs",
            ),
            progress_repository=SQLiteProgressRepository(
                SQLiteStore(root / "trainer.sqlite3")
            ),
            workspace=LocalExerciseWorkspace(),
            grader=StaticGrader(passed),
            editor=SubprocessEditor("definitely-not-used"),
            pack_importer=LocalPackImporter(root / "managed"),
            compiler=SystemCCompiler(candidates=("definitely-not-a-c-compiler",)),
            workspace_root=root / "workspace",
            config_repository=config,
            workspace_port=LocalWorkspace(),
            clock=clock,
        )

    def test_training_selection_prioritizes_uncompleted_exercises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = self._coordinator(temp_dir)
            options = TrainingOptions(
                pack_id="sample_rank",
                level_ids=("level0", "level1"),
                selection_mode="only_uncompleted",
                allow_repeated=False,
            )
            first = coordinator.choose_training_exercise(options)
            active = coordinator.prepare_exercise(first)
            coordinator.submit_training(active)

            second = coordinator.choose_training_exercise(options)

            self.assertNotEqual(first.definition.id, second.definition.id)

    def test_exam_fail_keeps_same_exercise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = self._coordinator(temp_dir, passed=False)
            state = coordinator.start_exam("sample_rank", duration_seconds=60)
            active = coordinator.prepare_exam_exercise(coordinator.exam_ref(state), state)

            _outcome, next_state = coordinator.submit_exam(state, active)

            self.assertIsNotNone(next_state)
            self.assertEqual(next_state.exercise_id, state.exercise_id)

    def test_exam_pass_advances_level(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = self._coordinator(temp_dir, passed=True)
            state = coordinator.start_exam("sample_rank", duration_seconds=60)
            active = coordinator.prepare_exam_exercise(coordinator.exam_ref(state), state)

            _outcome, next_state = coordinator.submit_exam(state, active)

            self.assertIsNotNone(next_state)
            self.assertEqual(next_state.level_index, 1)

    def test_exam_timeout_finishes_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = self._coordinator(temp_dir)
            clock = FakeClock()
            coordinator = self._coordinator(temp_dir, clock=clock)
            state = coordinator.start_exam("sample_rank", duration_seconds=1)
            clock.advance(1)

            updated = coordinator.tick_exam(state)

            self.assertIsNone(updated)
            self.assertIsNone(coordinator.load_active_exam())
            self.assertEqual(coordinator.list_exam_history()[0]["status"], "timeout")

    def test_exam_resume_loads_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = self._coordinator(temp_dir)
            state = coordinator.start_exam("sample_rank", duration_seconds=60)

            loaded = coordinator.load_active_exam()

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.id, state.id)

    def test_training_workspace_uses_training_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = self._coordinator(temp_dir)
            ref = coordinator.choose_training_exercise(
                TrainingOptions(pack_id="sample_rank", level_ids=("level0",))
            )

            active = coordinator.prepare_exercise(ref)

            self.assertIn("training", active.exercise_workspace_path.parts)
            self.assertNotIn("exam", active.exercise_workspace_path.parts)

    def test_exam_workspace_uses_session_directory_and_cleanup_preserves_training(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = self._coordinator(temp_dir)
            training_ref = coordinator.choose_training_exercise(
                TrainingOptions(pack_id="sample_rank", level_ids=("level0",))
            )
            training = coordinator.prepare_exercise(training_ref)
            state = coordinator.start_exam("sample_rank", duration_seconds=60)
            exam = coordinator.prepare_exam_exercise(coordinator.exam_ref(state), state)

            self.assertIn("exam", exam.exercise_workspace_path.parts)
            self.assertIn(state.id, exam.exercise_workspace_path.parts)

            coordinator.finish_exam(state, "abandoned", state.score)

            self.assertTrue(training.exercise_workspace_path.exists())
            self.assertFalse((coordinator.workspace_root / "exam" / state.id).exists())

    def test_import_pack_through_application_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = self._coordinator(temp_dir)
            sample_pack = Path(__file__).parent.parent / "examples" / "packs" / "sample_rank"

            pack = coordinator.import_pack(sample_pack)

            self.assertEqual(pack.id, "sample_rank")

    def test_settings_update_workspace_and_editor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = InMemoryConfig()
            coordinator = self._coordinator(temp_dir, config=config)
            new_workspace = Path(temp_dir) / "new-workspace"
            editor = Path(temp_dir) / "editor.exe"
            editor.write_text("", encoding="utf-8")

            coordinator.change_workspace(new_workspace)
            coordinator.save_editor_command(str(editor))

            self.assertTrue(new_workspace.is_dir())
            self.assertEqual(config.workspace_path, new_workspace)
            self.assertEqual(coordinator.editor_command(), str(editor))
