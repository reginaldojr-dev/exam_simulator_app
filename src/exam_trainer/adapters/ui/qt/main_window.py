from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from exam_trainer.adapters.editor.subprocess_editor import resolve_known_editor
from exam_trainer.application.mvp_models import ActiveExercise, CorrectionOutcome, ExerciseRef
from exam_trainer.application.use_cases.mvp_coordinator import (
    ExamState,
    MVPTrainerCoordinator,
    PreflightResult,
    TrainingOptions,
)


class MainWindow(QMainWindow):
    def __init__(self, workspace_path: Path, coordinator: MVPTrainerCoordinator) -> None:
        super().__init__()
        self._workspace_path = workspace_path
        self._coordinator = coordinator
        self._active: ActiveExercise | None = None
        self._last_outcome: CorrectionOutcome | None = None
        self._training_options: TrainingOptions | None = None
        self._exam_state: ExamState | None = None
        self._mode = "training"
        self._training_kind = "level"
        self._pending_action: Callable[[], None] | None = None

        self.setWindowTitle("42 Exam Trainer")
        self.setMinimumSize(760, 520)
        self._apply_style()

        self._stack = QStackedWidget()
        self._home_page = self._build_home_page()
        self._training_page = self._build_training_page()
        self._exam_page = self._build_exam_page()
        self._exercise_page = self._build_exercise_page()
        self._trace_page = self._build_trace_page()
        self._history_page = self._build_history_page()
        self._settings_page = self._build_settings_page()
        for page in (
            self._home_page,
            self._training_page,
            self._exam_page,
            self._exercise_page,
            self._trace_page,
            self._history_page,
            self._settings_page,
        ):
            self._stack.addWidget(page)
        self.setCentralWidget(self._stack)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_exam)
        self._refresh_packs()
        self._show_resume_if_needed()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background: #15171a; color: #eeeeee; font-size: 13px; }
            QLabel#title { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
            QLabel#section { font-size: 16px; font-weight: 700; margin-top: 10px; }
            QPushButton { background: #2d3138; border: 1px solid #454b55; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background: #373d46; }
            QPushButton#primary { background: #3662a8; border-color: #4778c7; font-weight: 700; }
            QComboBox, QLineEdit, QTextEdit { background: #0f1114; border: 1px solid #363b44; padding: 5px; }
            """
        )

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)
        title = QLabel("42 Exam Trainer")
        title.setObjectName("title")
        self._workspace_label = QLabel(f"Workspace: {self._workspace_path}")
        self._workspace_label.setWordWrap(True)
        for widget in (
            title,
            self._workspace_label,
            self._button("Treinar", self._open_training_setup, primary=True),
            self._button("Modo Prova", self._open_exam_setup, primary=True),
            self._button("Histórico", self._show_history),
            self._button("Configurações", lambda: self._show_settings()),
        ):
            layout.addWidget(widget)
        layout.addStretch()
        return page

    def _build_training_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(self._section_label("Treino"))
        choices = QHBoxLayout()
        choices.addWidget(self._button("Treino por Level", self._choose_level_training, primary=True))
        choices.addWidget(self._button("Treino Aleatório", self._choose_random_training, primary=True))
        layout.addLayout(choices)

        self._training_options_panel = QWidget()
        options = QVBoxLayout(self._training_options_panel)
        options.setContentsMargins(0, 8, 0, 0)
        self._training_mode_label = QLabel("")
        self._training_pack_combo = QComboBox()
        self._pack_combo = self._training_pack_combo
        self._training_pack_combo.currentIndexChanged.connect(self._refresh_levels)
        self._level_checks_layout = QVBoxLayout()
        self._level_checks: list[QCheckBox] = []
        self._prioritize_radio = QRadioButton("Priorizar não concluídos")
        self._only_uncompleted_radio = QRadioButton("Somente não concluídos")
        self._all_radio = QRadioButton("Todos os exercícios")
        self._allow_repeated_check = QCheckBox("Permitir repetidos")
        self._prioritize_radio.setChecked(True)
        self._random_options = QWidget()
        random_options = QVBoxLayout(self._random_options)
        random_options.setContentsMargins(0, 0, 0, 0)
        for widget in (
            self._prioritize_radio,
            self._only_uncompleted_radio,
            self._all_radio,
            self._allow_repeated_check,
        ):
            random_options.addWidget(widget)
        options.addWidget(self._training_mode_label)
        options.addWidget(QLabel("Rank/pack"))
        options.addWidget(self._training_pack_combo)
        options.addWidget(QLabel("Levels"))
        options.addLayout(self._level_checks_layout)
        options.addWidget(self._random_options)
        options.addWidget(self._button("Iniciar treino", self._start_training, primary=True))
        self._training_options_panel.setVisible(False)
        layout.addWidget(self._training_options_panel)
        layout.addStretch()
        layout.addWidget(self._button("Voltar", self._show_home))
        return page

    def _build_exam_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(self._section_label("Modo Prova"))
        self._exam_resume_label = QLabel("")
        self._exam_resume_label.setWordWrap(True)
        self._resume_exam_button = self._button("Continuar Prova", self._resume_exam, primary=True)
        self._end_exam_button = self._button("Encerrar Prova", self._end_exam)
        self._exam_pack_combo = QComboBox()
        for widget in (
            self._exam_resume_label,
            self._resume_exam_button,
            self._end_exam_button,
            QLabel("Rank/pack"),
            self._exam_pack_combo,
            self._button("Iniciar prova", self._start_exam, primary=True),
        ):
            layout.addWidget(widget)
        layout.addStretch()
        layout.addWidget(self._button("Voltar", self._show_home))
        return page

    def _build_exercise_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)
        self._exercise_title = QLabel("")
        self._exercise_title.setObjectName("section")
        self._exercise_meta = QLabel("")
        self._exam_timer_label = QLabel("")
        self._subject = QTextEdit()
        self._subject.setReadOnly(True)
        self._subject.setMinimumHeight(250)
        self._subject.setFont(QFont("Consolas", 10))
        self._result_label = QLabel("")
        self._open_editor_button = self._button("Abrir no IDE", self._open_editor)
        correct_button = self._button("Corrigir", self._submit_current, primary=True)
        self._trace_button = self._button("Ver trace", self._show_trace)
        self._next_button = self._button("Próximo / Trocar", self._next_exercise)
        back_button = self._button("Voltar", self._back_from_exercise)
        buttons = QHBoxLayout()
        for button in (self._open_editor_button, correct_button, self._trace_button, self._next_button, back_button):
            buttons.addWidget(button)
        for widget in (
            self._exercise_title,
            self._exercise_meta,
            self._exam_timer_label,
            self._subject,
            self._result_label,
        ):
            layout.addWidget(widget)
        layout.addLayout(buttons)
        return page

    def _build_trace_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._trace_text = QTextEdit()
        self._trace_text.setReadOnly(True)
        self._trace_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self._trace_text)
        layout.addWidget(self._button("Salvar trace como...", self._save_trace_as))
        layout.addWidget(self._button("Voltar ao exercício", lambda: self._stack.setCurrentWidget(self._exercise_page)))
        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        self._history_text = QTextEdit()
        self._history_text.setReadOnly(True)
        self._history_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self._section_label("Histórico"))
        layout.addWidget(self._history_text)
        layout.addWidget(self._button("Voltar", self._show_home))
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        self._settings_title = self._section_label("Configurações")
        self._settings_workspace = QLabel("")
        self._settings_editor = QLineEdit()
        self._editor_combo = QComboBox()
        self._editor_combo.addItems(("VS Code", "Zed", "Cursor", "Outro..."))
        self._settings_compiler = QLabel("")
        self._packs_summary = QLabel("")
        self._packs_summary.setWordWrap(True)
        self._editor_combo.currentTextChanged.connect(self._editor_preset_changed)
        for widget in (
            self._settings_title,
            self._section_label("Workspace"),
            self._settings_workspace,
            self._button("Alterar workspace", self._change_workspace),
            self._section_label("Editor/IDE"),
            self._editor_combo,
            self._settings_editor,
            self._button("Selecionar executável...", self._browse_editor),
            self._button("Salvar editor", self._save_editor_setting),
            self._section_label("Compilador"),
            self._settings_compiler,
            self._button("Detectar novamente", self._refresh_compiler_setting),
            self._button("Selecionar compilador manualmente...", self._choose_manual_compiler),
            self._section_label("Packs"),
            self._packs_summary,
            self._button("Importar Pack", self._import_pack),
            self._button("Atualizar Packs", self._refresh_packs),
        ):
            layout.addWidget(widget)
        layout.addStretch()
        layout.addWidget(self._button("Voltar", self._show_home))
        return page

    def _button(self, text: str, handler, primary: bool = False) -> QPushButton:
        button = QPushButton(text)
        if primary:
            button.setObjectName("primary")
        button.clicked.connect(handler)
        return button

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section")
        return label

    def _show_home(self) -> None:
        self._show_resume_if_needed()
        self._stack.setCurrentWidget(self._home_page)

    def _open_training_setup(self) -> None:
        if not self._handle_preflight(self._coordinator.preflight_training(), self._open_training_setup):
            return
        self._training_options_panel.setVisible(False)
        self._stack.setCurrentWidget(self._training_page)

    def _open_exam_setup(self) -> None:
        if not self._handle_preflight(self._coordinator.preflight_exam(), self._open_exam_setup):
            return
        self._show_resume_if_needed()
        self._stack.setCurrentWidget(self._exam_page)

    def _handle_preflight(self, preflight: PreflightResult, resume: Callable[[], None]) -> bool:
        if preflight.ok:
            return True
        self._pending_action = resume
        QMessageBox.information(self, "Configuração necessária", preflight.message)
        self._show_settings(preflight.missing)
        return False

    def _resume_pending_if_ready(self) -> None:
        if self._pending_action is None:
            return
        action = self._pending_action
        self._pending_action = None
        action()

    def _choose_level_training(self) -> None:
        self._training_kind = "level"
        self._training_mode_label.setText("Treino por Level")
        self._random_options.setVisible(False)
        self._training_options_panel.setVisible(True)

    def _choose_random_training(self) -> None:
        self._training_kind = "random"
        self._training_mode_label.setText("Treino Aleatório")
        self._random_options.setVisible(True)
        self._training_options_panel.setVisible(True)

    def _refresh_packs(self) -> None:
        packs = self._coordinator.list_packs()
        for combo in (self._training_pack_combo, self._exam_pack_combo):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for pack in packs:
                combo.addItem(f"{pack.name} ({pack.id})", pack.id)
            if current is not None:
                index = combo.findData(current)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)
        self._packs_summary.setText("\n".join(f"{pack.name} ({pack.id})" for pack in packs) or "Nenhum pack instalado.")
        self._refresh_levels()

    def _refresh_levels(self) -> None:
        while self._level_checks_layout.count():
            item = self._level_checks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._level_checks = []
        pack_id = self._selected_training_pack_id()
        if pack_id is None:
            return
        for level in self._coordinator.list_levels(pack_id):
            check = QCheckBox(level)
            check.setChecked(True)
            self._level_checks.append(check)
            self._level_checks_layout.addWidget(check)

    def _selected_training_pack_id(self) -> str | None:
        value = self._training_pack_combo.currentData()
        return None if value is None else str(value)

    def _selected_exam_pack_id(self) -> str | None:
        value = self._exam_pack_combo.currentData()
        return None if value is None else str(value)

    def _selected_levels(self) -> tuple[str, ...]:
        return tuple(check.text() for check in self._level_checks if check.isChecked())

    def _selection_mode(self) -> str:
        if self._only_uncompleted_radio.isChecked():
            return "only_uncompleted"
        if self._all_radio.isChecked():
            return "all"
        return "prioritize_uncompleted"

    def _make_training_options(self) -> TrainingOptions:
        pack_id = self._selected_training_pack_id()
        if pack_id is None:
            raise ValueError("Nenhum pack selecionado.")
        levels = self._selected_levels()
        if not levels:
            raise ValueError("Selecione pelo menos um level.")
        return TrainingOptions(
            pack_id=pack_id,
            level_ids=levels,
            selection_mode="prioritize_uncompleted" if self._training_kind == "level" else self._selection_mode(),
            allow_repeated=False if self._training_kind == "level" else self._allow_repeated_check.isChecked(),
        )

    def _start_training(self) -> None:
        if not self._handle_preflight(self._coordinator.preflight_training(), self._start_training):
            return
        try:
            self._training_options = self._make_training_options()
            self._load_exercise(self._coordinator.choose_training_exercise(self._training_options), mode="training")
        except Exception as error:
            QMessageBox.warning(self, "Treino", str(error))

    def _load_exercise(self, ref: ExerciseRef, mode: str, overwrite: bool = False) -> None:
        active = (
            self._coordinator.prepare_exam_exercise(ref, self._exam_state, overwrite=overwrite)
            if mode == "exam"
            else self._coordinator.prepare_exercise(ref, overwrite=overwrite)
        )
        if active.had_existing_submission and not overwrite:
            answer = QMessageBox.question(self, "Implementação existente", "Já existe implementação na workspace. Continuar implementação?")
            if answer != QMessageBox.StandardButton.Yes:
                active = (
                    self._coordinator.prepare_exam_exercise(ref, self._exam_state, overwrite=True)
                    if mode == "exam"
                    else self._coordinator.prepare_exercise(ref, overwrite=True)
                )
        self._mode = mode
        self._active = active
        self._last_outcome = None
        self._exercise_title.setText(active.ref.definition.name)
        self._exercise_meta.setText(f"Rank: {active.ref.pack.name} | Level: {active.ref.level_id} | Exercise: {active.ref.definition.id}")
        self._subject.setPlainText(active.subject_text)
        self._result_label.setText("")
        self._open_editor_button.setText(f"Abrir no {self._coordinator.editor_display_name()}")
        self._trace_button.setEnabled(False)
        self._next_button.setEnabled(mode == "training")
        self._stack.setCurrentWidget(self._exercise_page)

    def _open_editor(self) -> None:
        if self._active is None:
            return
        if not self._handle_preflight(self._coordinator.preflight_editor(), self._open_editor):
            return
        try:
            self._coordinator.open_in_editor(self._active)
        except Exception as error:
            QMessageBox.warning(self, "Editor", str(error))

    def _submit_current(self) -> None:
        if self._active is None:
            return
        if not self._coordinator.compiler_available():
            self._handle_preflight(PreflightResult.failed("compiler", "Configure um compilador C compatível antes de corrigir."), self._submit_current)
            return
        try:
            if self._mode == "exam" and self._exam_state is not None:
                outcome, next_state = self._coordinator.submit_exam(self._exam_state, self._active)
                self._last_outcome = outcome
                self._trace_button.setEnabled(True)
                if next_state is None:
                    self._timer.stop()
                    self._result_label.setText("PASS - prova concluída com 100%.")
                    self._show_resume_if_needed()
                    return
                if outcome.result.passed:
                    self._exam_state = next_state
                    self._load_exercise(self._coordinator.exam_ref(next_state), mode="exam")
                    return
            else:
                self._last_outcome = self._coordinator.submit_training(self._active)
                self._trace_button.setEnabled(True)
                if not self._last_outcome.result.passed:
                    self._show_training_fail_feedback()
            self._result_label.setText("PASS" if self._last_outcome.result.passed else "FAIL")
        except Exception as error:
            QMessageBox.warning(self, "Correção", str(error))

    def _show_training_fail_feedback(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Falhou")
        box.setText("Falhou.")
        trace_button = box.addButton("Ver trace", QMessageBox.ButtonRole.ActionRole)
        editor_button = box.addButton(f"Abrir no {self._coordinator.editor_display_name()}", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Voltar para corrigir", QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        if box.clickedButton() == trace_button:
            self._show_trace()
        elif box.clickedButton() == editor_button:
            self._open_editor()

    def _show_trace(self) -> None:
        if self._last_outcome is None:
            return
        self._trace_text.setPlainText(self._last_outcome.result.trace_data.as_text())
        self._stack.setCurrentWidget(self._trace_page)

    def _save_trace_as(self) -> None:
        if self._last_outcome is None:
            return
        target, _ = QFileDialog.getSaveFileName(self, "Salvar trace", "trace.txt")
        if target:
            Path(target).write_text(self._last_outcome.result.trace_data.as_text(), encoding="utf-8")

    def _next_exercise(self) -> None:
        if self._training_options is None:
            return
        try:
            self._load_exercise(self._coordinator.choose_training_exercise(self._training_options), mode="training")
        except Exception as error:
            QMessageBox.warning(self, "Treino", str(error))

    def _start_exam(self) -> None:
        if not self._handle_preflight(self._coordinator.preflight_exam(), self._start_exam):
            return
        pack_id = self._selected_exam_pack_id()
        if pack_id is None:
            QMessageBox.warning(self, "Prova", "Nenhum pack selecionado.")
            return
        try:
            self._exam_state = self._coordinator.start_exam(pack_id)
            self._timer.start(1000)
            self._load_exercise(self._coordinator.exam_ref(self._exam_state), mode="exam")
            self._show_resume_if_needed()
        except Exception as error:
            QMessageBox.warning(self, "Prova", str(error))

    def _resume_exam(self) -> None:
        state = self._coordinator.load_active_exam()
        if state is None:
            QMessageBox.information(self, "Prova", "Não há prova em andamento.")
            return
        self._exam_state = state
        self._timer.start(1000)
        self._load_exercise(self._coordinator.exam_ref(state), mode="exam")

    def _end_exam(self) -> None:
        state = self._coordinator.load_active_exam()
        if state is None:
            QMessageBox.information(self, "Prova", "Não há prova em andamento.")
            return
        self._coordinator.finish_exam(state, "abandoned", state.score)
        self._timer.stop()
        self._exam_state = None
        self._show_resume_if_needed()
        QMessageBox.information(self, "Prova", "Prova encerrada.")

    def _tick_exam(self) -> None:
        if self._exam_state is None:
            return
        state = self._coordinator.tick_exam(self._exam_state)
        if state is None:
            self._timer.stop()
            self._exam_state = None
            self._exam_timer_label.setText("Tempo esgotado.")
            QMessageBox.information(self, "Prova", "Tempo esgotado. Prova encerrada.")
            return
        self._exam_state = state
        minutes, seconds = divmod(state.remaining_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        self._exam_timer_label.setText(f"Tempo restante: {hours:02d}:{minutes:02d}:{seconds:02d} | Nota: {state.score:.0f}%")

    def _show_resume_if_needed(self) -> None:
        state = self._coordinator.load_active_exam()
        has_state = state is not None
        self._resume_exam_button.setVisible(has_state)
        self._end_exam_button.setVisible(has_state)
        if state is None:
            self._exam_resume_label.setText("")
            return
        minutes, seconds = divmod(state.remaining_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        self._exam_resume_label.setText(f"Prova em andamento\nRank: {state.pack_id}\nExercício: {state.exercise_id}\nTempo restante: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def _show_history(self) -> None:
        lines = ["Progresso por exercício", ""]
        for entry in self._coordinator.exercise_history_rows():
            symbol = "✓" if entry["status"] == "concluído" else ("◐" if entry["status"] == "tentado" else "○")
            lines.append(f"{symbol} {entry['pack']} | {entry['level']} | {entry['name']} ({entry['exercise_id']}) | {entry['status']} | tentativas: {entry['attempts']} | último: {entry['latest_result']} | data: {entry['last_attempt_at']} | modos: {entry['modes'] or '-'}")
        lines.extend(["", "Histórico de prova", ""])
        for row in self._coordinator.exam_history_rows():
            lines.append(f"{row.get('finished_at')} | {row.get('rank')} | nota: {row.get('final_score')} | {row.get('status')} | duração: {row.get('used_seconds')}s | exercícios: {row.get('exercises') or '-'}")
            for level in row.get("levels", []):
                result = "PASS" if level.get("passed") else "FAIL"
                lines.append(f"  level {level.get('level_index')}: {level.get('exercise_id')} | {result} | tentativas: {level.get('attempts_count')}")
        self._history_text.setPlainText("\n".join(lines))
        self._stack.setCurrentWidget(self._history_page)

    def _import_pack(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Selecionar pack ZIP", "", "Pack ZIP (*.zip);;Todos os arquivos (*)")
        if not source:
            source = QFileDialog.getExistingDirectory(self, "Selecionar pasta do pack")
        if not source:
            return
        try:
            pack = self._coordinator.import_pack(Path(source))
            QMessageBox.information(self, "Importar Pack", f"Pack importado: {pack.name}")
            self._refresh_packs()
            self._resume_pending_if_ready()
        except Exception as error:
            QMessageBox.warning(self, "Importar Pack", str(error))

    def _show_settings(self, section: str | None = None) -> None:
        self._settings_title.setText("Configurações" if section is None else f"Configurações > {section}")
        self._settings_workspace.setText(str(self._coordinator.workspace_root))
        self._settings_editor.setText(self._coordinator.editor_command())
        self._refresh_compiler_setting()
        self._stack.setCurrentWidget(self._settings_page)

    def _change_workspace(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Selecionar nova workspace")
        if not selected:
            return
        try:
            self._coordinator.change_workspace(Path(selected))
            self._workspace_path = Path(selected)
            self._workspace_label.setText(f"Workspace: {self._workspace_path}")
            self._settings_workspace.setText(str(self._workspace_path))
            QMessageBox.information(self, "Workspace", "Workspace atualizada.")
            self._resume_pending_if_ready()
        except Exception as error:
            QMessageBox.warning(self, "Workspace", str(error))

    def _save_editor_setting(self) -> None:
        try:
            self._coordinator.save_editor_command(self._settings_editor.text())
            self._open_editor_button.setText(f"Abrir no {self._coordinator.editor_display_name()}")
            QMessageBox.information(self, "Editor", "Editor atualizado.")
            self._resume_pending_if_ready()
        except Exception as error:
            QMessageBox.warning(self, "Editor", str(error))

    def _refresh_compiler_setting(self) -> None:
        compiler = self._coordinator.redetect_compiler()
        self._settings_compiler.setText(compiler or "Nenhum compilador C compatível com os exercícios foi encontrado.")

    def _editor_preset_changed(self, label: str) -> None:
        if label == "Outro...":
            self._browse_editor()
            return
        resolved = resolve_known_editor(label)
        if resolved is not None:
            self._settings_editor.setText(resolved)

    def _browse_editor(self) -> None:
        filter_text = "Executáveis (*.exe);;Todos os arquivos (*)" if sys.platform == "win32" else "Todos os arquivos (*)"
        selected, _ = QFileDialog.getOpenFileName(self, "Selecionar executável do editor", "", filter_text)
        if selected:
            self._settings_editor.setText(str(Path(selected)))

    def _choose_manual_compiler(self) -> None:
        filter_text = "Compiladores (*.exe);;Todos os arquivos (*)" if sys.platform == "win32" else "Todos os arquivos (*)"
        selected, _ = QFileDialog.getOpenFileName(self, "Selecionar compilador C", "", filter_text)
        if not selected:
            return
        try:
            self._coordinator.save_manual_compiler(Path(selected))
            self._refresh_compiler_setting()
            QMessageBox.information(self, "Compilador", "Compilador atualizado.")
            self._resume_pending_if_ready()
        except Exception as error:
            QMessageBox.warning(self, "Compilador", str(error))

    def _back_from_exercise(self) -> None:
        self._stack.setCurrentWidget(self._exam_page if self._mode == "exam" else self._training_page)
