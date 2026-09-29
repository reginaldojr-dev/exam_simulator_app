from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path, PurePath

from exam_trainer.adapters.editor.subprocess_editor import SubprocessEditor, SubprocessEditorFactory
from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter
from exam_trainer.adapters.persistence.sqlite_progress_repository import SQLiteProgressRepository
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from exam_trainer.application.engine.activity_preflight import (
    ActivityContentPreflight,
    ActivityPreflightStatus,
)
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry
from exam_trainer.application.mvp_models import ExerciseRef
from exam_trainer.application.use_cases.mvp_coordinator import MVPTrainerCoordinator
from exam_trainer.domain.exercise_definition import (
    ExecutionDefinition,
    ExerciseDefinition,
    LimitsDefinition,
    ReferenceDefinition,
    SubmissionDefinition,
    TestCaseDefinition,
    TestDefinition,
)
from exam_trainer.domain.grading import GradingOutcome, GradingResult, TraceData
from exam_trainer.domain.pack_definition import PackDefinition, PackLevelDefinition
from exam_trainer.domain.test_contract import ArgumentContract, ArgumentKind, TestContract
from exam_trainer.ports.compiler_port import CompilationResult
from exam_trainer.ports.grader_port import GradingRequest
from exam_trainer.ports.runtime_port import PreparedProgram, ProcessOutcome, ProgramSpec


class ScriptedRuntime:
    def __init__(self, language: str = "toy", display_name: str | None = None, available: bool = True) -> None:
        self.language = language
        self.display_name = display_name or language.title()
        self.available = available
        self.prepared: list[ProgramSpec] = []

    def is_ready(self) -> bool:
        return self.available

    def check_available(self) -> bool:
        return self.available

    def current_tool(self) -> str | None:
        return "toy" if self.available else None

    def redetect(self) -> str | None:
        return self.current_tool()

    def configure_manual(self, path: Path) -> str:
        return str(path)

    def prepare(self, spec: ProgramSpec, build_dir: Path, name: str) -> PreparedProgram:
        self.prepared.append(spec)
        text = spec.main_source.read_text(encoding="utf-8")
        build = CompilationResult(
            success=text.strip() != "broken",
            output="broken reference" if text.strip() == "broken" else "ok",
            command=("toy", name),
        )
        return PreparedProgram(success=build.success, build=build, argv=(text.strip(),))

    def run(
        self,
        program: PreparedProgram,
        args: tuple[str, ...],
        stdin: str,
        timeout_seconds: int,
    ) -> ProcessOutcome:
        return ProcessOutcome(stdout=" ".join(args), exit_code=0)


class CountingGrader:
    def __init__(self) -> None:
        self.calls = 0

    def grade(self, request: GradingRequest) -> GradingResult:
        self.calls += 1
        return GradingResult(outcome=GradingOutcome.PASSED, trace_data=TraceData(("graded",)))


class FirstChoiceRandom:
    def choice(self, values):
        return values[0]


class StaticPackCatalog:
    def __init__(self, refs: list[ExerciseRef]) -> None:
        self.refs = refs
        self.pack = refs[0].pack

    def list_packs(self) -> list[PackDefinition]:
        return [self.pack]

    def list_exercises(self, pack_id: str) -> list[ExerciseRef]:
        return self.refs if pack_id == self.pack.id else []


def definition(
    exercise_id: str = "activity",
    *,
    reference: str | None = None,
    execution: ExecutionDefinition | None = None,
    support_files: tuple[PurePath, ...] = (),
    **overrides: object,
) -> ExerciseDefinition:
    values: dict[str, object] = {
        "id": exercise_id,
        "name": exercise_id,
        "subject": PurePath("subject.md"),
        "submission": SubmissionDefinition(f"{exercise_id}.toy"),
        "execution": execution or ExecutionDefinition(type="program_output"),
        "tests": TestDefinition(
            generator="fixed_cases",
            expectation="literal" if reference is None else "reference_output",
            cases=(TestCaseDefinition(args=("a",), expected="a"),),
        ),
        "limits": LimitsDefinition(timeout_seconds=1),
        "reference": None if reference is None else ReferenceDefinition(PurePath(reference)),
        "support_files": support_files,
        "language": "toy",
        "programming_language": "toy",
    }
    values.update(overrides)
    return ExerciseDefinition(**values)  # type: ignore[arg-type]


def write_activity(root: Path, exercise_id: str, *, reference_text: str | None = None) -> Path:
    path = root / exercise_id
    path.mkdir(parents=True)
    (path / "subject.md").write_text("Subject", encoding="utf-8")
    if reference_text is not None:
        (path / "reference.toy").write_text(reference_text, encoding="utf-8")
    return path


def make_ref(pack: PackDefinition, level_id: str, definition_: ExerciseDefinition, content_path: Path) -> ExerciseRef:
    return ExerciseRef(pack=pack, level_id=level_id, definition=definition_, content_path=content_path)


class ActivityContentPreflightTest(unittest.TestCase):
    def test_literal_activity_without_reference_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            activity = write_activity(root, "ready")
            runtime = ScriptedRuntime()

            result = ActivityContentPreflight(RuntimeRegistry([runtime])).check(
                definition("ready"),
                activity,
            )

            self.assertIs(result.status, ActivityPreflightStatus.READY)
            self.assertEqual(runtime.prepared, [])

    def test_runtime_unavailable_is_not_content_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            activity = write_activity(Path(temp_dir), "runtime")

            result = ActivityContentPreflight(RuntimeRegistry([ScriptedRuntime(display_name="Toy", available=False)])).check(
                definition("runtime"),
                activity,
            )

            self.assertIs(result.status, ActivityPreflightStatus.RUNTIME_UNAVAILABLE)
            self.assertEqual(result.issue_code, "runtime_unavailable")
            self.assertFalse(result.ok)
            self.assertIn("Toy", result.message)

    def test_missing_harness_is_content_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            activity = write_activity(Path(temp_dir), "bad_plan")

            result = ActivityContentPreflight(RuntimeRegistry([ScriptedRuntime()])).check(
                definition(
                    "bad_plan",
                    execution=ExecutionDefinition(type="function_call", fixture=PurePath("missing.c")),
                ),
                activity,
            )

            self.assertIs(result.status, ActivityPreflightStatus.CONTENT_INVALID)
            self.assertIn("harness", result.technical_detail)

    def test_reference_build_failure_is_content_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            activity = write_activity(Path(temp_dir), "bad_reference", reference_text="broken")

            result = ActivityContentPreflight(RuntimeRegistry([ScriptedRuntime()])).check(
                definition("bad_reference", reference="reference.toy"),
                activity,
            )

            self.assertIs(result.status, ActivityPreflightStatus.CONTENT_INVALID)
            self.assertEqual(result.issue_code, "content_invalid")
            self.assertIn("broken reference", result.technical_detail)

    def test_missing_reference_file_is_content_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            activity = write_activity(Path(temp_dir), "missing_reference")

            result = ActivityContentPreflight(RuntimeRegistry([ScriptedRuntime()])).check(
                definition("missing_reference", reference="reference.toy"),
                activity,
            )

            self.assertIs(result.status, ActivityPreflightStatus.CONTENT_INVALID)
            self.assertIn("reference", result.technical_detail)

    def test_generator_contract_incompatibility_is_content_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            activity = write_activity(Path(temp_dir), "bad_generator")

            result = ActivityContentPreflight(RuntimeRegistry([ScriptedRuntime()])).check(
                definition(
                    "bad_generator",
                    tests=TestDefinition(
                        generator="random_integer",
                        expectation="literal",
                        contract=TestContract(
                            args=(
                                ArgumentContract(ArgumentKind.INTEGER),
                                ArgumentContract(ArgumentKind.INTEGER),
                            )
                        ),
                    ),
                ),
                activity,
            )

            self.assertIs(result.status, ActivityPreflightStatus.CONTENT_INVALID)
            self.assertIn("random_integer", result.technical_detail)

    def test_reference_preflight_preserves_support_include_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            activity = write_activity(Path(temp_dir), "with_header", reference_text="ok")
            include = activity / "include"
            include.mkdir()
            (include / "lib.h").write_text("/* header */", encoding="utf-8")
            runtime = ScriptedRuntime(language="c", display_name="C")

            result = ActivityContentPreflight(RuntimeRegistry([runtime])).check(
                definition(
                    "with_header",
                    reference="reference.toy",
                    support_files=(PurePath("include/lib.h"),),
                    language="c",
                    programming_language="c",
                ),
                activity,
            )

            self.assertTrue(result.ok, result)
            self.assertEqual(runtime.prepared[-1].include_dirs, (include,))

    def test_cpp_python_and_java_delegate_to_registered_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtimes = [ScriptedRuntime(language=language) for language in ("cpp", "python", "java")]
            preflight = ActivityContentPreflight(RuntimeRegistry(runtimes))

            for language in ("cpp", "python", "java"):
                with self.subTest(language=language):
                    activity = write_activity(root, f"{language}_activity")
                    result = preflight.check(
                        definition(
                            f"{language}_activity",
                            language=language,
                            programming_language=language,
                        ),
                        activity,
                    )
                    self.assertIs(result.status, ActivityPreflightStatus.READY)


class ActivityPreflightCoordinatorTest(unittest.TestCase):
    def _coordinator(self, root: Path, refs: list[ExerciseRef], grader: CountingGrader) -> MVPTrainerCoordinator:
        return MVPTrainerCoordinator(
            pack_catalog=StaticPackCatalog(refs),
            progress_repository=SQLiteProgressRepository(SQLiteStore(root / "trainer.sqlite3")),
            workspace=LocalExerciseWorkspace(),
            grader=grader,
            editor=SubprocessEditor("definitely-not-used"),
            pack_importer=LocalPackImporter(root / "managed"),
            runtimes=RuntimeRegistry([ScriptedRuntime(display_name="Toy")]),
            workspace_root=root / "workspace",
            editor_factory=SubprocessEditorFactory(),
            clock=lambda: datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            rng=FirstChoiceRandom(),
        )

    def test_training_content_invalid_blocks_grading_without_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack = PackDefinition(
                id="pack",
                name="Pack",
                version="1",
                levels=(PackLevelDefinition("level0", PurePath("level0")),),
                language="toy",
            )
            ref = make_ref(
                pack,
                "level0",
                definition("bad", reference="reference.toy"),
                write_activity(root, "bad", reference_text="broken"),
            )
            grader = CountingGrader()
            coordinator = self._coordinator(root, [ref], grader)
            active = coordinator.prepare_exercise(ref)

            outcome = coordinator.submit_training(active)

            self.assertEqual(grader.calls, 0)
            self.assertIs(outcome.result.outcome, GradingOutcome.CONTENT_ERROR)
            self.assertEqual(outcome.attempts_count, 0)
            self.assertEqual(coordinator.list_progress(), [])

    def test_exam_skips_known_invalid_activity_when_valid_alternative_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack = PackDefinition(
                id="pack",
                name="Pack",
                version="1",
                levels=(PackLevelDefinition("level0", PurePath("level0")),),
                language="toy",
            )
            invalid = make_ref(
                pack,
                "level0",
                definition("bad", reference="reference.toy"),
                write_activity(root, "bad", reference_text="broken"),
            )
            valid = make_ref(pack, "level0", definition("good"), write_activity(root, "good"))

            state = self._coordinator(root, [invalid, valid], CountingGrader()).start_exam("pack", 60)

            self.assertEqual(state.exercise_id, "good")

    def test_exam_fails_controlled_when_level_has_no_valid_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack = PackDefinition(
                id="pack",
                name="Pack",
                version="1",
                levels=(PackLevelDefinition("level0", PurePath("level0")),),
                language="toy",
            )
            ref = make_ref(
                pack,
                "level0",
                definition("bad", reference="reference.toy"),
                write_activity(root, "bad", reference_text="broken"),
            )
            coordinator = self._coordinator(root, [ref], CountingGrader())

            with self.assertRaisesRegex(ValueError, "No valid exercises"):
                coordinator.start_exam("pack", 60)
            self.assertIsNone(coordinator.load_active_exam())

    def test_exam_content_invalid_at_submit_does_not_record_user_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack = PackDefinition(
                id="pack",
                name="Pack",
                version="1",
                levels=(PackLevelDefinition("level0", PurePath("level0")),),
                language="toy",
            )
            activity_path = write_activity(root, "activity", reference_text="ok")
            ref = make_ref(pack, "level0", definition("activity", reference="reference.toy"), activity_path)
            coordinator = self._coordinator(root, [ref], CountingGrader())
            state = coordinator.start_exam("pack", 60)
            active = coordinator.prepare_exam_exercise(ref, state)
            (activity_path / "reference.toy").write_text("broken", encoding="utf-8")

            outcome, next_state = coordinator.submit_exam(state, active)

            self.assertIs(outcome.result.outcome, GradingOutcome.CONTENT_ERROR)
            self.assertEqual(outcome.attempts_count, 0)
            self.assertIsNotNone(next_state)
            self.assertEqual(next_state.exercise_id, state.exercise_id)
            repo = SQLiteProgressRepository(SQLiteStore(root / "trainer.sqlite3"))
            self.assertEqual(repo.list_exam_level_results(state.id), [])


if __name__ == "__main__":
    unittest.main()
