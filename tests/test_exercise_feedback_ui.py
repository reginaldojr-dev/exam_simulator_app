"""Fase "exercise-feedback-ui": exercise/subject screen redesign (terminal
look, PACK label) and the new FAIL flow (trace resumido + compact clickable
status + OPEN FULL TRACE in the configured editor).

Follows the same offscreen-Qt harness as `test_qt_main_window.py`
(`RecordingEditor`, the `QMessageBox` monkeypatch, `_window(...)`); it does
not duplicate that file's coverage of unrelated flows (editor reuse, exam
timers, themes/locale layout, learning UI, ...).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from rankeddojo.adapters.editor.subprocess_editor import SubprocessEditor, SubprocessEditorFactory
from rankeddojo.adapters.pack.local_pack_catalog import LocalPackCatalog
from rankeddojo.adapters.pack.local_pack_importer import LocalPackImporter
from rankeddojo.adapters.persistence.sqlite_progress_repository import SQLiteProgressRepository
from rankeddojo.adapters.persistence.sqlite_store import SQLiteStore
from rankeddojo.adapters.runtime.c_runtime import CRuntime
from rankeddojo.adapters.ui.qt.i18n import TRANSLATIONS
from rankeddojo.adapters.ui.qt.main_window import MainWindow
from rankeddojo.adapters.ui.qt.theme.manager import ThemeManager
from rankeddojo.adapters.ui.qt.theme.themes import THEME_REGISTRY
from rankeddojo.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from rankeddojo.adapters.workspace.local_workspace import LocalWorkspace
from rankeddojo.application.engine.runtime_registry import RuntimeRegistry
from rankeddojo.application.engine.trace_summary import build_trace_summary
from rankeddojo.application.use_cases.mvp_coordinator import MVPTrainerCoordinator
from rankeddojo.domain.grading import GradingOutcome, GradingResult, TestCase, TestResult, TraceData
from rankeddojo.ports.compiler_port import CompilationResult
from rankeddojo.ports.grader_port import GradingRequest


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


class CompilationFailureGrader:
    """A submission that never even compiled -- `test_results` stays empty."""

    def grade(self, request: GradingRequest) -> GradingResult:
        return GradingResult(
            outcome=GradingOutcome.USER_FAILED,
            compile_output="hidenp.c:4:1: error: undefined reference to `foo`",
            trace_data=TraceData(
                (
                    "=== Compilation ===",
                    "Command: gcc -Wall -Wextra -Werror hidenp.c -o .build/hidenp.exe",
                    "Output:",
                    "hidenp.c:4:1: error: undefined reference to `foo`",
                    "Result: FAIL",
                    "",
                )
            ),
        )


class TestCaseFailureGrader:
    """Compiled fine; the first (only) test case's output doesn't match."""

    def grade(self, request: GradingRequest) -> GradingResult:
        test_result = TestResult(
            test_case=TestCase(args=("abc",), expected="3 0 3 1"),
            passed=False,
            stdout="3 0 3 0",
            stderr="",
            exit_code=0,
        )
        return GradingResult(
            outcome=GradingOutcome.USER_FAILED,
            compile_output="",
            test_results=(test_result,),
            trace_data=TraceData(("=== Test 1 ===", "Result: FAIL", "")),
        )


class ContentErrorGrader:
    def grade(self, request: GradingRequest) -> GradingResult:
        return GradingResult(
            outcome=GradingOutcome.CONTENT_ERROR,
            compile_output="Reference failed to compile:\n(reference build log)",
            trace_data=TraceData(("=== Content Error ===", "Reference failed to compile", "")),
        )


class StaticPassGrader:
    def grade(self, request: GradingRequest) -> GradingResult:
        return GradingResult(outcome=GradingOutcome.PASSED, trace_data=TraceData(("trace",)))


class RecordingEditor:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, bool]] = []
        self.file_calls: list[tuple[Path, bool]] = []

    def open_directory(self, directory: Path, *, reuse_window: bool = False) -> None:
        self.calls.append((directory, reuse_window))

    def open_file(self, path: Path, *, reuse_window: bool = True) -> None:
        self.file_calls.append((path, reuse_window))


class ExerciseFeedbackUITest(unittest.TestCase):
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

    def _window(self, temp_dir: str, grader=None, editor=None) -> MainWindow:
        root = Path(temp_dir)
        workspace = root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        compiler = AvailableCompiler()
        coordinator = MVPTrainerCoordinator(
            pack_catalog=LocalPackCatalog(
                managed_packs_dir=root / "managed",
                bundled_packs_dir=Path(__file__).parent.parent / "examples" / "packs",
            ),
            progress_repository=SQLiteProgressRepository(SQLiteStore(root / "trainer.sqlite3")),
            workspace=LocalExerciseWorkspace(),
            grader=grader or StaticPassGrader(),
            editor=editor or SubprocessEditor("definitely-not-used"),
            pack_importer=LocalPackImporter(root / "managed"),
            runtimes=RuntimeRegistry([CRuntime(compiler, manager=compiler)]),
            workspace_root=workspace,
            editor_factory=SubprocessEditorFactory(),
            workspace_port=LocalWorkspace(),
        )
        window = MainWindow(workspace, coordinator)
        return window

    def _load_c_basics_exercise(self, window: MainWindow):
        ref = next(
            ref
            for ref in window._coordinator._pack_catalog.list_exercises("c-basics")
            if ref.definition.id == "char_stats"
        )
        window._load_exercise(ref, mode="training", overwrite=True)
        return ref

    # ------------------------------------------------------------- header
    def test_exercise_header_shows_pack_label_not_rank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            self._load_c_basics_exercise(window)

            text = window._exercise_rank_label.text()

            self.assertTrue(text.upper().startswith("PACK"), text)
            self.assertNotIn("RANK", text.upper())
            self.assertIn("C Basics", text)  # pack name preserved

    # ------------------------------------------------------------- subject
    def test_subject_still_renders_markdown_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._load_exercise(
                next(iter(window._coordinator._pack_catalog.list_exercises("sample_rank"))),
                mode="training",
                overwrite=True,
            )
            self.assertTrue(window._subject.toPlainText().strip())

    def test_subject_command_line_shows_terminal_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            window._load_exercise(
                next(iter(window._coordinator._pack_catalog.list_exercises("sample_rank"))),
                mode="training",
                overwrite=True,
            )
            prompt = window._subject_prompt_label.text()
            self.assertIn("less subject.md", prompt)
            self.assertIn("rankeddojo@dojo:~/", prompt)
            self.assertIn(window._active.exercise_workspace_path.name, prompt)

    def test_expected_file_metadata_is_unchanged_source_of_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            ref = self._load_c_basics_exercise(window)
            # The subject's "expected file"/"allowed functions" content still
            # comes straight from the pack's own subject.md -- no new parsed
            # metadata field was introduced.
            self.assertIn("char_stats.c", window._active.subject_text)
            self.assertEqual(ref.definition.submission.filename, "char_stats.c")

    # --------------------------------------------------------------- FAIL
    def test_fail_automatically_opens_trace_summary_with_compilation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=CompilationFailureGrader())
            self._load_c_basics_exercise(window)

            window._submit_current()
            self.assertTrue(window._tasks.wait())

            self.assertFalse(window._trace_summary_panel.isHidden())
            self.assertIsNotNone(window._trace_summary)
            self.assertEqual(window._trace_summary.stage, "compilation")
            self.assertEqual(window._trace_summary.compilation.compiler, "gcc")
            self.assertIn("-Wall", window._trace_summary.compilation.flags)
            self.assertIn("hidenp.c", window._trace_summary.compilation.sources)
            self.assertEqual(window._trace_summary.compilation.output_path, ".build/hidenp.exe")

    def test_compilation_summary_never_shows_the_raw_command_as_main_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=CompilationFailureGrader())
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            title, rows = window._trace_summary_view(window._trace_summary)
            row_labels = [field for field, _ in rows]
            self.assertIn(window._t("Compilador"), row_labels)
            self.assertIn(window._t("Flags"), row_labels)
            self.assertIn(window._t("Fontes"), row_labels)
            self.assertIn(window._t("Saída"), row_labels)
            full_command = "gcc -Wall -Wextra -Werror hidenp.c -o .build/hidenp.exe"
            for _, value in rows:
                self.assertNotEqual(value, full_command)

    def test_test_failure_summary_reuses_structured_expected_received(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=TestCaseFailureGrader())
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            self.assertEqual(window._trace_summary.stage, "test")
            self.assertEqual(window._trace_summary.test_failure.expected, "3 0 3 1")
            self.assertEqual(window._trace_summary.test_failure.received, "3 0 3 0")

    def test_content_error_does_not_use_fail_status_but_still_summarizes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=ContentErrorGrader())
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            self.assertEqual(window._feedback.headline, "[!] " + window._t("CONTEÚDO INVÁLIDO"))
            self.assertEqual(window._trace_summary.stage, "content_error")
            self.assertFalse(window._trace_summary_panel.isHidden())

    def test_feedback_banner_is_compact_and_clickable_after_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=CompilationFailureGrader())
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            self.assertEqual(window._feedback.headline, "[✗] FAIL")
            self.assertIn(window._t("Clique para ver detalhes"), window._feedback.text)
            self.assertTrue(window._feedback._clickable)

    def test_clicking_feedback_banner_reopens_collapsed_trace_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=CompilationFailureGrader())
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            window._collapse_trace_summary()
            self.assertFalse(window._trace_summary_panel._expanded)

            window._feedback.clicked.emit()

            self.assertTrue(window._trace_summary_panel._expanded)
            self.assertFalse(window._trace_summary_panel.isHidden())

    def test_trace_summary_collapses_after_scheduled_delay(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=CompilationFailureGrader())
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            self.assertTrue(window._trace_summary_panel._expanded)
            self.assertTrue(window._trace_collapse_timer.isActive())

            window._trace_collapse_timer.stop()
            window._collapse_trace_summary()

            self.assertFalse(window._trace_summary_panel._expanded)
            # The compact status persists -- the panel stays visible (just collapsed),
            # not hidden entirely.
            self.assertFalse(window._trace_summary_panel.isHidden())
            self.assertFalse(window._feedback.isHidden())

    def test_view_trace_button_toggles_the_summary_panel(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=CompilationFailureGrader())
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())
            self.assertTrue(window._trace_button.isEnabled())

            window._collapse_trace_summary()
            self.assertFalse(window._trace_summary_panel._expanded)

            window._toggle_trace_summary()

            self.assertTrue(window._trace_summary_panel._expanded)

    def test_view_trace_button_disabled_without_a_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=StaticPassGrader())
            self._load_c_basics_exercise(window)
            self.assertFalse(window._trace_button.isEnabled())

    def test_open_full_trace_opens_configured_editor_as_a_new_tab(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            editor = RecordingEditor()
            window = self._window(temp_dir, grader=CompilationFailureGrader(), editor=editor)
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            window._open_full_trace()

            self.assertEqual(len(editor.file_calls), 1)
            path, reuse_window = editor.file_calls[0]
            self.assertEqual(path, window._last_outcome.trace_path)
            self.assertTrue(reuse_window)
            self.assertTrue(path.name, "trace.txt")
            # Never routed through RankedDojo's own window/pages.
            self.assertIs(window._stack.currentWidget(), window._exercise_page)

    # --------------------------------------------------------------- PASS
    def test_pass_feedback_is_compact_and_not_clickable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=StaticPassGrader())
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            self.assertEqual(window._feedback.headline, "[✓] PASS")
            self.assertFalse(window._feedback._clickable)
            self.assertTrue(window._trace_summary_panel.isHidden())

    # ----------------------------------------------------------- animations
    def test_trace_summary_skips_animation_when_theme_disables_animations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=CompilationFailureGrader())
            window._theme._tokens = replace(window._theme.tokens, animations=False)
            self._load_c_basics_exercise(window)

            window._submit_current()
            self.assertTrue(window._tasks.wait())

            # No animation running -- the body is already in its final, visible state.
            self.assertIsNone(window._trace_summary_panel._body_animation)
            self.assertTrue(window._trace_summary_panel._body.isVisible())

    # -------------------------------------------------------------- themes
    def test_existing_themes_still_apply_with_the_redesigned_subject_and_trace_panel(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=CompilationFailureGrader())
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            for tokens in THEME_REGISTRY.themes():
                window._theme.set_theme(tokens.key)
                QApplication.processEvents()
                self.assertIn(tokens.text_primary.lower().lstrip("#")[:3], window._subject.document().defaultStyleSheet().lower())

    # ---------------------------------------------------------------- i18n
    def test_new_strings_are_translated_for_en_and_es(self) -> None:
        for key in (
            "Pack",
            "Clique para ver detalhes",
            "Abrir trace completo",
            "Falha de compilação",
            "Erro de conteúdo",
            "Compilador",
            "Flags",
            "Fontes",
            "Saída",
            "Esperado",
            "Recebido",
            "Código de saída",
            "Timeout",
        ):
            self.assertIn(key, TRANSLATIONS["en"], key)
            self.assertIn(key, TRANSLATIONS["es"], key)

    # ------------------------------------------------------ grading intact
    def test_trace_summary_is_built_from_the_already_produced_grading_result(self) -> None:
        """No re-grading/re-execution: the summary comes from the same
        `GradingResult` already persisted, matching the raw trace.txt."""
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=TestCaseFailureGrader())
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            expected_summary = build_trace_summary(window._last_outcome.result)
            self.assertEqual(window._trace_summary, expected_summary)
            self.assertTrue(window._last_outcome.trace_path.exists())
            self.assertIn("Test 1", window._last_outcome.trace_path.read_text(encoding="utf-8"))

    # ------------------------------------------------- split sidebar layout
    def test_window_opens_at_the_larger_default_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            self.assertEqual(window.size().width(), 1100)
            self.assertEqual(window.size().height(), 760)

    def test_sidebar_holds_breadcrumb_title_and_feedback_banner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            self._load_c_basics_exercise(window)

            sidebar = window._exercise_id_label.parentWidget()
            while sidebar is not None and sidebar.property("role") != "exercise-sidebar":
                sidebar = sidebar.parentWidget()
            self.assertIsNotNone(sidebar, "breadcrumb must live inside the exercise-sidebar widget")
            self.assertIs(window._exercise_title.parentWidget(), sidebar)
            self.assertIs(window._feedback.parentWidget(), sidebar)

    def test_footer_buttons_live_in_a_fixed_footer_bar(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            self._load_c_basics_exercise(window)

            footer = window._correct_button.parentWidget()
            while footer is not None and footer.property("role") != "exercise-footer":
                footer = footer.parentWidget()
            self.assertIsNotNone(footer, "action buttons must live inside the exercise-footer widget")
            for button in (
                window._open_editor_button,
                window._correct_button,
                window._trace_button,
                window._next_button,
                window._exercise_back_button,
            ):
                parent = button.parentWidget()
                while parent is not None and parent is not footer and parent.property("role") != "exercise-footer":
                    parent = parent.parentWidget()
                self.assertIs(parent, footer)

    def test_subject_is_not_inside_the_sidebar_and_keeps_stretch_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            self._load_c_basics_exercise(window)

            sidebar = window._exercise_id_label.parentWidget()
            while sidebar is not None and sidebar.property("role") != "exercise-sidebar":
                sidebar = sidebar.parentWidget()
            parent = window._subject.parentWidget()
            self.assertIsNot(parent, sidebar)
            self.assertNotEqual(sidebar.property("role"), "")

    def test_difficulty_badge_shows_when_the_pack_declares_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            ref = self._load_c_basics_exercise(window)
            self.assertEqual(ref.definition.difficulty, "intro")
            self.assertTrue(window._exercise_difficulty_label.isVisible())
            self.assertIn("INTRO", window._exercise_difficulty_label.text().upper())

    def test_difficulty_badge_hides_when_the_pack_declares_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            ref = next(iter(window._coordinator._pack_catalog.list_exercises("sample_rank")))
            self.assertIsNone(ref.definition.difficulty)
            window._load_exercise(ref, mode="training", overwrite=True)
            self.assertFalse(window._exercise_difficulty_label.isVisible())

    def test_sidebar_expected_file_comes_from_the_real_submission_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            ref = self._load_c_basics_exercise(window)
            self.assertIn(ref.definition.submission.filename, window._sidebar_expected_value.text())

    def test_sidebar_allowed_and_not_allowed_extracted_from_the_real_subject(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            self._load_c_basics_exercise(window)

            self.assertTrue(window._sidebar_allowed_block.isVisible())
            self.assertIn("write", window._sidebar_allowed_value.text())
            self.assertTrue(window._sidebar_not_allowed_block.isVisible())
            not_allowed_text = window._sidebar_not_allowed_value.text()
            self.assertIn("printf", not_allowed_text)
            self.assertIn("isalpha", not_allowed_text)
            self.assertIn("isdigit", not_allowed_text)

    def test_sidebar_allowed_blocks_hide_when_subject_has_no_matching_heading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            ref = next(iter(window._coordinator._pack_catalog.list_exercises("sample_rank")))
            window._load_exercise(ref, mode="training", overwrite=True)

            self.assertFalse(window._sidebar_allowed_block.isVisible())
            self.assertFalse(window._sidebar_not_allowed_block.isVisible())

    def test_feedback_banner_still_sits_in_the_sidebar_after_a_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir, grader=CompilationFailureGrader())
            self._load_c_basics_exercise(window)
            window._submit_current()
            self.assertTrue(window._tasks.wait())

            sidebar = window._feedback.parentWidget()
            while sidebar is not None and sidebar.property("role") != "exercise-sidebar":
                sidebar = sidebar.parentWidget()
            self.assertIsNotNone(sidebar)
            self.assertTrue(window._feedback.isVisible())

    def test_split_layout_survives_locale_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            self._load_c_basics_exercise(window)
            window._locale.set_locale("en")
            self.assertIn("EXPECTED", window._sidebar_expected_header.text().upper())
            self.assertIn("ALLOWED", window._sidebar_allowed_header.text().upper())
            window._locale.set_locale("pt-BR")

    def test_split_layout_strings_are_translated_for_en_and_es(self) -> None:
        for key in ("Arquivos esperados", "Permitido", "Não permitido"):
            self.assertIn(key, TRANSLATIONS["en"], key)
            self.assertIn(key, TRANSLATIONS["es"], key)

    def test_all_themes_apply_cleanly_to_the_new_sidebar_and_footer_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = self._window(temp_dir)
            self._load_c_basics_exercise(window)
            for tokens in THEME_REGISTRY.themes():
                window._theme.set_theme(tokens.key)  # must not raise for any preset
                QApplication.processEvents()
            window._theme.set_theme("terminal")


if __name__ == "__main__":
    unittest.main()
