from __future__ import annotations

import tempfile
import threading
import unittest
import os
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton

from exam_trainer.adapters.editor.subprocess_editor import SubprocessEditor, SubprocessEditorFactory
from exam_trainer.adapters.pack.local_pack_catalog import LocalPackCatalog
from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter
from exam_trainer.adapters.persistence.json_app_config_repository import JsonAppConfigRepository
from exam_trainer.adapters.persistence.sqlite_progress_repository import SQLiteProgressRepository
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.adapters.runtime.c_runtime import CRuntime
from exam_trainer.adapters.ui.qt.i18n import LocaleService
from exam_trainer.adapters.ui.qt import main_window as main_window_module
from exam_trainer.adapters.ui.qt.main_window import MainWindow
from exam_trainer.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from exam_trainer.adapters.workspace.local_workspace import LocalWorkspace
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry
from exam_trainer.application.use_cases.mvp_coordinator import MVPTrainerCoordinator, PreflightResult
from exam_trainer.domain.grading import GradingOutcome, GradingResult, TraceData
from exam_trainer.domain.progress import ActivityProgress
from exam_trainer.ports.compiler_port import CompilationResult
from exam_trainer.ports.grader_port import GradingRequest


class StaticGrader:
    def __init__(self, passed: bool = True) -> None:
        self.passed = passed

    def grade(self, request: GradingRequest) -> GradingResult:
        return GradingResult(
            outcome=GradingOutcome.PASSED if self.passed else GradingOutcome.USER_FAILED,
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

    def cached_compiler(self) -> str | None:
        return "gcc"

    def validate_compiler(self, compiler_path) -> bool:
        return True

    def set_manual_compiler(self, compiler_path) -> None:
        pass

    def compile(
        self,
        source_files: list[Path],
        output_path: Path,
        *,
        include_dirs: tuple[Path, ...] = (),
    ) -> CompilationResult:
        return CompilationResult(success=True, executable_path=output_path)


class BlockingGrader:
    """Hold grading until the test releases it, so the UI can be observed while busy."""

    def __init__(self, passed: bool = False) -> None:
        self.passed = passed
        self.release = threading.Event()
        self.started = threading.Event()
        self.calls = 0
        self.thread_ids: list[int] = []

    def grade(self, request: GradingRequest) -> GradingResult:
        self.calls += 1
        self.thread_ids.append(threading.get_ident())
        self.started.set()
        self.release.wait(10)
        return GradingResult(
            outcome=GradingOutcome.PASSED if self.passed else GradingOutcome.USER_FAILED,
            trace_data=TraceData(("trace",)),
        )


class FailingGrader:
    def grade(self, request: GradingRequest) -> GradingResult:
        raise RuntimeError("compiler disappeared")


class RecordingEditor:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, bool]] = []

    def open_directory(self, directory: Path, *, reuse_window: bool = False) -> None:
        self.calls.append((directory, reuse_window))


class SlowProbeCompiler(AvailableCompiler):
    """Mimic SystemCCompiler: only knows whether a compiler exists after a probe."""

    def __init__(self, found: bool = True) -> None:
        super().__init__()
        self.found = found
        self._cached: str | None = None
        self.probe_threads: list[int] = []

    def cached_compiler(self) -> str | None:
        return self._cached

    def is_available(self) -> bool:
        if self._cached is None:
            self.probe_threads.append(threading.get_ident())
            self._cached = "gcc" if self.found else None
        return self._cached is not None

    def current_compiler(self) -> str | None:
        return self._cached


class MainWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        # Modal dialogs lock offscreen mode forever: in tests they are only
        # recorded. Tests that need to verify messages replace them themselves.
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

    def _window(
        self,
        temp_dir: str,
        passed: bool = True,
        grader=None,
        compiler=None,
        locale_service=None,
        editor=None,
    ) -> MainWindow:
        root = Path(temp_dir)
        workspace = root / "workspace"
        workspace.mkdir()
        compiler = compiler or AvailableCompiler()
        self._compiler = compiler
        coordinator = MVPTrainerCoordinator(
            pack_catalog=LocalPackCatalog(
                managed_packs_dir=root / "managed",
                bundled_packs_dir=Path(__file__).parent.parent / "examples" / "packs",
            ),
            progress_repository=SQLiteProgressRepository(SQLiteStore(root / "trainer.sqlite3")),
            workspace=LocalExerciseWorkspace(),
            grader=grader or StaticGrader(passed),
            editor=editor or SubprocessEditor("definitely-not-used"),
            pack_importer=LocalPackImporter(root / "managed"),
            runtimes=RuntimeRegistry([CRuntime(compiler, manager=compiler)]),
            workspace_root=workspace,
            editor_factory=SubprocessEditorFactory(),
            workspace_port=LocalWorkspace(),
        )
        window = MainWindow(workspace, coordinator, locale_service=locale_service)
        # UI tests use the example C pack; python-basics is also bundled.
        for combo in (window._training_pack_combo, window._exam_pack_combo):
            combo.setCurrentIndex(combo.findData("sample_rank"))
        return window

    @staticmethod
    def _runtime_action_button(window: MainWindow, source: str) -> QPushButton:
        for button in window._settings_page.findChildren(QPushButton):
            if button.property("sourceText") == source:
                return button
        raise AssertionError(f"No settings button found for source={source!r}")

    def test_open_editor_first_time_targets_current_exercise_without_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            editor = RecordingEditor()
            window = self._window(temp_dir, editor=editor)
            window._coordinator.preflight_editor = lambda: PreflightResult.passed()
            ref = next(iter(window._coordinator._pack_catalog.list_exercises("sample_rank")))
            window._load_exercise(ref, mode="training", overwrite=True)

            window._open_editor()

            self.assertEqual(editor.calls, [(window._active.exercise_workspace_path, False)])

    def test_training_reuses_editor_window_when_switching_exercises_after_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            editor = RecordingEditor()
            window = self._window(temp_dir, editor=editor)
            window._coordinator.preflight_editor = lambda: PreflightResult.passed()
            refs = window._coordinator._pack_catalog.list_exercises("sample_rank")[:2]
            window._load_exercise(refs[0], mode="training", overwrite=True)
            first_path = window._active.exercise_workspace_path
            window._open_editor()

            window._load_exercise(refs[1], mode="training", overwrite=True)

            self.assertEqual(editor.calls[0], (first_path, False))
            self.assertEqual(editor.calls[1], (window._active.exercise_workspace_path, True))
            self.assertTrue(first_path.exists())
            self.assertTrue(window._active.exercise_workspace_path.exists())

    def test_switching_exercise_does_not_open_editor_if_user_never_opened_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            editor = RecordingEditor()
            window = self._window(temp_dir, editor=editor)
            window._coordinator.preflight_editor = lambda: PreflightResult.passed()
            refs = window._coordinator._pack_catalog.list_exercises("sample_rank")[:2]

            window._load_exercise(refs[0], mode="training", overwrite=True)
            window._load_exercise(refs[1], mode="training", overwrite=True)

            self.assertEqual(editor.calls, [])

    def test_exam_pass_reuses_editor_window_for_next_exercise_and_preserves_previous_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            editor = RecordingEditor()
            window = self._window(temp_dir, editor=editor)
            window._coordinator.preflight_editor = lambda: PreflightResult.passed()
            state = window._coordinator.start_exam("sample_rank", 60)
            window._exam_state = state
            window._load_exercise(window._coordinator.exam_ref(state), mode="exam", overwrite=True)
            first_active = window._active
            first_path = first_active.exercise_workspace_path
            window._open_editor()

            result = window._coordinator.submit_exam(state, first_active)
            window._on_exam_graded(first_active, result)

            self.assertTrue(first_path.exists())
            self.assertIsNotNone(window._active)
            self.assertNotEqual(window._active.exercise_workspace_path, first_path)
            self.assertEqual(editor.calls[0], (first_path, False))
            self.assertEqual(editor.calls[1], (window._active.exercise_workspace_path, True))

    def test_exam_fail_does_not_reopen_editor_for_same_exercise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            editor = RecordingEditor()
            window = self._window(temp_dir, passed=False, editor=editor)
            window._coordinator.preflight_editor = lambda: PreflightResult.passed()
            state = window._coordinator.start_exam("sample_rank", 60)
            window._exam_state = state
            window._load_exercise(window._coordinator.exam_ref(state), mode="exam", overwrite=True)
            active = window._active
            window._open_editor()

            result = window._coordinator.submit_exam(state, active)
            window._on_exam_graded(active, result)

            self.assertEqual(len(editor.calls), 1)

    def test_home_navigates_to_training_exam_history_and_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            window._open_study_flow()
            self.assertIs(window._stack.currentWidget(), window._study_page)
            window._show_home()
            self.assertIs(window._stack.currentWidget(), window._home_page)

            window._open_training_setup()
            self.assertIs(window._stack.currentWidget(), window._training_page)

            window._open_exam_setup()
            self.assertIs(window._stack.currentWidget(), window._exam_page)

            window._show_history()
            self.assertIs(window._stack.currentWidget(), window._history_page)

            window._show_settings()
            self.assertIs(window._stack.currentWidget(), window._settings_page)

    def test_home_keeps_study_intent_form_on_dedicated_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            self.assertIs(window._stack.currentWidget(), window._home_page)
            self.assertFalse(window._home_page.isAncestorOf(window._study_topic))
            self.assertTrue(any("QUERO ESTUDAR ALGO NOVO" in button.text() for button in window._menu_buttons))

            window._menu_buttons[0].click()
            self.assertIs(window._stack.currentWidget(), window._study_page)
            self.assertTrue(window._study_page.isAncestorOf(window._study_topic))

    def test_home_generates_and_copies_vendor_neutral_pack_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._open_study_flow()
            window._study_topic.setPlainText("ponteiros e strings")
            c_index = window._study_language_combo.findData("c")
            self.assertGreaterEqual(c_index, 0)
            window._study_language_combo.setCurrentIndex(c_index)

            window._generate_study_prompt()
            prompt = window._study_prompt_output.toPlainText()

            self.assertIn("ponteiros e strings", prompt)
            self.assertIn("Linguagem de programacao: c", prompt)
            self.assertIn("Idioma dos subjects/conteudo: pt-BR", prompt)
            self.assertIn("Contrato atual do pack", prompt)
            self.assertIn("program_output", prompt)
            self.assertNotIn("OpenAI", prompt)
            self.assertNotIn("Claude", prompt)

            window._copy_study_prompt()
            self.assertEqual(QApplication.clipboard().text(), prompt)

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

    def test_subject_markdown_is_rendered_in_exercise_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            ref = next(
                ref
                for ref in window._coordinator._pack_catalog.list_exercises("c-basics")
                if ref.definition.id == "argc_counter"
            )

            window._load_exercise(ref, mode="training", overwrite=True)

            rendered = window._subject.toPlainText()
            first_line = next(line for line in rendered.splitlines() if line.strip())
            self.assertEqual(window._cursor._titles[window._exercise_title], "Argc Counter")
            self.assertNotEqual(first_line.strip(), "argc_counter")
            self.assertIn("argc_counter", rendered)
            self.assertIn("Arquivo esperado", rendered)
            self.assertIn("argc_counter.c", rendered)
            self.assertIn("\\n", rendered)
            self.assertNotIn("# argc_counter", rendered)
            self.assertNotIn("## Arquivo esperado", rendered)
            self.assertNotIn("`argc_counter.c`", rendered)
            stylesheet = window._subject.document().defaultStyleSheet()
            self.assertIn("h2", stylesheet)
            self.assertIn("h3", stylesheet)
            self.assertIn("border-bottom", stylesheet)

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
            self.assertIn("Contrato de Pack — RankedDojo", content)
            self.assertIn("pack.json", content)
            self.assertIn("exercise.json", content)
            self.assertIn("subject.md", content)
            self.assertIn("programming_language", content)
            self.assertIn("content_language", content)
            self.assertIn("program_output", content)
            self.assertIn("function_call", content)
            self.assertIn("random_arguments", content)
            self.assertIn("reference_output", content)
            # single source: help shows the same contract file referenced by README
            from exam_trainer.resources import pack_contract_text

            self.assertIn(pack_contract_text().strip(), content)

    def test_settings_packs_shows_capabilities_and_links_contract_docs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            window._show_settings("Packs")

            summary = window._pack_capabilities_summary.text()
            self.assertIn("schema_version 3", summary)
            self.assertIn("Runtimes:", summary)
            self.assertIn("Strategies:", summary)
            self.assertIn("Validators/expectations:", summary)
            window._show_pack_help()
            self.assertIs(window._stack.currentWidget(), window._pack_help_page)

    def test_import_pack_cancel_zip_dialog_does_not_open_folder_dialog_or_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            with mock.patch.object(window, "_ask_pack_source_format", return_value="zip"), \
                 mock.patch.object(QFileDialog, "getOpenFileName", return_value=("", "")) as open_file, \
                 mock.patch.object(QFileDialog, "getExistingDirectory") as open_dir, \
                 mock.patch.object(window._coordinator, "inspect_pack") as inspect_pack:
                window._import_pack()

            open_file.assert_called_once()
            open_dir.assert_not_called()
            inspect_pack.assert_not_called()

    def test_import_pack_format_choice_dialog_uses_explicit_buttons(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            dialog, zip_button, folder_button, cancel_button = window._pack_source_format_dialog()
            labels = {button.text() for button in dialog.buttons()}

            self.assertEqual(dialog.windowTitle(), "Importar Pack")
            self.assertEqual(dialog.text(), "Qual é o formato do pack?")
            self.assertIn("ZIP", labels)
            self.assertIn("PASTA", labels)
            self.assertIn("CANCELAR", labels)
            self.assertEqual(zip_button.text(), "ZIP")
            self.assertEqual(folder_button.text(), "PASTA")
            self.assertEqual(cancel_button.text(), "CANCELAR")

    def test_import_pack_cancel_format_choice_opens_no_explorer_and_imports_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            with mock.patch.object(window, "_ask_pack_source_format", return_value=None), \
                 mock.patch.object(QFileDialog, "getOpenFileName") as open_file, \
                 mock.patch.object(QFileDialog, "getExistingDirectory") as open_dir, \
                 mock.patch.object(window._coordinator, "inspect_pack") as inspect_pack:
                window._import_pack()

            open_file.assert_not_called()
            open_dir.assert_not_called()
            inspect_pack.assert_not_called()

    def test_import_pack_cancel_folder_dialog_does_not_open_zip_dialog_or_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            with mock.patch.object(window, "_ask_pack_source_format", return_value="folder"), \
                 mock.patch.object(QFileDialog, "getOpenFileName") as open_file, \
                 mock.patch.object(QFileDialog, "getExistingDirectory", return_value="") as open_dir, \
                 mock.patch.object(window._coordinator, "inspect_pack") as inspect_pack:
                window._import_pack()

            open_file.assert_not_called()
            open_dir.assert_called_once()
            inspect_pack.assert_not_called()

    def test_import_pack_folder_selection_starts_single_import_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            source = Path(temp_dir) / "pack-folder"
            source.mkdir()
            tasks: list[tuple[str, str]] = []
            window._run_task = lambda key, work, on_done, title, on_finally=None: tasks.append((key, title)) or True
            with mock.patch.object(window, "_ask_pack_source_format", return_value="folder"), \
                 mock.patch.object(QFileDialog, "getOpenFileName") as open_file, \
                 mock.patch.object(QFileDialog, "getExistingDirectory", return_value=str(source)) as open_dir:
                window._import_pack()

            open_file.assert_not_called()
            open_dir.assert_called_once()
            self.assertEqual(tasks, [("import", "Importar Pack")])
            self.assertEqual(window._packs_summary.text(), "validando pack...")

    def test_import_pack_errors_are_still_reported_by_task_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            source = Path(temp_dir) / "bad.zip"
            source.write_text("not a zip", encoding="utf-8")
            shown: list[str] = []
            with mock.patch.object(window, "_ask_pack_source_format", return_value="zip"), \
                 mock.patch.object(QFileDialog, "getOpenFileName", return_value=(str(source), "Pack ZIP (*.zip)")), \
                 mock.patch.object(window._coordinator, "inspect_pack", side_effect=ValueError("invalid pack")), \
                 mock.patch.object(QMessageBox, "warning", side_effect=lambda parent, title, text, *a, **k: shown.append(text)):
                window._import_pack()
                self.assertTrue(window._tasks.wait())

            self.assertEqual(shown, ["invalid pack"])

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
            self.assertTrue(window._tasks.wait())

            window._show_history()
            window._set_history_view("activities")

            self.assertIs(window._stack.currentWidget(), window._history_page)
            headers = [
                window._history_table.horizontalHeaderItem(column).text()
                for column in range(window._history_table.columnCount())
            ]
            self.assertEqual(
                headers,
                ["PACK/LEVEL", "ATIVIDADE", "STATUS", "TENTATIVAS", "ÚLTIMO RESULTADO", "DATA"],
            )
            matching_row = next(
                row
                for row in range(window._history_table.rowCount())
                if "steady_echo" in window._history_table.item(row, 1).text()
            )
            self.assertEqual(window._history_table.item(matching_row, 3).text(), "1")
            self.assertEqual(window._history_table.item(matching_row, 4).text(), "FAIL")
            self.assertEqual(window._history_table.item(matching_row, 2).text(), "[\u2717] Tentado")

            coordinator_row = next(
                row
                for row in window._coordinator.exercise_history_rows()
                if row["exercise_id"] == "steady_echo"
            )
            self.assertEqual(coordinator_row["status"], ActivityProgress.ATTEMPTED)

    def test_activity_progress_status_is_stable_internally_and_translated_in_ui(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, passed=True)
            ref = next(
                ref
                for ref in window._coordinator._pack_catalog.list_exercises("sample_rank")
                if ref.definition.id == "steady_echo"
            )
            window._load_exercise(ref, mode="training", overwrite=True)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            # Internal state never depends on translated text: the coordinator/history
            # layer always returns the stable ActivityProgress value, regardless of locale.
            coordinator_row = next(
                row
                for row in window._coordinator.exercise_history_rows()
                if row["exercise_id"] == "steady_echo"
            )
            self.assertEqual(coordinator_row["status"], ActivityProgress.COMPLETED)
            self.assertNotEqual(coordinator_row["status"], "concluído")

            window._show_history()
            window._set_history_view("activities")
            row_index = next(
                row
                for row in range(window._history_table.rowCount())
                if "steady_echo" in window._history_table.item(row, 1).text()
            )
            self.assertEqual(window._history_table.item(row_index, 2).text(), "[\u2713] Concluído")

            window._locale.set_locale("en")
            window._render_history()
            self.assertEqual(window._history_table.item(row_index, 2).text(), "[\u2713] Completed")

            window._locale.set_locale("es")
            window._render_history()
            self.assertEqual(window._history_table.item(row_index, 2).text(), "[\u2713] Completado")

            # Counts derived from ActivityProgress stay correct regardless of locale.
            self.assertIn("1/", window._history_summary.text())

    def test_history_exposes_overview_pack_session_and_timeline_views(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, passed=True)
            ref = next(iter(window._coordinator._pack_catalog.list_exercises("sample_rank")))
            window._load_exercise(ref, mode="training", overwrite=True)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            window._show_history()
            self.assertEqual(window._history_view, "overview")
            self.assertEqual(window._history_table.horizontalHeaderItem(0).text(), "ITEM")

            window._set_history_view("packs")
            self.assertEqual(window._history_table.horizontalHeaderItem(0).text(), "PACK")

            window._set_history_view("sessions")
            self.assertEqual(window._history_table.horizontalHeaderItem(0).text(), "DATA")

            window._set_history_view("timeline")
            headers = [window._history_table.horizontalHeaderItem(column).text() for column in range(window._history_table.columnCount())]
            self.assertEqual(headers, ["DATA", "SESSÃO", "PACK", "ATIVIDADE", "STATUS"])
            self.assertGreaterEqual(window._history_table.rowCount(), 1)

    def test_home_layout_survives_reference_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            for width, height in ((760, 520), (1024, 720), (1440, 900), (1920, 1080)):
                window.resize(width, height)
                QApplication.processEvents()
                self.assertFalse(window._menu_buttons[0].isHidden())
                self.assertTrue(window._menu_buttons[0].isEnabled())

    def test_settings_locale_layout_survives_reference_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._locale.set_locale("es")
            window._show_settings()
            for width, height in ((760, 520), (1024, 720), (1440, 900), (1920, 1080)):
                window.resize(width, height)
                QApplication.processEvents()
                self.assertFalse(window._locale_combo.isHidden())
                self.assertEqual(window._locale_combo.count(), 3)


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
            self.assertTrue(window._tasks.wait())

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


    def test_home_shows_rankeddojo_brand_and_window_title(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            self.assertEqual(window._cursor._titles[window._title_home], "RankedDojo")
            self.assertEqual(window.windowTitle(), "RankedDojo")
            self.assertIn("dojo@RankedDojo:", window._workspace_label.text())
            self.assertNotIn("EXAM TRAINER", window._cursor._titles[window._title_home])
            self.assertNotIn("user@42", window._workspace_label.text())
            # The mini logo mark sits beside the "RankedDojo" title; the
            # written brand itself never changes shape or name per theme.
            self.assertEqual(window._home_logo.property("role"), "logo")
            self.assertTrue(window._home_logo.text())

    def test_home_logo_mark_is_generic_and_reused_across_themes(self) -> None:
        # The logo consumer must not be rebuilt or special-cased when the
        # theme changes -- same widget instance, same glyph, regardless of
        # which theme (old or new RankedDojo one) is active.
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            logo = window._home_logo
            glyph = logo.text()

            for theme_key in ("terminal", "default", "gamified", "retro", "paper"):
                window._theme.set_theme(theme_key)
                self.assertIs(window._home_logo, logo)
                self.assertEqual(window._home_logo.text(), glyph)
                self.assertEqual(window._home_logo.property("role"), "logo")

    def test_theme_combo_offers_new_rankeddojo_themes_alongside_legacy_ones(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_settings()

            for key in ("default", "gamified", "retro", "terminal", "amber", "gameboy", "neon", "minimal", "paper"):
                self.assertGreaterEqual(window._theme_combo.findData(key), 0, key)

    def test_home_is_pt_br_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            labels = [button.property("baseText") for button in window._menu_buttons]

            self.assertIn("> [2] TREINAR", labels)
            self.assertIn("> [3] MODO PROVA", labels)
            self.assertIn("> [4] HISTÓRICO", labels)

    def test_home_can_switch_to_english_at_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            window._locale.set_locale("en")

            labels = [button.property("baseText") for button in window._menu_buttons]
            self.assertIn("> [1] STUDY SOMETHING NEW", labels)
            self.assertIn("> [2] TRAINING", labels)
            self.assertIn("> [3] EXAM MODE", labels)
            self.assertIn("> [4] HISTORY", labels)
            self.assertIn("> [5] SETTINGS", labels)

    def test_home_can_switch_to_spanish_at_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            window._locale.set_locale("es")

            labels = [button.property("baseText") for button in window._menu_buttons]
            self.assertIn("> [1] ESTUDIAR ALGO NUEVO", labels)
            self.assertIn("> [2] ENTRENAR", labels)
            self.assertIn("> [3] MODO EXAMEN", labels)
            self.assertIn("> [4] HISTORIAL", labels)
            self.assertIn("> [5] CONFIGURACIÓN", labels)

    def test_settings_shows_translated_locale_selector_with_three_languages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)

            window._locale.set_locale("en")
            window._show_settings()

            self.assertEqual(window._locale_label.text(), "Interface language")
            self.assertEqual(window._locale_combo.count(), 3)
            self.assertEqual(
                [window._locale_combo.itemText(index) for index in range(window._locale_combo.count())],
                ["Português (Brasil)", "English", "Español"],
            )

    def test_random_draw_options_replace_labels_in_pt_br_en_and_es(self) -> None:
        expectations = {
            "pt-BR": (
                "(•) Priorizar não concluídos",
                "( ) Somente não concluídos",
                "( ) Todos os exercícios",
                "[ ] Permitir repetidos",
            ),
            "en": (
                "(•) Prioritize uncompleted",
                "( ) Only uncompleted",
                "( ) All exercises",
                "[ ] Allow repeats",
            ),
            "es": (
                "(•) Priorizar no completados",
                "( ) Solo no completados",
                "( ) Todos los ejercicios",
                "[ ] Permitir repetidos",
            ),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._choose_random_training()
            for locale, expected in expectations.items():
                window._locale.set_locale(locale)
                actual = (
                    window._prioritize_radio.property("baseText"),
                    window._only_uncompleted_radio.property("baseText"),
                    window._all_radio.property("baseText"),
                    window._allow_repeated_check.property("baseText"),
                )
                self.assertEqual(actual, expected)
                for text in actual:
                    self.assertNotRegex(text, r"Priorizar não concluídos\\s+Prioritize")
                    self.assertNotRegex(text, r"Somente não concluídos\\s+Only")
                    self.assertNotRegex(text, r"Todos os exercícios\\s+All")

            self.assertEqual(window._prioritize_radio.value, "prioritize_uncompleted")
            self.assertEqual(window._only_uncompleted_radio.value, "only_uncompleted")
            self.assertEqual(window._all_radio.value, "all_exercises")
            self.assertEqual(window._allow_repeated_check.value, "allow_repeats")

    def test_settings_editor_buttons_follow_locale(self) -> None:
        expectations = {
            "pt-BR": {"[ DETECTAR AUTOMATICAMENTE ]", "[ SELECIONAR EXECUTÁVEL ]", "[ SALVAR EDITOR ]"},
            "en": {"[ DETECT AUTOMATICALLY ]", "[ SELECT EXECUTABLE ]", "[ SAVE EDITOR ]"},
            "es": {"[ DETECTAR AUTOMÁTICAMENTE ]", "[ SELECCIONAR EJECUTABLE ]", "[ GUARDAR EDITOR ]"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            for locale, expected in expectations.items():
                window._locale.set_locale(locale)
                window._show_settings()
                labels = {button.property("baseText") for button in window._settings_page.findChildren(QPushButton)}
                self.assertTrue(expected.issubset(labels))

    def test_detect_editor_automatically_button_exists_and_reuses_resolution_flow(self) -> None:
        # The explicit "Detectar automaticamente" action must call the very same
        # known-editor resolution already used by the preset combo -- never a
        # second, independent lookup.
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_settings()
            button = self._runtime_action_button(window, "[ DETECTAR AUTOMATICAMENTE ]")
            self.assertTrue(button.isEnabled())

            calls: list[str] = []
            original = window._coordinator.resolve_known_editor

            def recording_resolve(label: str) -> str | None:
                calls.append(label)
                return "/usr/bin/code" if label == "VS Code" else None

            window._coordinator.resolve_known_editor = recording_resolve
            try:
                window._detect_editor_automatically()
            finally:
                window._coordinator.resolve_known_editor = original

            # Every candidate it tried came from the single shared preset list,
            # never a locally invented VS Code/Zed/Cursor list.
            self.assertTrue(set(calls).issubset(set(main_window_module.KNOWN_EDITOR_PRESETS)))
            self.assertEqual(window._settings_editor.text(), "/usr/bin/code")
            self.assertEqual(window._editor_combo.currentData(), "VS Code")

    def test_detect_editor_automatically_prefers_current_preset_direct_redetection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_settings()
            index = window._editor_combo.findData("Zed")
            window._editor_combo.setCurrentIndex(index)

            resolved = {"VS Code": "/usr/bin/code", "Zed": "/usr/bin/zed", "Cursor": "/usr/bin/cursor"}
            window._coordinator.resolve_known_editor = lambda label: resolved.get(label)

            window._detect_editor_automatically()

            # The currently selected preset (Zed) is redetected directly, without
            # switching to a different known editor.
            self.assertEqual(window._editor_combo.currentData(), "Zed")
            self.assertEqual(window._settings_editor.text(), "/usr/bin/zed")

    def test_detect_editor_automatically_falls_back_to_first_known_editor_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_settings()
            index = window._editor_combo.findData("Outro...")
            window._editor_combo.setCurrentIndex(index)

            # Current preset ("Outro...") never resolves; the flow falls back to
            # scanning known editors and fills in the first one that is found.
            window._coordinator.resolve_known_editor = lambda label: "/opt/cursor" if label == "Cursor" else None

            window._detect_editor_automatically()

            self.assertEqual(window._editor_combo.currentData(), "Cursor")
            self.assertEqual(window._settings_editor.text(), "/opt/cursor")

    def test_detect_editor_automatically_warns_when_nothing_is_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_settings()
            window._coordinator.resolve_known_editor = lambda label: None
            before_text = window._settings_editor.text()
            self._dialogs.clear()

            window._detect_editor_automatically()

            self.assertEqual(window._settings_editor.text(), before_text)
            self.assertTrue(any(name == "warning" for name, _text in self._dialogs))

    def test_runtime_settings_status_and_actions_follow_locale(self) -> None:
        expectations = {
            "pt-BR": {
                "status": "● não verificado — use [ DETECTAR NOVAMENTE ]",
                "detect": "[ DETECTAR NOVAMENTE ]",
                "select_cpp": "[ SELECIONAR COMPILADOR C++ ]",
                "title_cpp": "COMPILADOR C++",
            },
            "en": {
                "status": "● Not checked — use [ DETECT AGAIN ]",
                "detect": "[ DETECT AGAIN ]",
                "select_cpp": "[ SELECT C++ COMPILER ]",
                "title_cpp": "C++ COMPILER",
            },
            "es": {
                "status": "● No verificado — usa [ DETECTAR DE NUEVO ]",
                "detect": "[ DETECTAR DE NUEVO ]",
                "select_cpp": "[ SELECCIONAR COMPILADOR C++ ]",
                "title_cpp": "COMPILADOR C++",
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            compiler = SlowProbeCompiler(found=True)
            window = self._window(temp_dir, compiler=compiler)
            for locale, expected in expectations.items():
                window._locale.set_locale(locale)
                window._show_settings()
                self.assertEqual(window._settings_compiler.text(), expected["status"])
                self.assertEqual(window._settings_action_text("detect-runtime:cpp"), expected["detect"])
                self.assertEqual(window._settings_action_text("select-runtime:cpp"), expected["select_cpp"])
                self.assertEqual(window._settings_title_text("runtime:cpp"), expected["title_cpp"])

    def test_locale_combo_persists_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = JsonAppConfigRepository(Path(temp_dir) / "config.json")
            locale_service = LocaleService(config, self._app)
            window = self._window(temp_dir, locale_service=locale_service)

            window._show_settings()
            window._locale_combo.setCurrentIndex(window._locale_combo.findData("es"))

            self.assertEqual(config.load_ui_locale(), "es")

    def test_pack_content_and_exercise_name_are_not_translated_by_ui_locale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            ref = next(
                ref
                for ref in window._coordinator._pack_catalog.list_exercises("c-basics")
                if ref.definition.id == "argc_counter"
            )

            window._locale.set_locale("en")
            window._load_exercise(ref, mode="training", overwrite=True)

            self.assertEqual(window._cursor._titles[window._exercise_title], "Argc Counter")
            rendered = window._subject.toPlainText()
            self.assertIn("Arquivo esperado", rendered)
            self.assertIn("argc_counter.c", rendered)

    def test_internal_status_values_are_not_translated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, passed=False)
            ref = next(iter(window._coordinator._pack_catalog.list_exercises("sample_rank")))
            window._locale.set_locale("es")
            window._load_exercise(ref, mode="training", overwrite=True)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            rows = window._coordinator.exercise_history_rows()
            self.assertTrue(any(row["latest_result"] == "FAIL" for row in rows))

    def test_runtime_preflight_message_is_translated_from_structured_missing_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            compiler = SlowProbeCompiler(found=False)
            window = self._window(temp_dir, compiler=compiler)
            window._locale.set_locale("en")
            shown: list[str] = []
            original = QMessageBox.information
            QMessageBox.information = staticmethod(lambda parent, title, text, *a, **k: shown.append(text))
            try:
                window._open_exam_setup()
                self.assertTrue(window._tasks.wait())
            finally:
                QMessageBox.information = original

            self.assertEqual(shown, ["Install or configure a compatible runtime to submit this exercise."])

    def test_grading_runs_off_the_ui_thread_and_blocks_duplicate_submissions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            grader = BlockingGrader(passed=False)
            window = self._window(temp_dir, grader=grader)
            ref = next(iter(window._coordinator._pack_catalog.list_exercises("sample_rank")))
            window._load_exercise(ref, mode="training", overwrite=True)

            window._submit_current()
            self.assertTrue(grader.started.wait(5))
            # UI already returned: the button is locked with the progress label
            self.assertFalse(window._correct_button.isEnabled())
            self.assertEqual(window._correct_button.text(), "CORRIGINDO...")
            window._submit_current()  # duplicate click is ignored
            grader.release.set()
            self.assertTrue(window._tasks.wait())

            self.assertEqual(grader.calls, 1)
            self.assertNotEqual(grader.thread_ids[0], threading.get_ident())
            self.assertTrue(window._correct_button.isEnabled())
            self.assertEqual(window._correct_button.text(), "> CORRIGIR")
            self.assertEqual(window._feedback.headline, "[✗] FAIL")

    def test_exam_timer_keeps_running_while_grading_and_does_not_finish_mid_correction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            grader = BlockingGrader(passed=False)
            window = self._window(temp_dir, grader=grader)
            state = window._coordinator.start_exam("sample_rank", 60)
            window._exam_state = state
            window._load_exercise(window._coordinator.exam_ref(state), mode="exam", overwrite=True)

            window._submit_current()
            self.assertTrue(grader.started.wait(5))
            window._tick_exam()  # timer keeps drawing during grading
            self.assertIsNotNone(window._exam_state)
            self.assertIn("⏱", window._exam_timer_label.text())
            grader.release.set()
            self.assertTrue(window._tasks.wait())
            self.assertIsNotNone(window._exam_state)
            window._coordinator.finish_exam(window._exam_state, "abandoned", 0)

    def test_grading_error_is_shown_as_message_not_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=FailingGrader())
            ref = next(iter(window._coordinator._pack_catalog.list_exercises("sample_rank")))
            window._load_exercise(ref, mode="training", overwrite=True)
            shown: list[str] = []
            original = QMessageBox.warning
            QMessageBox.warning = staticmethod(lambda parent, title, text, *a, **k: shown.append(text))
            try:
                window._submit_current()
                self.assertTrue(window._tasks.wait())
            finally:
                QMessageBox.warning = original
            self.assertEqual(shown, ["compiler disappeared"])
            self.assertTrue(window._correct_button.isEnabled())

    def test_redetect_runtime_button_sends_language_id_not_clicked_bool(self) -> None:
        # Regression guard for the QPushButton.clicked(bool checked) signal
        # overwriting the lambda's captured language default.
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_settings()
            received: list[object] = []
            window._redetect_runtime = received.append
            button = self._runtime_action_button(window, "detect-runtime:c")

            button.click()

            self.assertEqual(received, ["c"])

    def test_select_manual_runtime_button_sends_language_id_not_clicked_bool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_settings()
            received: list[object] = []
            window._choose_manual_runtime = received.append
            button = self._runtime_action_button(window, "select-runtime:c")

            button.click()

            self.assertEqual(received, ["c"])

    def test_redetect_runtime_button_click_does_not_raise_keyerror(self) -> None:
        # End-to-end: clicking the real button (not a monkeypatched handler)
        # must not crash with `KeyError: False` when Qt passes the
        # `clicked(bool)` argument through the callback chain.
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_settings()
            button = self._runtime_action_button(window, "detect-runtime:c")

            button.click()
            self.assertTrue(window._tasks.wait())

            self.assertEqual(self._compiler.redetect_calls, 1)
            self.assertIn("gcc", window._runtime_labels["c"].text())

    def test_select_manual_runtime_button_click_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, \
             mock.patch.object(QFileDialog, "getOpenFileName", return_value=("", "")) as open_file:
            window = self._window(temp_dir)
            window._show_settings()
            button = self._runtime_action_button(window, "select-runtime:c")

            button.click()

            open_file.assert_called_once()

    def test_compiler_redetection_runs_in_background(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._show_settings()
            window._refresh_compiler_setting()
            self.assertTrue(window._tasks.wait())
            self.assertEqual(self._compiler.redetect_calls, 1)
            self.assertIn("gcc", window._settings_compiler.text())

    def test_first_compiler_probe_runs_in_background_then_continues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            compiler = SlowProbeCompiler(found=True)
            window = self._window(temp_dir, compiler=compiler)

            window._open_exam_setup()
            self.assertIsNot(window._stack.currentWidget(), window._exam_page)  # ainda detectando
            self.assertTrue(window._tasks.wait())

            self.assertIs(window._stack.currentWidget(), window._exam_page)
            self.assertEqual(len(compiler.probe_threads), 1)
            self.assertNotEqual(compiler.probe_threads[0], threading.get_ident())

    def test_missing_compiler_after_background_probe_opens_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            compiler = SlowProbeCompiler(found=False)
            window = self._window(temp_dir, compiler=compiler)
            original = QMessageBox.information
            QMessageBox.information = staticmethod(lambda *a, **k: None)
            try:
                window._open_exam_setup()
                self.assertTrue(window._tasks.wait())
            finally:
                QMessageBox.information = original
            self.assertIs(window._stack.currentWidget(), window._settings_page)
            self.assertIsNotNone(window._pending_action)


if __name__ == "__main__":
    unittest.main()
