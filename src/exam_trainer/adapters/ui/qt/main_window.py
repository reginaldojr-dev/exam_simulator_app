from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
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
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from exam_trainer.application.mvp_models import ActiveExercise, CorrectionOutcome, ExerciseRef
from exam_trainer.application.use_cases.mvp_coordinator import (
    ExamState,
    MVPTrainerCoordinator,
    TrainingOptions,
)
from exam_trainer.adapters.editor.subprocess_editor import resolve_known_editor


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

        self.setWindowTitle("42 Exam Trainer")
        self.setMinimumSize(760, 520)

        self._stack = QStackedWidget()
        self._home_page = self._build_home_page()
        self._exercise_page = self._build_exercise_page()
        self._trace_page = self._build_trace_page()
        self._history_page = self._build_history_page()
        self._settings_page = self._build_settings_page()
        for page in (
            self._home_page,
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

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        title = QLabel("42 Exam Trainer")
        title.setObjectName("title")
        self._workspace_label = QLabel(f"Workspace: {self._workspace_path}")
        self._workspace_label.setWordWrap(True)
        self._resume_label = QLabel("")
        self._resume_label.setWordWrap(True)
        self._pack_combo = QComboBox()

        self._level_checks_layout = QVBoxLayout()
        self._level_checks: list[QCheckBox] = []
        self._prioritize_radio = QRadioButton("Priorizar não concluídos")
        self._only_uncompleted_radio = QRadioButton("Somente não concluídos")
        self._all_radio = QRadioButton("Todos os exercícios")
        self._allow_repeated_check = QCheckBox("Permitir repetidos")
        self._prioritize_radio.setChecked(True)

        buttons = [
            ("Treino por Level", self._start_training),
            ("Treino Aleatório", self._start_random_training),
            ("Modo Prova", self._start_exam),
            ("Histórico", self._show_history),
            ("Configurações", self._show_settings),
            ("Importar Pack", self._import_pack),
            ("Atualizar Packs", self._refresh_packs),
        ]
        self._resume_exam_button = QPushButton("Continuar Prova")
        self._end_exam_button = QPushButton("Encerrar Prova")
        self._resume_exam_button.clicked.connect(self._resume_exam)
        self._end_exam_button.clicked.connect(self._end_exam)

        self._pack_combo.currentIndexChanged.connect(self._refresh_levels)

        layout.addWidget(title)
        layout.addWidget(self._workspace_label)
        layout.addWidget(self._resume_label)
        layout.addWidget(QLabel("Rank/pack"))
        layout.addWidget(self._pack_combo)
        layout.addWidget(QLabel("Levels"))
        layout.addLayout(self._level_checks_layout)
        layout.addWidget(self._prioritize_radio)
        layout.addWidget(self._only_uncompleted_radio)
        layout.addWidget(self._all_radio)
        layout.addWidget(self._allow_repeated_check)
        layout.addWidget(self._resume_exam_button)
        layout.addWidget(self._end_exam_button)
        for label, handler in buttons:
            button = QPushButton(label)
            button.clicked.connect(handler)
            layout.addWidget(button)
        layout.addStretch()
        return page

    def _build_exercise_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        self._exercise_title = QLabel("")
        self._exercise_meta = QLabel("")
        self._exam_timer_label = QLabel("")
        self._subject = QTextBrowser()
        self._subject.setMinimumHeight(230)
        self._result_label = QLabel("")

        self._open_editor_button = QPushButton("Abrir no IDE")
        correct_button = QPushButton("Corrigir")
        self._trace_button = QPushButton("Ver trace")
        self._next_button = QPushButton("Próximo / Trocar")
        back_button = QPushButton("Voltar")

        self._open_editor_button.clicked.connect(self._open_editor)
        correct_button.clicked.connect(self._submit_current)
        self._trace_button.clicked.connect(self._show_trace)
        self._next_button.clicked.connect(self._next_exercise)
        back_button.clicked.connect(lambda: self._stack.setCurrentWidget(self._home_page))

        buttons = QHBoxLayout()
        for button in (self._open_editor_button, correct_button, self._trace_button, self._next_button, back_button):
            buttons.addWidget(button)

        layout.addWidget(self._exercise_title)
        layout.addWidget(self._exercise_meta)
        layout.addWidget(self._exam_timer_label)
        layout.addWidget(self._subject)
        layout.addWidget(self._result_label)
        layout.addLayout(buttons)
        return page

    def _build_trace_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._trace_text = QTextEdit()
        self._trace_text.setReadOnly(True)
        save_button = QPushButton("Salvar trace como...")
        back_button = QPushButton("Voltar ao exercício")
        save_button.clicked.connect(self._save_trace_as)
        back_button.clicked.connect(lambda: self._stack.setCurrentWidget(self._exercise_page))
        layout.addWidget(self._trace_text)
        layout.addWidget(save_button)
        layout.addWidget(back_button)
        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._history_text = QTextEdit()
        self._history_text.setReadOnly(True)
        back_button = QPushButton("Voltar")
        back_button.clicked.connect(lambda: self._stack.setCurrentWidget(self._home_page))
        layout.addWidget(self._history_text)
        layout.addWidget(back_button)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        self._settings_workspace = QLabel("")
        self._settings_editor = QLineEdit()
        self._editor_combo = QComboBox()
        self._editor_combo.addItems(("VS Code", "Zed", "Cursor", "Outro..."))
        self._settings_compiler = QLabel("")

        choose_workspace = QPushButton("Alterar workspace")
        save_editor = QPushButton("Salvar editor")
        browse_editor = QPushButton("Selecionar executável...")
        detect_compiler = QPushButton("Reexecutar detecção de compilador")
        choose_compiler = QPushButton("Selecionar compilador manualmente...")
        back_button = QPushButton("Voltar")

        choose_workspace.clicked.connect(self._change_workspace)
        self._editor_combo.currentTextChanged.connect(self._editor_preset_changed)
        browse_editor.clicked.connect(self._browse_editor)
        save_editor.clicked.connect(self._save_editor_setting)
        detect_compiler.clicked.connect(self._refresh_compiler_setting)
        choose_compiler.clicked.connect(self._choose_manual_compiler)
        back_button.clicked.connect(lambda: self._stack.setCurrentWidget(self._home_page))

        layout.addWidget(QLabel("Configurações"))
        layout.addWidget(QLabel("Workspace atual"))
        layout.addWidget(self._settings_workspace)
        layout.addWidget(choose_workspace)
        layout.addWidget(QLabel("Editor"))
        layout.addWidget(self._editor_combo)
        layout.addWidget(QLabel("Executável do editor/IDE"))
        layout.addWidget(self._settings_editor)
        layout.addWidget(browse_editor)
        layout.addWidget(save_editor)
        layout.addWidget(QLabel("Compilador C detectado"))
        layout.addWidget(self._settings_compiler)
        layout.addWidget(detect_compiler)
        layout.addWidget(choose_compiler)
        layout.addStretch()
        layout.addWidget(back_button)
        return page

    def _refresh_packs(self) -> None:
        current = self._pack_combo.currentData()
        self._pack_combo.blockSignals(True)
        self._pack_combo.clear()
        for pack in self._coordinator.list_packs():
            self._pack_combo.addItem(f"{pack.name} ({pack.id})", pack.id)
        if current is not None:
            index = self._pack_combo.findData(current)
            if index >= 0:
                self._pack_combo.setCurrentIndex(index)
        self._pack_combo.blockSignals(False)
        self._refresh_levels()

    def _refresh_levels(self) -> None:
        while self._level_checks_layout.count():
            item = self._level_checks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._level_checks = []
        pack_id = self._selected_pack_id()
        if pack_id is None:
            return
        for level in self._coordinator.list_levels(pack_id):
            check = QCheckBox(level)
            check.setChecked(True)
            self._level_checks.append(check)
            self._level_checks_layout.addWidget(check)

    def _selected_pack_id(self) -> str | None:
        value = self._pack_combo.currentData()
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
        pack_id = self._selected_pack_id()
        if pack_id is None:
            raise ValueError("Nenhum pack selecionado.")
        levels = self._selected_levels()
        if not levels:
            raise ValueError("Selecione pelo menos um level.")
        return TrainingOptions(
            pack_id=pack_id,
            level_ids=levels,
            selection_mode=self._selection_mode(),
            allow_repeated=self._allow_repeated_check.isChecked(),
        )

    def _start_training(self) -> None:
        try:
            self._training_options = self._make_training_options()
            ref = self._coordinator.choose_training_exercise(self._training_options)
            self._load_exercise(ref, mode="training")
        except Exception as error:
            QMessageBox.warning(self, "Treino", str(error))

    def _start_random_training(self) -> None:
        self._start_training()

    def _load_exercise(self, ref: ExerciseRef, mode: str, overwrite: bool = False) -> None:
        active = (
            self._coordinator.prepare_exam_exercise(ref, self._exam_state, overwrite=overwrite)
            if mode == "exam"
            else self._coordinator.prepare_exercise(ref, overwrite=overwrite)
        )
        if active.had_existing_submission and not overwrite:
            answer = QMessageBox.question(
                self,
                "Implementação existente",
                "Já existe implementação na workspace. Continuar implementação?",
            )
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
        self._exercise_meta.setText(
            f"Rank: {active.ref.pack.name} | Level: {active.ref.level_id} | Exercise: {active.ref.definition.id}"
        )
        self._subject.setMarkdown(active.subject_text)
        self._result_label.setText("")
        self._open_editor_button.setText(f"Abrir no {self._coordinator.editor_display_name()}")
        self._trace_button.setEnabled(False)
        self._next_button.setEnabled(mode == "training")
        self._stack.setCurrentWidget(self._exercise_page)

    def _open_editor(self) -> None:
        if self._active is None:
            return
        try:
            self._coordinator.open_in_editor(self._active)
        except Exception as error:
            QMessageBox.warning(self, "Editor", str(error))

    def _submit_current(self) -> None:
        if self._active is None:
            return
        if not self._coordinator.compiler_available():
            QMessageBox.warning(
                self,
                "Compilador",
                "Nenhum compilador C compatível com os exercícios foi encontrado.",
            )
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
            self._result_label.setText("PASS" if self._last_outcome.result.passed else "FAIL")
        except Exception as error:
            QMessageBox.warning(self, "Correção", str(error))

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
            ref = self._coordinator.choose_training_exercise(self._training_options)
            self._load_exercise(ref, mode="training")
        except Exception as error:
            QMessageBox.warning(self, "Treino", str(error))

    def _start_exam(self) -> None:
        pack_id = self._selected_pack_id()
        if pack_id is None:
            QMessageBox.warning(self, "Prova", "Nenhum pack selecionado.")
            return
        if not self._coordinator.compiler_available():
            QMessageBox.warning(
                self,
                "Prova",
                "Nenhum compilador C compatível com os exercícios foi encontrado. A prova não pode iniciar.",
            )
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
        self._exam_timer_label.setText(
            f"Tempo restante: {hours:02d}:{minutes:02d}:{seconds:02d} | Nota: {state.score:.0f}%"
        )

    def _show_resume_if_needed(self) -> None:
        state = self._coordinator.load_active_exam()
        if state is None:
            self._resume_label.setText("")
            self._resume_exam_button.setVisible(False)
            self._end_exam_button.setVisible(False)
            return
        minutes, seconds = divmod(state.remaining_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        self._resume_label.setText(
            f"Prova em andamento\nRank: {state.pack_id}\nExercício: {state.exercise_id}\nTempo restante: {hours:02d}:{minutes:02d}:{seconds:02d}"
        )
        self._resume_exam_button.setVisible(True)
        self._end_exam_button.setVisible(True)

    def _show_history(self) -> None:
        lines = ["Progresso por exercício", ""]
        for entry in self._coordinator.exercise_history_rows():
            symbol = "✓" if entry["status"] == "concluído" else ("◐" if entry["status"] == "tentado" else "○")
            lines.append(
                f"{symbol} {entry['pack']} | {entry['level']} | {entry['name']} ({entry['exercise_id']}) | "
                f"{entry['status']} | tentativas: {entry['attempts']} | último: {entry['latest_result']} | "
                f"data: {entry['last_attempt_at']} | modos: {entry['modes'] or '-'}"
            )
        lines.extend(["", "Histórico de prova", ""])
        for row in self._coordinator.exam_history_rows():
            lines.append(
                f"{row.get('finished_at')} | {row.get('rank')} | nota: {row.get('final_score')} | "
                f"{row.get('status')} | duração: {row.get('used_seconds')}s | exercícios: {row.get('exercises') or '-'}"
            )
            for level in row.get("levels", []):
                result = "PASS" if level.get("passed") else "FAIL"
                lines.append(
                    f"  level {level.get('level_index')}: {level.get('exercise_id')} | {result} | "
                    f"tentativas: {level.get('attempts_count')}"
                )
        self._history_text.setPlainText("\n".join(lines))
        self._stack.setCurrentWidget(self._history_page)

    def _import_pack(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar pack ZIP",
            "",
            "Pack ZIP (*.zip);;Todos os arquivos (*)",
        )
        if not source:
            source = QFileDialog.getExistingDirectory(self, "Selecionar pasta do pack")
        if not source:
            return
        try:
            pack = self._coordinator.import_pack(Path(source))
            QMessageBox.information(self, "Importar Pack", f"Pack importado: {pack.name}")
            self._refresh_packs()
        except Exception as error:
            QMessageBox.warning(self, "Importar Pack", str(error))

    def _show_settings(self) -> None:
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
        except Exception as error:
            QMessageBox.warning(self, "Workspace", str(error))

    def _save_editor_setting(self) -> None:
        try:
            self._coordinator.save_editor_command(self._settings_editor.text())
            QMessageBox.information(self, "Editor", "Editor atualizado.")
        except Exception as error:
            QMessageBox.warning(self, "Editor", str(error))

    def _refresh_compiler_setting(self) -> None:
        compiler = self._coordinator.redetect_compiler()
        self._settings_compiler.setText(
            compiler or "Nenhum compilador C compatível com os exercícios foi encontrado."
        )

    def _editor_preset_changed(self, label: str) -> None:
        if label == "Outro...":
            self._browse_editor()
            return
        resolved = resolve_known_editor(label)
        if resolved is not None:
            self._settings_editor.setText(resolved)

    def _browse_editor(self) -> None:
        filter_text = "Executáveis (*.exe);;Todos os arquivos (*)" if sys.platform == "win32" else "Todos os arquivos (*)"
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar executável do editor",
            "",
            filter_text,
        )
        if selected:
            self._settings_editor.setText(str(Path(selected)))

    def _choose_manual_compiler(self) -> None:
        filter_text = "Compiladores (*.exe);;Todos os arquivos (*)" if sys.platform == "win32" else "Todos os arquivos (*)"
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar compilador C",
            "",
            filter_text,
        )
        if not selected:
            return
        try:
            self._coordinator.save_manual_compiler(Path(selected))
            self._refresh_compiler_setting()
            QMessageBox.information(self, "Compilador", "Compilador atualizado.")
        except Exception as error:
            QMessageBox.warning(self, "Compilador", str(error))
