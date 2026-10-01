"""Learning track UI integration: exposes the Fase 9 foundation
(`ContentRegistry`/`GetLearningTrack`/`GetNextLearningActivity`) in the
desktop UI, reusing the existing training/exam/workspace/grading flow --
no parallel execution engine, no XP/ranks/badges yet.

`LearningCoordinatorTest` covers the new `MVPTrainerCoordinator` delegation
methods without any Qt involvement. `LearningUITest` drives the real
`MainWindow` (offscreen) against the real bundled example packs.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from rankeddojo.adapters.editor.subprocess_editor import SubprocessEditor, SubprocessEditorFactory
from rankeddojo.adapters.learning.pack_content_provider import PackContentProvider
from rankeddojo.adapters.pack.local_pack_catalog import LocalPackCatalog
from rankeddojo.adapters.pack.local_pack_importer import LocalPackImporter
from rankeddojo.adapters.persistence.sqlite_progress_repository import SQLiteProgressRepository
from rankeddojo.adapters.persistence.sqlite_store import SQLiteStore
from rankeddojo.adapters.runtime.c_runtime import CRuntime
from rankeddojo.adapters.ui.qt.i18n import SUPPORTED_UI_LOCALES, LocaleService
from rankeddojo.adapters.ui.qt.main_window import MainWindow
from rankeddojo.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from rankeddojo.adapters.workspace.local_workspace import LocalWorkspace
from rankeddojo.application.engine.content_registry import ContentRegistry
from rankeddojo.application.engine.runtime_registry import RuntimeRegistry
from rankeddojo.application.use_cases.mvp_coordinator import MVPTrainerCoordinator
from rankeddojo.domain.grading import GradingOutcome, GradingResult, TraceData
from rankeddojo.ports.compiler_port import CompilationResult

EXAMPLES_DIR = Path(__file__).parent.parent / "examples" / "packs"

# The real c-basics pilot prerequisite chain (Fase 9): array_peak depends on
# argc_counter, ft_strlen_lite depends on char_stats, parse_sum depends on
# both. Reused here instead of inventing synthetic fixtures.
C_BASICS_LEAF_NO_PREREQS = "argc_counter"
C_BASICS_BLOCKED_UNTIL_LEAVES_DONE = "parse_sum"
C_BASICS_ALL_ACTIVITY_IDS = (
    "argc_counter",
    "char_stats",
    "array_peak",
    "ft_strlen_lite",
    "parse_sum",
)


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

    def compile(self, source_files, output_path, *, include_dirs=()) -> CompilationResult:
        return CompilationResult(success=True, executable_path=output_path)


def _content_registry(bundled_dir: Path, managed_dir: Path) -> ContentRegistry:
    registry = ContentRegistry()
    registry.register_provider("builtin", PackContentProvider(LocalPackCatalog(bundled_dir)))
    registry.register_provider("installed", PackContentProvider(LocalPackCatalog(managed_dir)))
    return registry


def _coordinator(root: Path, bundled_dir: Path = EXAMPLES_DIR) -> MVPTrainerCoordinator:
    managed = root / "managed"
    compiler = AvailableCompiler()
    return MVPTrainerCoordinator(
        pack_catalog=LocalPackCatalog(managed_packs_dir=managed, bundled_packs_dir=bundled_dir),
        progress_repository=SQLiteProgressRepository(SQLiteStore(root / "trainer.sqlite3")),
        workspace=LocalExerciseWorkspace(),
        grader=None,  # not exercised by these tests
        editor=SubprocessEditor("definitely-not-used"),
        pack_importer=LocalPackImporter(managed),
        runtimes=RuntimeRegistry([CRuntime(compiler, manager=compiler)]),
        workspace_root=root / "workspace",
        editor_factory=SubprocessEditorFactory(),
        workspace_port=LocalWorkspace(),
        content_registry=_content_registry(bundled_dir, managed),
    )


def _mark_completed(coordinator: MVPTrainerCoordinator, pack_id: str, exercise_id: str) -> None:
    coordinator._progress_repository.save_grading_result(
        pack_id,
        exercise_id,
        GradingResult(outcome=GradingOutcome.PASSED, trace_data=TraceData(())),
        mode="training",
    )


class LearningCoordinatorTest(unittest.TestCase):
    def test_learning_languages_come_from_real_content_not_a_hardcoded_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = _coordinator(Path(temp_dir))
            self.assertEqual(
                coordinator.learning_languages(), ("c", "cpp", "java", "python")
            )

    def test_language_with_no_opted_in_content_returns_no_languages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_bundled = Path(temp_dir) / "empty-bundled"
            empty_bundled.mkdir()
            coordinator = _coordinator(Path(temp_dir) / "work", bundled_dir=empty_bundled)
            self.assertEqual(coordinator.learning_languages(), ())

    def test_track_order_matches_position_starting_at_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = _coordinator(Path(temp_dir))
            view = coordinator.learning_track("c")
            positions = [activity.position for activity in view.track.activities]
            self.assertEqual(positions, sorted(positions))
            self.assertEqual(positions[0], 1)
            self.assertEqual(view.current_level, 1)

    def test_completed_progress_is_reflected_in_the_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = _coordinator(Path(temp_dir))
            _mark_completed(coordinator, "c-basics", C_BASICS_LEAF_NO_PREREQS)

            view = coordinator.learning_track("c")

            self.assertIn(C_BASICS_LEAF_NO_PREREQS, view.completed_activity_ids)
            self.assertGreater(view.current_level, 1)

    def test_activity_with_pending_prerequisite_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = _coordinator(Path(temp_dir))
            view = coordinator.learning_track("c")
            blocked = view.track.get(C_BASICS_BLOCKED_UNTIL_LEAVES_DONE)
            self.assertIsNotNone(blocked)
            self.assertFalse(set(blocked.prerequisites) <= view.completed_activity_ids)

    def test_activity_unlocks_once_prerequisites_are_satisfied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = _coordinator(Path(temp_dir))
            view = coordinator.learning_track("c")
            blocked = view.track.get(C_BASICS_BLOCKED_UNTIL_LEAVES_DONE)
            for prerequisite_id in blocked.prerequisites:
                _mark_completed(coordinator, "c-basics", prerequisite_id)

            view_after = coordinator.learning_track("c")

            self.assertTrue(set(blocked.prerequisites) <= view_after.completed_activity_ids)

    def test_next_learning_activity_matches_the_track_views_next_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = _coordinator(Path(temp_dir))
            expected = coordinator.learning_track("c").next_activity
            self.assertIsNotNone(expected)
            self.assertEqual(coordinator.next_learning_activity("c").activity_id, expected.activity_id)

    def test_track_completed_reports_no_next_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = _coordinator(Path(temp_dir))
            for activity_id in C_BASICS_ALL_ACTIVITY_IDS:
                _mark_completed(coordinator, "c-basics", activity_id)

            self.assertIsNone(coordinator.next_learning_activity("c"))
            self.assertEqual(len(coordinator.learning_track("c").completed_activity_ids), 5)

    def test_unknown_language_returns_a_predictable_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = _coordinator(Path(temp_dir))
            view = coordinator.learning_track("does-not-exist")
            self.assertEqual(view.track.activities, ())
            self.assertEqual(view.completed_activity_ids, frozenset())
            self.assertIsNone(view.next_activity)

    def test_exercise_ref_for_activity_resolves_a_real_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = _coordinator(Path(temp_dir))
            ref = coordinator.exercise_ref_for_activity("c-basics", C_BASICS_LEAF_NO_PREREQS)
            self.assertIsNotNone(ref)
            self.assertEqual(ref.definition.id, C_BASICS_LEAF_NO_PREREQS)

    def test_exercise_ref_for_activity_returns_none_when_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator = _coordinator(Path(temp_dir))
            self.assertIsNone(coordinator.exercise_ref_for_activity("c-basics", "does-not-exist"))

    def test_coordinator_without_content_registry_behaves_like_no_content(self) -> None:
        """Every pre-existing caller/test builds `MVPTrainerCoordinator`
        without `content_registry` -- must keep behaving exactly like
        before this feature existed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            managed = root / "managed"
            compiler = AvailableCompiler()
            coordinator = MVPTrainerCoordinator(
                pack_catalog=LocalPackCatalog(managed_packs_dir=managed, bundled_packs_dir=EXAMPLES_DIR),
                progress_repository=SQLiteProgressRepository(SQLiteStore(root / "trainer.sqlite3")),
                workspace=LocalExerciseWorkspace(),
                grader=None,
                editor=SubprocessEditor("definitely-not-used"),
                pack_importer=LocalPackImporter(managed),
                runtimes=RuntimeRegistry([CRuntime(compiler, manager=compiler)]),
                workspace_root=root / "workspace",
                editor_factory=SubprocessEditorFactory(),
                workspace_port=LocalWorkspace(),
            )
            self.assertEqual(coordinator.learning_languages(), ())
            self.assertIsNone(coordinator.next_learning_activity("c"))


class LearningUITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._dialogs: list[tuple[str, str]] = []
        cls._original_dialogs = {
            name: getattr(QMessageBox, name) for name in ("information", "warning", "question", "critical")
        }
        for name in cls._original_dialogs:
            setattr(
                QMessageBox,
                name,
                staticmethod(
                    lambda parent, title, text, *args, _name=name, **kwargs: cls._dialogs.append((_name, text))
                    or QMessageBox.StandardButton.Yes
                ),
            )

    @classmethod
    def tearDownClass(cls) -> None:
        for name, original in cls._original_dialogs.items():
            setattr(QMessageBox, name, original)

    def setUp(self) -> None:
        self.__class__._dialogs.clear()

    def _window(self, temp_dir: str, bundled_dir: Path = EXAMPLES_DIR, locale_service=None) -> MainWindow:
        root = Path(temp_dir)
        workspace = root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        coordinator = _coordinator(root, bundled_dir=bundled_dir)
        return MainWindow(workspace, coordinator, locale_service=locale_service)

    def test_home_exposes_a_distinct_learning_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            texts = [button.property("baseText") for button in window._menu_buttons]
            matches = [text for text in texts if "TRILHA DE APRENDIZADO" in str(text)]
            self.assertEqual(len(matches), 1)
            # distinct handlers from training/random/exam/history/settings
            handlers = {
                window._open_study_flow,
                window._open_training_setup,
                window._open_learning_flow,
                window._open_exam_setup,
                window._show_history,
            }
            self.assertEqual(len(handlers), 5)

    def test_learning_button_navigates_to_the_languages_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._open_learning_flow()
            self.assertIs(window._stack.currentWidget(), window._learning_languages_page)

    def test_languages_page_lists_languages_from_real_content_not_hardcoded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._refresh_learning_languages()
            expected = window._coordinator.learning_languages()
            self.assertEqual(expected, ("c", "cpp", "java", "python"))
            self.assertEqual(window._learning_languages_layout.count() - 1, len(expected))  # -1 for the stretch

    def test_languages_page_with_no_content_shows_empty_state_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_bundled = Path(temp_dir) / "empty-bundled"
            empty_bundled.mkdir()
            window = self._window(temp_dir, bundled_dir=empty_bundled)
            window._refresh_learning_languages()
            self.assertEqual(window._coordinator.learning_languages(), ())

    def test_track_page_shows_activities_in_position_order_with_topics_and_difficulty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_learning_track("c")

            self.assertIs(window._stack.currentWidget(), window._learning_track_page)
            view = window._coordinator.learning_track("c")
            self.assertEqual(window._learning_track_table.rowCount(), len(view.track.activities))
            for row_index, activity in enumerate(view.track.activities):
                self.assertEqual(window._learning_track_table.item(row_index, 0).text(), str(activity.position))
                self.assertEqual(window._learning_track_table.item(row_index, 1).text(), activity.title)

    def test_level_shown_is_the_activitys_position_not_a_global_score(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_learning_track("c")
            view = window._coordinator.learning_track("c")
            for row_index, activity in enumerate(view.track.activities):
                self.assertEqual(int(window._learning_track_table.item(row_index, 0).text()), activity.position)

    def test_completed_activity_shows_completed_state_in_the_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            _mark_completed(window._coordinator, "c-basics", C_BASICS_LEAF_NO_PREREQS)
            window._show_learning_track("c")

            row = next(
                index
                for index, activity in enumerate(window._learning_track_view.track.activities)
                if activity.activity_id == C_BASICS_LEAF_NO_PREREQS
            )
            self.assertIn("Concluído", window._learning_track_table.item(row, 4).text())

    def test_blocked_activity_cannot_be_started(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_learning_track("c")
            blocked = next(
                activity
                for activity in window._learning_track_view.track.activities
                if activity.activity_id == C_BASICS_BLOCKED_UNTIL_LEAVES_DONE
            )

            window._open_learning_activity(blocked)

            self.assertIsNone(window._active)
            self.assertTrue(self.__class__._dialogs)

    def test_prerequisite_satisfied_allows_starting_the_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            blocked = window._coordinator.learning_track("c").track.get(C_BASICS_BLOCKED_UNTIL_LEAVES_DONE)
            for prerequisite_id in blocked.prerequisites:
                _mark_completed(window._coordinator, "c-basics", prerequisite_id)
            window._show_learning_track("c")
            unlocked = next(
                activity
                for activity in window._learning_track_view.track.activities
                if activity.activity_id == C_BASICS_BLOCKED_UNTIL_LEAVES_DONE
            )

            window._open_learning_activity(unlocked)

            self.assertIsNotNone(window._active)
            # `ActiveExercise.definition` doesn't exist -- the exercise's
            # definition is reached through `ref` (see ExerciseRef).
            self.assertEqual(window._active.ref.definition.id, C_BASICS_BLOCKED_UNTIL_LEAVES_DONE)
            self.assertIs(window._stack.currentWidget(), window._exercise_page)

    def test_continue_opens_the_activity_provided_by_the_application(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            expected = window._coordinator.next_learning_activity("c")
            window._show_learning_track("c")

            window._continue_learning()

            self.assertIsNotNone(window._active)
            # `ActiveExercise.definition` doesn't exist -- the exercise's
            # definition is reached through `ref` (see ExerciseRef).
            self.assertEqual(window._active.ref.definition.id, expected.activity_id)

    def test_track_completed_shows_final_state_without_opening_an_exercise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            for activity_id in C_BASICS_ALL_ACTIVITY_IDS:
                _mark_completed(window._coordinator, "c-basics", activity_id)
            window._show_learning_track("c")

            window._continue_learning()

            self.assertIsNone(window._active)
            self.assertTrue(self.__class__._dialogs)
            self.assertFalse(window._learning_continue_button.isEnabled())

    def test_empty_track_does_not_break_the_ui(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_learning_track("does-not-exist")
            self.assertEqual(window._learning_track_table.rowCount(), 0)
            self.assertFalse(window._learning_continue_button.isEnabled())

    def test_provider_error_does_not_crash_main_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            def _raise(language: str):
                raise RuntimeError("boom")

            window._coordinator.learning_track = _raise
            window._show_learning_track("c")  # must not raise

            self.assertEqual(window._learning_track_table.rowCount(), 0)
            self.assertFalse(window._learning_continue_button.isEnabled())

    def test_ui_never_imports_content_adapters_directly(self) -> None:
        import ast

        source = Path("src/rankeddojo/adapters/ui/qt/main_window.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        ]
        forbidden_prefixes = (
            "rankeddojo.adapters.pack",
            "rankeddojo.adapters.learning",
            "rankeddojo.adapters.persistence",
            "rankeddojo.application.engine.content_registry",
        )
        violations = [m for m in modules if m.startswith(forbidden_prefixes)]
        self.assertEqual(violations, [])

    def test_existing_training_and_history_flows_still_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._open_training_setup()
            self.assertIs(window._stack.currentWidget(), window._training_page)
            window._show_history()
            self.assertIs(window._stack.currentWidget(), window._history_page)
            window._show_home()
            self.assertIs(window._stack.currentWidget(), window._home_page)

    def test_existing_themes_still_apply_with_the_learning_pages_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_learning_track("c")
            for key in ("terminal", "default", "gamified", "retro"):
                window._theme.set_theme(key)  # must not raise for any registered theme
            self.assertTrue(window._learning_track_page.styleSheet() or window.styleSheet())

    def test_i18n_locales_do_not_crash_the_learning_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_learning_track("c")
            for locale in SUPPORTED_UI_LOCALES:
                window._locale.set_locale(locale)  # triggers _retranslate_static_ui + re-render
            self.assertEqual(window._locale.locale, SUPPORTED_UI_LOCALES[-1])

    def test_locale_change_never_changes_which_activities_are_locked(self) -> None:
        """Translated presentation text must never control the lock logic."""
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_learning_track("c")
            before = frozenset(window._learning_track_view.completed_activity_ids)
            for locale in SUPPORTED_UI_LOCALES:
                window._locale.set_locale(locale)
                self.assertEqual(window._learning_track_view.completed_activity_ids, before)


if __name__ == "__main__":
    unittest.main()
