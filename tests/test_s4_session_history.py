from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from exam_trainer.adapters.editor.subprocess_editor import SubprocessEditor, SubprocessEditorFactory
from exam_trainer.adapters.pack.local_pack_catalog import LocalPackCatalog
from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter
from exam_trainer.adapters.persistence.sqlite_progress_repository import SQLiteProgressRepository
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.adapters.runtime.c_runtime import CRuntime
from exam_trainer.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from exam_trainer.adapters.workspace.local_workspace import LocalWorkspace
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry
from exam_trainer.application.history_service import HistoryQuery
from exam_trainer.application.use_cases.mvp_coordinator import MVPTrainerCoordinator, TrainingOptions
from exam_trainer.domain.grading import GradingPolicy, GradingResult, TraceData
from exam_trainer.domain.session_policy import ExamPolicy, SessionPolicyRegistry, TrainingPolicy
from exam_trainer.ports.compiler_port import CompilationResult
from exam_trainer.ports.grader_port import GradingRequest


class StaticGrader:
    def __init__(self, passed: bool = True) -> None:
        self.passed = passed

    def grade(self, request: GradingRequest) -> GradingResult:
        return GradingResult(passed=self.passed, trace_data=TraceData(("trace",)))


class AvailableCompiler:
    def is_available(self) -> bool:
        return True

    def find_compiler(self) -> str:
        return "gcc"

    def redetect(self) -> str:
        return "gcc"

    def current_compiler(self) -> str:
        return "gcc"

    def cached_compiler(self) -> str | None:
        return "gcc"

    def validate_compiler(self, compiler_path) -> bool:
        return True

    def set_manual_compiler(self, compiler_path) -> None:
        pass

    def compile(self, source_files: list[Path], output_path: Path) -> CompilationResult:
        return CompilationResult(success=True, executable_path=output_path)


@dataclass(frozen=True)
class FakeSessionPolicy:
    id: str = "fake"
    can_switch_activity: bool = True
    advances_on_pass: bool = False
    stays_on_fail: bool = False
    has_deadline: bool = False
    workspace_scope_kind: str = "training"

    def grading_policy(self) -> GradingPolicy:
        return GradingPolicy.training()


class SessionPolicyHistoryTest(unittest.TestCase):
    def _coordinator(self, root: Path, grader: StaticGrader | None = None) -> MVPTrainerCoordinator:
        workspace = root / "workspace"
        workspace.mkdir()
        compiler = AvailableCompiler()
        return MVPTrainerCoordinator(
            pack_catalog=LocalPackCatalog(root / "managed", bundled_packs_dir=Path(__file__).parent.parent / "examples" / "packs"),
            progress_repository=SQLiteProgressRepository(SQLiteStore(root / "trainer.sqlite3")),
            workspace=LocalExerciseWorkspace(),
            grader=grader or StaticGrader(),
            editor=SubprocessEditor("unused"),
            pack_importer=LocalPackImporter(root / "managed"),
            runtimes=RuntimeRegistry([CRuntime(compiler, manager=compiler)]),
            workspace_root=workspace,
            editor_factory=SubprocessEditorFactory(),
            workspace_port=LocalWorkspace(),
        )

    def test_training_and_exam_policy_flags_document_current_behavior(self) -> None:
        training = TrainingPolicy()
        exam = ExamPolicy()

        self.assertTrue(training.can_switch_activity)
        self.assertFalse(training.has_deadline)
        self.assertFalse(exam.can_switch_activity)
        self.assertTrue(exam.stays_on_fail)
        self.assertTrue(exam.advances_on_pass)
        self.assertTrue(exam.has_deadline)

    def test_fake_session_policy_enters_through_registry_extension_point(self) -> None:
        registry = SessionPolicyRegistry((TrainingPolicy(), ExamPolicy()))
        registry.register(FakeSessionPolicy())

        self.assertIn("fake", registry.ids())
        self.assertIsInstance(registry.get("fake"), FakeSessionPolicy)

    def test_coordinator_exposes_session_policy_extension_point(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = self._coordinator(Path(temp_dir))

            coordinator.register_session_policy(FakeSessionPolicy())

            self.assertIn("fake", coordinator.session_policy_ids())

    def test_history_query_filters_by_pack_activity_and_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            coordinator = self._coordinator(root)
            ref = next(
                ref
                for ref in coordinator._pack_catalog.list_exercises("sample_rank")
                if ref.definition.id == "steady_echo"
            )
            active = coordinator.prepare_exercise(ref, overwrite=True)
            coordinator.submit_training(active)

            state = coordinator.start_exam("sample_rank", duration_seconds=60)
            exam_active = coordinator.prepare_exam_exercise(coordinator.exam_ref(state), state, overwrite=True)
            coordinator.submit_exam(state, exam_active)

            by_pack = coordinator.history_timeline(HistoryQuery(pack_id="sample_rank"))
            by_activity = coordinator.history_timeline(HistoryQuery(activity_id="steady_echo"))
            by_session = coordinator.history_timeline(HistoryQuery(session_id=state.id))

            self.assertGreaterEqual(len(by_pack), 2)
            self.assertTrue(all(entry.identity.pack_id == "sample_rank" for entry in by_pack))
            self.assertTrue(any(entry.identity.activity_id == "steady_echo" for entry in by_activity))
            self.assertTrue(by_session)
            self.assertTrue(all(entry.session_id == state.id for entry in by_session))

    def test_sqlite_schema_has_neutral_activity_and_policy_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            coordinator = self._coordinator(root)
            ref = next(iter(coordinator._pack_catalog.list_exercises("sample_rank")))
            active = coordinator.prepare_exercise(ref, overwrite=True)
            coordinator.submit_training(active)

            with coordinator._progress_repository._store.session() as connection:
                attempt_columns = {row[1] for row in connection.execute("PRAGMA table_info(attempts)")}
                progress_columns = {row[1] for row in connection.execute("PRAGMA table_info(progress)")}
                row = connection.execute("SELECT activity_id, activity_kind, policy FROM attempts").fetchone()

            self.assertTrue({"activity_id", "activity_kind", "policy"}.issubset(attempt_columns))
            self.assertTrue({"activity_id", "activity_kind", "policy"}.issubset(progress_columns))
            self.assertEqual(row["activity_kind"], "exercise")
            self.assertEqual(row["policy"], "training")


if __name__ == "__main__":
    unittest.main()
