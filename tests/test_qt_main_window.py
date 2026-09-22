from __future__ import annotations

import tempfile
import unittest
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
for module_name in list(sys.modules):
    if module_name == "exam_trainer" or module_name.startswith("exam_trainer."):
        del sys.modules[module_name]

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


if __name__ == "__main__":
    unittest.main()
