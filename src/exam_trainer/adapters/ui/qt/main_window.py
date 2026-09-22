from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont
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
    QTableWidget,
    QTableWidgetItem,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from exam_trainer.adapters.editor.subprocess_editor import resolve_known_editor
from exam_trainer.application.capabilities import default_exercise_capabilities
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
        self._cursor_on = True
        self._cursor_labels: list[tuple[QLabel, str]] = []
        self._cursor_buttons: set[QPushButton] = set()

        self.setWindowTitle("42 Exam Trainer")
        self.setMinimumSize(760, 520)
        self._apply_style()

        self._stack = QStackedWidget()
        self._home_page = self._build_home_page()
        self._training_page = self._build_training_page()
        self._exam_page = self._build_exam_page()
        self._exam_prepare_page = self._build_exam_prepare_page()
        self._exercise_page = self._build_exercise_page()
        self._trace_page = self._build_trace_page()
        self._history_page = self._build_history_page()
        self._settings_page = self._build_settings_page()
        self._pack_help_page = self._build_pack_help_page()
        for page in (
            self._home_page,
            self._training_page,
            self._exam_page,
            self._exam_prepare_page,
            self._exercise_page,
            self._trace_page,
            self._history_page,
            self._settings_page,
            self._pack_help_page,
        ):
            self._stack.addWidget(page)
        self.setCentralWidget(self._stack)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_exam)
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._blink_cursor)
        self._cursor_timer.start(650)
        self._refresh_packs()
        self._show_resume_if_needed()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background: #0a0e0a; color: #39ff14; font-family: Consolas, "Cascadia Mono", "Courier New", monospace; font-size: 13px; }
            QLabel#title { color: #39ff14; font-size: 28px; font-weight: 900; letter-spacing: 1px; margin-bottom: 8px; }
            QLabel#section { color: #39ff14; font-size: 16px; font-weight: 700; margin-top: 12px; }
            QLabel#muted { color: #4a6b4a; }
            QLabel#success { color: #50fa7b; font-weight: 700; }
            QLabel#error { color: #ff5555; font-weight: 700; }
            QPushButton { background: #0a0e0a; color: #39ff14; border: 1px solid #39ff14; padding: 7px 10px; border-radius: 0; text-align: left; }
            QPushButton:hover, QPushButton:focus { background: #102010; color: #50fa7b; border: 1px solid #39ff14; }
            QPushButton:pressed, QPushButton:checked { background: #0d1a0d; color: #50fa7b; border: 2px solid #39ff14; }
            QPushButton:disabled { background: #0a0e0a; color: #4a6b4a; border: 1px solid #1f3a1f; }
            QPushButton#primary { color: #50fa7b; border: 2px solid #50fa7b; font-weight: 700; }
            QPushButton#start { color: #50fa7b; border: 2px solid #39ff14; font-weight: 900; font-size: 15px; padding: 13px 18px; text-align: center; }
            QPushButton#menu { min-height: 34px; font-weight: 700; }
            QPushButton#danger { color: #ff5555; border-color: #ff5555; }
            QComboBox, QLineEdit { background: #050505; color: #39ff14; border: 1px solid #4a6b4a; padding: 6px; border-radius: 0; }
            QComboBox:hover, QComboBox:focus, QLineEdit:focus { background: #102010; color: #50fa7b; border: 1px solid #39ff14; }
            QComboBox QAbstractItemView { background: #050505; color: #39ff14; selection-background-color: #102010; selection-color: #50fa7b; border: 1px solid #39ff14; }
            QTextEdit { background: #050505; color: #39ff14; border: 1px solid #4a6b4a; padding: 8px; border-radius: 0; selection-background-color: #102010; selection-color: #50fa7b; }
            QCheckBox, QRadioButton { color: #39ff14; spacing: 8px; padding: 5px; border: 1px solid transparent; }
            QCheckBox:hover, QRadioButton:hover, QCheckBox:focus, QRadioButton:focus { background: #102010; color: #50fa7b; border: 1px solid #39ff14; }
            QCheckBox::indicator, QRadioButton::indicator { width: 15px; height: 15px; border: 1px solid #39ff14; background: #050505; }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked { background: #102010; border: 2px solid #50fa7b; }
            QTableWidget { background: #050505; color: #39ff14; gridline-color: #1f3a1f; border: 1px solid #4a6b4a; selection-background-color: #102010; selection-color: #50fa7b; }
            QHeaderView::section { background: #0a0e0a; color: #39ff14; border: 1px solid #1f3a1f; padding: 6px; font-weight: 700; }
            """
        )

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)
        self._title = self._title_label("42 EXAM TRAINER")
        self._workspace_label = QLabel(self._workspace_prompt())
        self._workspace_label.setObjectName("muted")
        self._workspace_label.setWordWrap(True)
        layout.addWidget(self._title)
        layout.addWidget(self._workspace_label)
        layout.addStretch(1)
        menu = QWidget()
        menu_layout = QVBoxLayout(menu)
        menu_layout.setContentsMargins(70, 0, 70, 0)
        menu_layout.setSpacing(10)
        for index, (label, handler) in enumerate(
            (
                ("TREINAR", self._open_training_setup),
                ("MODO PROVA", self._open_exam_setup),
                ("HISTÓRICO", self._show_history),
                ("CONFIGURAÇÕES", lambda: self._show_settings()),
            ),
            start=1,
        ):
            menu_layout.addWidget(self._button(f"> [{index}] {label}", handler, primary=index in (1, 2), role="menu"))
        layout.addWidget(menu)
        layout.addStretch(2)
        return page

    def _build_training_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(self._title_label("TREINO"))
        choices = QHBoxLayout()
        self._level_training_button = self._button("[1] TREINO POR LEVEL", self._choose_level_training, primary=True)
        self._random_training_button = self._button("[2] TREINO ALEATÓRIO", self._choose_random_training, primary=True)
        self._level_training_button.setCheckable(True)
        self._random_training_button.setCheckable(True)
        choices.addWidget(self._level_training_button)
        choices.addWidget(self._random_training_button)
        layout.addLayout(choices)

        self._training_options_panel = QWidget()
        options = QVBoxLayout(self._training_options_panel)
        options.setContentsMargins(32, 18, 32, 0)
        options.setSpacing(10)
        self._training_mode_label = QLabel("")
        self._training_mode_label.setObjectName("section")
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
        options.addWidget(QLabel("> Rank/pack"))
        options.addWidget(self._training_pack_combo)
        options.addWidget(QLabel("> Levels"))
        options.addLayout(self._level_checks_layout)
        options.addWidget(self._random_options)
        self._start_training_button = self._button("> START TRAINING", self._start_training, primary=True, role="start")
        options.addSpacing(14)
        options.addWidget(self._start_training_button)
        self._training_options_panel.setVisible(False)
        layout.addWidget(self._training_options_panel)
        layout.addStretch()
        layout.addWidget(self._button("[ VOLTAR ]", self._show_home))
        return page

    def _build_exam_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(self._title_label("MODO PROVA"))
        self._exam_resume_label = QLabel("")
        self._exam_resume_label.setWordWrap(True)
        self._resume_exam_button = self._button("[ CONTINUAR PROVA ]", self._resume_exam, primary=True)
        self._end_exam_button = self._button("[ ENCERRAR PROVA ]", self._end_exam)
        self._exam_pack_combo = QComboBox()
        for widget in (
            self._exam_resume_label,
            self._resume_exam_button,
            self._end_exam_button,
            QLabel("> Rank/pack"),
            self._exam_pack_combo,
            self._button("[ PREPARAR PROVA ]", self._show_exam_prepare, primary=True),
        ):
            layout.addWidget(widget)
        layout.addStretch()
        layout.addWidget(self._button("[ VOLTAR ]", self._show_home))
        return page

    def _build_exam_prepare_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(self._title_label("PREPARAR PROVA"))
        self._exam_prepare_text = QTextEdit()
        self._exam_prepare_text.setReadOnly(True)
        self._exam_prepare_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self._exam_prepare_text)
        self._start_exam_button = self._button("> START EXAM", self._start_exam, primary=True, role="start")
        layout.addWidget(self._start_exam_button)
        layout.addWidget(self._button("[ VOLTAR ]", lambda: self._stack.setCurrentWidget(self._exam_page)))
        return page

    def _build_exercise_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)
        self._exercise_title = self._title_label("")
        self._exercise_meta = QLabel("")
        self._exam_timer_label = QLabel("")
        self._subject = QTextEdit()
        self._subject.setReadOnly(True)
        self._subject.setMinimumHeight(250)
        self._subject.setFont(QFont("Consolas", 10))
        self._result_label = QLabel("")
        self._open_editor_button = self._button("[ ABRIR IDE ]", self._open_editor)
        correct_button = self._button("> CORRIGIR_", self._submit_current, primary=True)
        self._trace_button = self._button("[ VER TRACE ]", self._show_trace)
        self._next_button = self._button("[ PRÓXIMO / TROCAR ]", self._next_exercise)
        back_button = self._button("[ VOLTAR ]", self._back_from_exercise)
        buttons = QHBoxLayout()
        for button in (self._open_editor_button, correct_button, self._trace_button, self._next_button, back_button):
            buttons.addWidget(button)
        for widget in (
            self._exercise_title,
            self._exercise_meta,
            self._exam_timer_label,
            QLabel("subject.md — less"),
            self._subject,
            self._result_label,
        ):
            layout.addWidget(widget)
        layout.addLayout(buttons)
        return page

    def _build_trace_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._title_label("TRACE"))
        self._trace_text = QTextEdit()
        self._trace_text.setReadOnly(True)
        self._trace_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self._trace_text)
        layout.addWidget(self._button("[ SALVAR TRACE COMO... ]", self._save_trace_as))
        layout.addWidget(self._button("[ VOLTAR AO EXERCÍCIO ]", lambda: self._stack.setCurrentWidget(self._exercise_page)))
        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.addWidget(self._title_label("HISTÓRICO"))
        self._history_summary = QLabel("")
        self._history_summary.setObjectName("muted")
        self._history_summary.setWordWrap(True)
        self._history_table = QTableWidget(0, 6)
        self._history_table.setHorizontalHeaderLabels(("LEVEL", "EXERCÍCIO", "STATUS", "TENTATIVAS", "ÚLTIMO RESULTADO", "DATA"))
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._history_table.verticalHeader().setVisible(False)
        self._exam_history_text = QTextEdit()
        self._exam_history_text.setReadOnly(True)
        self._exam_history_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self._section_label("═══ PROGRESSO POR EXERCÍCIO ═══"))
        layout.addWidget(self._history_summary)
        layout.addWidget(self._history_table)
        layout.addWidget(self._section_label("═══ HISTÓRICO DE PROVA ═══"))
        layout.addWidget(self._exam_history_text)
        layout.addWidget(self._button("[ VOLTAR ]", self._show_home))
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        self._settings_title = self._title_label("CONFIGURAÇÕES")
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
            self._section_label("WORKSPACE"),
            self._settings_workspace,
            self._button("[ ALTERAR WORKSPACE ]", self._change_workspace),
            self._section_label("EDITOR/IDE"),
            self._editor_combo,
            self._settings_editor,
            self._button("[ SELECIONAR EXECUTÁVEL ]", self._browse_editor),
            self._button("[ SALVAR EDITOR ]", self._save_editor_setting),
            self._section_label("COMPILADOR"),
            self._settings_compiler,
            self._button("[ DETECTAR NOVAMENTE ]", self._refresh_compiler_setting),
            self._button("[ SELECIONAR COMPILADOR ]", self._choose_manual_compiler),
            self._section_label("PACKS"),
            self._packs_summary,
            self._button("[ IMPORTAR PACK ]", self._import_pack),
            self._button("[ ATUALIZAR PACKS ]", self._refresh_packs),
            self._button("[ COMO CRIAR UM PACK ]", self._show_pack_help),
        ):
            layout.addWidget(widget)
        layout.addStretch()
        layout.addWidget(self._button("[ VOLTAR ]", self._show_home))
        return page

    def _build_pack_help_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(self._title_label("COMO CRIAR UM PACK"))
        self._pack_help_text = QTextEdit()
        self._pack_help_text.setReadOnly(True)
        self._pack_help_text.setFont(QFont("Consolas", 10))
        self._pack_help_text.setPlainText(self._pack_help_content())
        layout.addWidget(self._pack_help_text)
        layout.addWidget(self._button("[ ABRIR DOCUMENTAÇÃO COMPLETA ]", self._open_full_documentation))
        layout.addWidget(self._button("[ VOLTAR PARA CONFIGURAÇÕES ]", lambda: self._show_settings("Packs")))
        return page

    def _button(self, text: str, handler, primary: bool = False, role: str = "") -> QPushButton:
        button = QPushButton(text)
        button.setProperty("baseText", text)
        button.installEventFilter(self)
        if primary:
            button.setObjectName("primary")
        if role:
            button.setObjectName(role)
        button.clicked.connect(handler)
        return button

    def _title_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("title")
        self._cursor_labels.append((label, text))
        return label

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section")
        return label

    def _workspace_prompt(self) -> str:
        name = self._workspace_path.name or str(self._workspace_path)
        parent = self._workspace_path.parent.name
        compact = f"~/{parent}/{name}" if parent else f"~/{name}"
        if len(compact) > 54:
            compact = f"~/.../{name}"
        return f"user@42:{compact}$"

    def _blink_cursor(self) -> None:
        self._cursor_on = not self._cursor_on
        cursor = "_" if self._cursor_on else " "
        for label, base_text in self._cursor_labels:
            if base_text:
                label.setText(f"{base_text} {cursor}")
        for button in list(self._cursor_buttons):
            base_text = button.property("baseText")
            if isinstance(base_text, str):
                button.setText(f"{base_text}{cursor if self._cursor_on else ' '}")

    def eventFilter(self, source: object, event: QEvent) -> bool:
        if isinstance(source, QPushButton):
            if event.type() in (QEvent.Type.Enter, QEvent.Type.FocusIn):
                self._cursor_buttons.add(source)
                self._blink_button(source)
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.FocusOut):
                self._cursor_buttons.discard(source)
                base_text = source.property("baseText")
                if isinstance(base_text, str):
                    source.setText(base_text)
        return super().eventFilter(source, event)

    def _blink_button(self, button: QPushButton) -> None:
        base_text = button.property("baseText")
        if isinstance(base_text, str):
            button.setText(f"{base_text}{'_' if self._cursor_on else ' '}")

    def _set_title_label(self, label: QLabel, text: str) -> None:
        for index, (known_label, _) in enumerate(self._cursor_labels):
            if known_label is label:
                self._cursor_labels[index] = (label, text)
                break
        label.setText(f"{text} {'_' if self._cursor_on else ' '}" if text else "")

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
        self._level_training_button.setChecked(True)
        self._random_training_button.setChecked(False)

    def _choose_random_training(self) -> None:
        self._training_kind = "random"
        self._training_mode_label.setText("Treino Aleatório")
        self._random_options.setVisible(True)
        self._training_options_panel.setVisible(True)
        self._level_training_button.setChecked(False)
        self._random_training_button.setChecked(True)

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
        self._packs_summary.setText(
            "\n".join(
                f"PACK = {pack.name} | ID = {pack.id} | VERSION = {pack.version} | LEVELS = {len(pack.levels)}"
                for pack in packs
            )
            or "PACKS = 0 installed"
        )
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
        self._set_title_label(self._exercise_title, active.ref.definition.name)
        self._exercise_meta.setText(
            f"ID: {active.ref.definition.id}\n"
            f"Rank: {active.ref.pack.name}    Level: {active.ref.level_id}"
        )
        self._subject.setPlainText(active.subject_text)
        self._result_label.setText("")
        self._result_label.setObjectName("")
        self._result_label.style().unpolish(self._result_label)
        self._result_label.style().polish(self._result_label)
        self._open_editor_button.setText(f"Abrir no {self._coordinator.editor_display_name()}")
        self._open_editor_button.setProperty("baseText", self._open_editor_button.text())
        self._trace_button.setEnabled(False)
        self._next_button.setVisible(mode == "training")
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
                    self._result_label.setObjectName("error")
                    self._result_label.style().unpolish(self._result_label)
                    self._result_label.style().polish(self._result_label)
                    self._show_training_fail_feedback()
            if self._last_outcome.result.passed:
                self._show_training_pass_feedback()
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

    def _show_training_pass_feedback(self) -> None:
        if self._mode != "training":
            return
        self._result_label.setObjectName("success")
        self._result_label.setText("[✓] EXERCÍCIO CONCLUÍDO")
        self._result_label.style().unpolish(self._result_label)
        self._result_label.style().polish(self._result_label)
        QTimer.singleShot(900, lambda: self._result_label.setText("PASS"))

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

    def _show_exam_prepare(self) -> None:
        if not self._handle_preflight(self._coordinator.preflight_exam(), self._show_exam_prepare):
            return
        pack_id = self._selected_exam_pack_id()
        if pack_id is None:
            QMessageBox.warning(self, "Prova", "Nenhum pack selecionado.")
            return
        pack = self._selected_pack(pack_id)
        if pack is None:
            QMessageBox.warning(self, "Prova", "Pack selecionado não encontrado.")
            return
        levels = self._coordinator.list_levels(pack_id)
        duration = "04:00:00"
        lines = [
            f"Pack/Rank : {pack.name}",
            f"ID        : {pack.id}",
            f"Levels    : {len(levels)}",
            "",
            "Estrutura da prova baseada no pack real:",
            *(f"  {level}" for level in levels),
            "",
            f"Duração   : {duration}",
            "Aprovação : 100%",
            "",
            "Regras:",
            "- ao errar, permanece no mesmo exercício;",
            "- ao passar, avança automaticamente;",
            "- não é permitido trocar exercício;",
            "- se o tempo acabar, a prova encerra e salva nota parcial;",
            "- se fechar no meio, a sessão pode ser retomada.",
        ]
        self._exam_prepare_text.setPlainText("\n".join(lines))
        self._stack.setCurrentWidget(self._exam_prepare_page)

    def _selected_pack(self, pack_id: str):
        for pack in self._coordinator.list_packs():
            if pack.id == pack_id:
                return pack
        return None

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
        rows = self._coordinator.exercise_history_rows()
        completed = sum(1 for row in rows if row["status"] == "concluído")
        attempted = sum(1 for row in rows if row["status"] == "tentado")
        pending = max(0, len(rows) - completed - attempted)
        bar_width = 14
        filled = 0 if not rows else round((completed / len(rows)) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        self._history_summary.setText(
            f"[{bar}] {completed}/{len(rows)} concluídos\n"
            f"PASS: {completed}   FAIL: {attempted}   PENDENTES: {pending}"
        )
        self._populate_history_table(rows)
        self._exam_history_text.setPlainText(self._exam_history_text_content())
        self._stack.setCurrentWidget(self._history_page)

    def _populate_history_table(self, rows: list[dict[str, object]]) -> None:
        self._history_table.setRowCount(len(rows))
        grouped_positions: dict[str, int] = {}
        sorted_rows = sorted(rows, key=lambda row: (str(row["level"]), str(row["exercise_id"])))
        for row_index, row in enumerate(sorted_rows):
            level = str(row["level"])
            grouped_positions[level] = grouped_positions.get(level, 0) + 1
            level_total = sum(1 for candidate in sorted_rows if str(candidate["level"]) == level)
            branch = "└──" if grouped_positions[level] == level_total else "├──"
            status = str(row["status"])
            latest = str(row["latest_result"])
            attempts = int(row["attempts"])
            marker = "[ ]"
            if status == "concluído":
                marker = "[✓]"
            elif status == "tentado":
                marker = "[✗]" if latest == "FAIL" else "[…]"
            values = (
                f"{level}/",
                f"{branch} {row['exercise_id']}",
                f"{marker} {status}",
                str(attempts),
                latest,
                self._format_date(row["last_attempt_at"]),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 2:
                    if status == "concluído":
                        item.setForeground(QColor("#50fa7b"))
                    elif status == "tentado":
                        item.setForeground(QColor("#f1fa8c"))
                    else:
                        item.setForeground(QColor("#4a6b4a"))
                if column == 4 and latest == "FAIL":
                    item.setForeground(QColor("#ff5555"))
                elif column == 4 and latest == "PASS":
                    item.setForeground(QColor("#50fa7b"))
                self._history_table.setItem(row_index, column, item)
        self._history_table.resizeColumnsToContents()

    def _exam_history_text_content(self) -> str:
        lines: list[str] = []
        exam_rows = self._coordinator.exam_history_rows()
        if not exam_rows:
            return "Nenhuma prova realizada ainda."
        for row in exam_rows:
            lines.append(
                f"{self._format_date(row.get('finished_at'))} | Rank: {escape(str(row.get('rank')))} | "
                f"nota: {row.get('final_score')} | status: {escape(str(row.get('status')))} | "
                f"duração: {row.get('used_seconds')}s | exercícios: {escape(str(row.get('exercises') or '-'))}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_date(value: object) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return str(value)[:16]

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
        self._set_title_label(self._settings_title, "CONFIGURAÇÕES" if section is None else f"CONFIGURAÇÕES > {section.upper()}")
        self._settings_workspace.setText(str(self._coordinator.workspace_root))
        self._settings_editor.setText(self._coordinator.editor_command())
        self._show_compiler_cached()
        self._stack.setCurrentWidget(self._settings_page)

    def _show_pack_help(self) -> None:
        self._pack_help_text.setPlainText(self._pack_help_content())
        self._stack.setCurrentWidget(self._pack_help_page)

    def _open_full_documentation(self) -> None:
        readme = self._documentation_path()
        if readme is None:
            QMessageBox.warning(self, "Documentação", "README.md não encontrado.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(readme)))

    @staticmethod
    def _documentation_path() -> Path | None:
        candidates = (
            Path(__file__).resolve().parents[5] / "README.md",
            Path.cwd() / "README.md",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _pack_help_content() -> str:
        capabilities = default_exercise_capabilities()
        executions = ", ".join(sorted(capabilities.executions.supported))
        generators = ", ".join(sorted(capabilities.generators.supported))
        expectations = ", ".join(sorted(capabilities.expectations.supported))
        return f"""O 42 Exam Trainer não é limitado ao Rank 02.
Qualquer rank, trilha ou coleção de exercícios pode virar um pack, desde que siga
o contrato abaixo e use capabilities suportadas pela engine.

Estrutura mínima:

my_pack/
├── pack.json
└── level0/
    └── steady_echo/
        ├── exercise.json
        └── subject.md

Para exercícios de função, adicione uma fixture de main quando necessário:

sum_values/
├── exercise.json
├── subject.md
└── fixtures/
    └── main.c

pack.json:

{{
  "id": "my_rank",
  "name": "My Rank",
  "version": "1.0.0",
  "levels": [
    {{ "id": "level0", "path": "level0" }},
    {{ "id": "level1", "path": "level1" }}
  ]
}}

exercise.json para programa com argv/stdout:

{{
  "id": "steady_echo",
  "name": "Steady Echo",
  "subject": "subject.md",
  "submission": {{
    "filename": "steady_echo.c"
  }},
  "execution": {{
    "type": "program_output"
  }},
  "tests": {{
    "generator": "random_arguments",
    "expectation": "echo_arguments"
  }},
  "limits": {{
    "timeout_seconds": 2
  }}
}}

exercise.json para função testada com main.c:

{{
  "id": "sum_values",
  "name": "Sum Values",
  "subject": "subject.md",
  "submission": {{
    "filename": "sum_values.c"
  }},
  "execution": {{
    "type": "function_with_main",
    "fixture": "fixtures/main.c"
  }},
  "tests": {{
    "generator": "random_int_array",
    "expectation": "sum_integers"
  }},
  "limits": {{
    "timeout_seconds": 2
  }}
}}

subject.md:

Use texto em estilo de prova, preservando quebras de linha:

Assignment name  : steady_echo
Expected files   : steady_echo.c
Allowed functions: write
--------------------------------------------------------------------------------

Write a program...

Examples:

$> ./steady_echo hello world | cat -e
hello world$
$>

Fixtures e arquivos de apoio:

- main.c/fixtures só devem preparar o teste, nunca conter a solução.
- Caminhos são relativos ao diretório do exercício.
- Se declarar fixture ou support_files no JSON, o arquivo precisa existir no pack.

Execution types disponíveis:
{executions}

Generators disponíveis:
{generators}

Expectations disponíveis:
{expectations}

Validação e importação:

1. Crie a pasta do pack ou um .zip contendo o pack.
2. Abra Configurações > Packs.
3. Clique em [ IMPORTAR PACK ].
4. O app valida pack.json, exercise.json, subject.md, fixtures e capabilities.
5. Se qualquer exercício falhar, o pack inteiro é rejeitado.
6. Se passar, o pack é copiado para o diretório gerenciado do app.

Packs não podem trazer comandos shell arbitrários nem código Python executável.
O conteúdo externo apenas declara o contrato; a engine do app executa o grader.
"""

    def _change_workspace(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Selecionar nova workspace")
        if not selected:
            return
        try:
            self._coordinator.change_workspace(Path(selected))
            self._workspace_path = Path(selected)
            self._workspace_label.setText(self._workspace_prompt())
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
        self._settings_compiler.setText(
            f"● COMPILER = {compiler}" if compiler else "● COMPILER = inválido/ausente"
        )

    def _show_compiler_cached(self) -> None:
        compiler = self._coordinator.current_compiler()
        self._settings_compiler.setText(
            f"● COMPILER = {compiler}" if compiler else "○ COMPILER = não detectado; use [ DETECTAR NOVAMENTE ]"
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
