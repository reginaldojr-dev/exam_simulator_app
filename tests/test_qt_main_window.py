from __future__ import annotations

import tempfile
import unittest
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from exam_trainer.adapters.editor.subprocess_editor import SubprocessEditor
from exam_trainer.adapters.pack.local_pack_catalog import LocalPackCatalog
from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter
from exam_trainer.adapters.persistence.sqlite_progress_repository import SQLiteProgressRepository
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.adapters.ui.qt.main_window import MainWindow
from exam_trainer.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from exam_trainer.adapters.workspace.local_workspace import LocalWorkspace
from exam_trainer.application.use_cases.mvp_coordinator import MVPTrainerCoordinator
from exam_trainer.domain.grading import GradingResult, TraceData
from exam_trainer.ports.compiler_port import CompilationResult
from exam_trainer.ports.grader_port import GradingRequest


class StaticGrader:
    def __init__(self, passed: bool = True) -> None:
        self.passed = passed

    def grade(self, request: GradingRequest) -> GradingResult:
        return GradingResult(
            passed=self.passed,
            trace_data=TraceData(("trace",)),
        )


class AvailableCompiler:
    def __init__(self) -> None:
        self.redetect_calls = 0

    def is_available(self) -> bool:
        return True

    def find_compiler(self) -> str:
        return "gcc"

    def redetect(self) -> str:
        self.redetect_calls += 1
        return "gcc"

    def current_compiler(self) -> str:
        return "gcc"

    def compile(self, source_files: list[Path], output_path: Path) -> CompilationResult:
        return CompilationResult(success=True, executable_path=output_path)


class MainWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _window(self, temp_dir: str, passed: bool = True) -> MainWindow:
        root = Path(temp_dir)
        workspace = root / "workspace"
        workspace.mkdir()
        compiler = AvailableCompiler()
        self._compiler = compiler
        coordinator = MVPTrainerCoordinator(
            pack_catalog=LocalPackCatalog(
                managed_packs_dir=root / "managed",
                bundled_packs_dir=Path(__file__).parent.parent / "examples" / "packs",
            ),
            progress_repository=SQLiteProgressRepository(SQLiteStore(root / "trainer.sqlite3")),
            workspace=LocalExerciseWorkspace(),
            grader=StaticGrader(passed),
            editor=SubprocessEditor("definitely-not-used"),
            pack_importer=LocalPackImporter(root / "managed"),
            compiler=compiler,
            workspace_root=workspace,
            workspace_port=LocalWorkspace(),
        )
        return MainWindow(workspace, coordinator)

    def test_home_navigates_to_training_exam_history_and_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            window._open_training_setup()
            self.assertIs(window._stack.currentWidget(), window._training_page)

            window._open_exam_setup()
            self.assertIs(window._stack.currentWidget(), window._exam_page)

            window._show_history()
            self.assertIs(window._stack.currentWidget(), window._history_page)

            window._show_settings()
            self.assertIs(window._stack.currentWidget(), window._settings_page)

    def test_resume_buttons_appear_only_with_active_exam(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            self.assertTrue(window._resume_exam_button.isHidden())
            self.assertTrue(window._end_exam_button.isHidden())

            state = window._coordinator.start_exam("sample_rank", 60)
            window._show_resume_if_needed()

            self.assertFalse(window._resume_exam_button.isHidden())
            self.assertFalse(window._end_exam_button.isHidden())
            window._coordinator.finish_exam(state, "abandoned", 0)

    def test_subject_is_rendered_as_plain_text_preserving_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            ref = next(
                ref
                for ref in window._coordinator._pack_catalog.list_exercises("sample_rank")
                if ref.definition.id == "steady_echo"
            )

            window._load_exercise(ref, mode="training", overwrite=True)

            rendered = window._subject.toPlainText()
            self.assertIn("Assignment name  : steady_echo", rendered)
            self.assertIn("$> ./steady_echo hello world | cat -e\nhello world$", rendered)

    def test_settings_open_does_not_run_compiler_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            window._show_settings()

            self.assertEqual(self._compiler.redetect_calls, 0)

    def test_pack_help_page_documents_pack_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            window._show_pack_help()

            self.assertIs(window._stack.currentWidget(), window._pack_help_page)
            content = window._pack_help_text.toPlainText()
            self.assertIn("não é limitado ao Rank 02", content)
            self.assertIn("pack.json", content)
            self.assertIn("exercise.json", content)
            self.assertIn("subject.md", content)
            self.assertIn("program_output", content)
            self.assertIn("function_with_main", content)
            self.assertIn("random_arguments", content)
            self.assertIn("echo_arguments", content)

    def test_global_style_does_not_use_neon_green_as_solid_button_background(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            style = window.styleSheet().lower()

            self.assertNotIn("background: #39ff14", style)
            self.assertIn("background: #102010", style)
            self.assertIn("qpushbutton:hover", style)

    def test_training_and_exam_next_button_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            ref = next(iter(window._coordinator._pack_catalog.list_exercises("sample_rank")))

            window._load_exercise(ref, mode="training", overwrite=True)
            self.assertFalse(window._next_button.isHidden())
            self.assertTrue(window._next_button.isEnabled())

            state = window._coordinator.start_exam("sample_rank", 60)
            window._exam_state = state
            window._load_exercise(window._coordinator.exam_ref(state), mode="exam", overwrite=True)
            self.assertTrue(window._next_button.isHidden())
            window._coordinator.finish_exam(state, "abandoned", 0)

    def test_exam_prepare_uses_real_pack_levels_and_start_exam(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            window._open_exam_setup()
            window._show_exam_prepare()

            self.assertIs(window._stack.currentWidget(), window._exam_prepare_page)
            text = window._exam_prepare_text.toPlainText()
            self.assertIn("Pack/Rank : Sample Rank", text)
            self.assertIn("level0", text)
            self.assertIn("Aprovação : 100%", text)

            window._start_exam()

            self.assertIs(window._stack.currentWidget(), window._exercise_page)
            self.assertEqual(window._mode, "exam")
            self.assertIsNotNone(window._exam_state)
            window._coordinator.finish_exam(window._exam_state, "abandoned", 0)

    def test_start_training_button_starts_training(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            window._open_training_setup()
            window._choose_level_training()
            window._start_training()

            self.assertIs(window._stack.currentWidget(), window._exercise_page)
            self.assertEqual(window._mode, "training")
            self.assertIsNotNone(window._active)

    def test_history_uses_columns_for_attempts_and_latest_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, passed=False)
            ref = next(
                ref
                for ref in window._coordinator._pack_catalog.list_exercises("sample_rank")
                if ref.definition.id == "steady_echo"
            )
            window._show_training_fail_feedback = lambda: None
            window._load_exercise(ref, mode="training", overwrite=True)
            window._submit_current()

            window._show_history()

            self.assertIs(window._stack.currentWidget(), window._history_page)
            headers = [
                window._history_table.horizontalHeaderItem(column).text()
                for column in range(window._history_table.columnCount())
            ]
            self.assertEqual(
                headers,
                ["LEVEL", "EXERCÍCIO", "STATUS", "TENTATIVAS", "ÚLTIMO RESULTADO", "DATA"],
            )
            matching_row = next(
                row
                for row in range(window._history_table.rowCount())
                if "steady_echo" in window._history_table.item(row, 1).text()
            )
            self.assertEqual(window._history_table.item(matching_row, 3).text(), "1")
            self.assertEqual(window._history_table.item(matching_row, 4).text(), "FAIL")


    def test_theme_change_restyles_window_and_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            saved: list[str] = []
            window._coordinator.save_theme = saved.append

            index = window._theme_combo.findData("minimal")
            window._theme_combo.setCurrentIndex(index)

            self.assertEqual(saved, ["minimal"])
            self.assertIn("#121417", window.styleSheet())

    def test_training_fail_shows_inline_feedback_with_trace_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, passed=False)
            ref = next(iter(window._coordinator._pack_catalog.list_exercises("sample_rank")))
            window._load_exercise(ref, mode="training", overwrite=True)

            window._submit_current()

            self.assertFalse(window._feedback.isHidden())
            self.assertEqual(window._feedback.headline, "[✗] FAIL")
            self.assertTrue(window._trace_button.isEnabled())

    def test_level_options_are_clickable_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._open_training_setup()

            self.assertTrue(window._level_training_button.isChecked())
            self.assertTrue(window._level_checks)
            first = window._level_checks[0]
            self.assertTrue(first.text().startswith("[x] "))
            first.click()
            self.assertTrue(first.text().startswith("[ ] "))
            self.assertNotIn(first.value, window._selected_levels())


    def test_home_shows_exam_trainer_brand_and_keeps_technical_window_title(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            self.assertEqual(window._cursor._titles[window._title_home], "EXAM TRAINER")
            self.assertEqual(window.windowTitle(), "42 Exam Trainer")


if __name__ == "__main__":
    unittest.main()
