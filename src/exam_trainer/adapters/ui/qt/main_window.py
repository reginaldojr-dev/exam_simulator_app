from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from exam_trainer.adapters.ui.qt.components import widgets as ui
from exam_trainer.adapters.ui.qt.components.cursor import CursorController
from exam_trainer.adapters.ui.qt.task_runner import TaskRunner
from exam_trainer.adapters.ui.qt.theme import ThemeManager, ThemeTokens
from exam_trainer.application.capabilities import default_exercise_capabilities
from exam_trainer.resources import PACK_CONTRACT, pack_contract_text, resource_path
from exam_trainer.application.mvp_models import (
    ActiveExercise,
    CorrectionOutcome,
    ExerciseRef,
)
from exam_trainer.application.use_cases.mvp_coordinator import (
    ExamState,
    MVPTrainerCoordinator,
    PreflightResult,
    TrainingOptions,
)

MENU_WIDTH = 460
EXAM_STATUS_LABELS = {
    "completed": ("[✓] aprovada", "success"),
    "timeout": ("[✗] tempo esgotado", "fail"),
    "abandoned": ("[✗] abandonada", "fail"),
    "in_progress": ("[…] em andamento", "warning"),
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        workspace_path: Path,
        coordinator: MVPTrainerCoordinator,
        theme_manager: ThemeManager | None = None,
        task_runner: TaskRunner | None = None,
    ) -> None:
        super().__init__()
        self._workspace_path = workspace_path
        self._coordinator = coordinator
        self._tasks = task_runner or TaskRunner(self)
        self._active: ActiveExercise | None = None
        self._last_outcome: CorrectionOutcome | None = None
        self._training_options: TrainingOptions | None = None
        self._exam_state: ExamState | None = None
        self._mode = "training"
        self._training_kind = "level"
        self._pending_action: Callable[[], None] | None = None
        self._level_checks: list[ui.OptionButton] = []

        self._theme = theme_manager or ThemeManager(self._saved_theme_key())
        self._cursor = CursorController(self)

        self.setWindowTitle("Exam Trainer")
        self.setMinimumSize(760, 560)

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

        self._theme.apply(self)
        self._theme.theme_changed.connect(self._on_theme_changed)
        self._on_theme_changed(self._theme.tokens)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_exam)
        self._install_shortcuts()
        self._refresh_packs()
        self._show_resume_if_needed()
        self._refresh_home_status()
        self._cursor.enter_page(self._home_page)

    # ------------------------------------------------------------------ tema
    def _saved_theme_key(self) -> str | None:
        loader = getattr(self._coordinator, "theme_key", None)
        return loader() if callable(loader) else None

    def _on_theme_changed(self, tokens: ThemeTokens) -> None:
        self._cursor.configure(
            enabled=tokens.blink_cursor,
            animations=tokens.animations,
            cursor_char=tokens.cursor_char,
        )
        if self._stack.currentWidget() is self._history_page:
            self._show_history()

    def _change_theme(self, index: int) -> None:
        key = self._theme_combo.itemData(index)
        if not key:
            return
        self._theme.set_theme(str(key))
        saver = getattr(self._coordinator, "save_theme", None)
        if callable(saver):
            saver(str(key))

    # --------------------------------------------------------------- helpers
    def _go(self, page: QWidget) -> None:
        ui.fade_to(self._stack, page, animate=self._theme.tokens.animations)
        self._cursor.enter_page(page)

    def _button(self, text: str, handler, variant: str = "default") -> QPushButton:
        button = ui.button(text, handler, variant)
        if variant in ("menu", "start", "primary", "tab"):
            self._cursor.track(button)
        return button

    def _title(self, text: str) -> QLabel:
        label = ui.title_label()
        self._cursor.register_title(label, text)
        return label

    @staticmethod
    def _page(margins: int = 28, spacing: int = 12) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(margins, margins - 4, margins, 18)
        layout.setSpacing(spacing)
        return page, layout

    @staticmethod
    def _centered(widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(widget)
        row.addStretch(1)
        return row

    @staticmethod
    def _terminal_text() -> QTextEdit:
        text = QTextEdit()
        text.setReadOnly(True)
        text.setProperty("role", "terminal")
        text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        return text

    def _footer(self, back: Callable[[], None] | None, hints: list[tuple[str, str]], back_text: str = "[ VOLTAR ]") -> QVBoxLayout:
        footer = QVBoxLayout()
        footer.setSpacing(10)
        if back is not None:
            row = QHBoxLayout()
            back_button = self._button(back_text, back)
            back_button.setMinimumWidth(180)
            row.addWidget(back_button)
            row.addStretch(1)
            footer.addLayout(row)
        footer.addWidget(ui.HintBar(hints))
        return footer

    # ------------------------------------------------------------------ home
    def _build_home_page(self) -> QWidget:
        page, layout = self._page(margins=34)
        self._title_home = self._title("EXAM TRAINER")
        self._workspace_label = ui.label(self._workspace_prompt(), role="prompt", wrap=True)
        layout.addWidget(self._title_home)
        layout.addWidget(self._workspace_label)
        layout.addStretch(2)

        menu = QWidget()
        menu.setFixedWidth(MENU_WIDTH)
        menu_layout = QVBoxLayout(menu)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(10)
        self._menu_buttons: list[QPushButton] = []
        for index, (text, handler) in enumerate(
            (
                ("TREINAR", self._open_training_setup),
                ("MODO PROVA", self._open_exam_setup),
                ("HISTÓRICO", self._show_history),
                ("CONFIGURAÇÕES", lambda: self._show_settings()),
            ),
            start=1,
        ):
            button = self._button(f"> [{index}] {text}", handler, "menu")
            self._menu_buttons.append(button)
            menu_layout.addWidget(button)
        self._home_status = ui.label("", role="muted", wrap=True)
        self._home_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        menu_layout.addSpacing(10)
        menu_layout.addWidget(self._home_status)
        layout.addLayout(self._centered(menu))
        layout.addStretch(3)
        layout.addLayout(self._footer(None, [("1-4", "navegar"), ("Tab", "foco"), ("Enter", "abrir")]))
        return page

    # ---------------------------------------------------------------- treino
    def _build_training_page(self) -> QWidget:
        page, layout = self._page()
        layout.addWidget(self._title("TREINO"))

        tabs = QHBoxLayout()
        tabs.setSpacing(0)
        self._level_training_button = self._button("[1] TREINO POR LEVEL", self._choose_level_training, "tab")
        self._random_training_button = self._button("[2] TREINO ALEATÓRIO", self._choose_random_training, "tab")
        for tab in (self._level_training_button, self._random_training_button):
            tab.setCheckable(True)
            tabs.addWidget(tab)
        tabs.addStretch(1)
        layout.addLayout(tabs)

        self._training_options_panel = QWidget()
        options = QVBoxLayout(self._training_options_panel)
        options.setContentsMargins(6, 14, 6, 0)
        options.setSpacing(8)
        self._training_mode_label = ui.label("", role="headline")
        self._training_pack_combo = QComboBox()
        self._pack_combo = self._training_pack_combo
        self._training_pack_combo.currentIndexChanged.connect(self._refresh_levels)
        self._level_checks_layout = QVBoxLayout()
        self._level_checks_layout.setSpacing(2)

        self._random_options = QWidget()
        random_options = QVBoxLayout(self._random_options)
        random_options.setContentsMargins(0, 8, 0, 0)
        random_options.setSpacing(2)
        self._selection_group = QButtonGroup(self)
        self._selection_group.setExclusive(True)
        self._prioritize_radio = ui.OptionButton("Priorizar não concluídos", kind="radio", checked=True)
        self._only_uncompleted_radio = ui.OptionButton("Somente não concluídos", kind="radio")
        self._all_radio = ui.OptionButton("Todos os exercícios", kind="radio")
        for radio in (self._prioritize_radio, self._only_uncompleted_radio, self._all_radio):
            self._selection_group.addButton(radio)
        self._allow_repeated_check = ui.OptionButton("Permitir repetidos", kind="check")
        random_options.addWidget(ui.section_label("> SORTEIO"))
        for widget in (self._prioritize_radio, self._only_uncompleted_radio, self._all_radio):
            random_options.addWidget(widget)
        random_options.addSpacing(6)
        random_options.addWidget(self._allow_repeated_check)

        options.addWidget(self._training_mode_label)
        options.addWidget(ui.section_label("> RANK / PACK"))
        options.addWidget(self._training_pack_combo)
        options.addSpacing(6)
        options.addWidget(ui.section_label("> LEVELS"))
        options.addLayout(self._level_checks_layout)
        options.addWidget(self._random_options)
        options.addSpacing(18)
        self._start_training_button = self._button("> START TRAINING", self._start_training, "start")
        options.addLayout(self._centered(self._start_training_button))
        options.addStretch(1)
        self._cursor.set_idle_target(page, self._start_training_button)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._training_options_panel)
        layout.addWidget(scroll, 1)
        layout.addLayout(
            self._footer(self._show_home, [("1", "por level"), ("2", "aleatório"), ("Esc", "voltar")])
        )
        return page

    # ------------------------------------------------------------ modo prova
    def _build_exam_page(self) -> QWidget:
        page, layout = self._page()
        layout.addWidget(self._title("MODO PROVA"))

        self._exam_resume_card = ui.card(status="pending")
        resume = QVBoxLayout(self._exam_resume_card)
        resume.setContentsMargins(16, 12, 16, 14)
        resume.setSpacing(8)
        resume.addWidget(ui.label("● PROVA EM ANDAMENTO", status="pending"))
        self._exam_resume_label = ui.label("", wrap=True)
        resume.addWidget(self._exam_resume_label)
        resume_buttons = QHBoxLayout()
        self._resume_exam_button = self._button("> CONTINUAR PROVA", self._resume_exam, "primary")
        self._end_exam_button = self._button("[ ENCERRAR PROVA ]", self._end_exam, "danger")
        resume_buttons.addWidget(self._resume_exam_button, 2)
        resume_buttons.addWidget(self._end_exam_button, 1)
        resume.addLayout(resume_buttons)
        layout.addWidget(self._exam_resume_card)

        layout.addSpacing(8)
        layout.addWidget(ui.section_label("> NOVA PROVA — RANK / PACK"))
        self._exam_pack_combo = QComboBox()
        layout.addWidget(self._exam_pack_combo)
        prepare_row = QHBoxLayout()
        self._prepare_exam_button = self._button("> PREPARAR PROVA", self._show_exam_prepare, "primary")
        self._prepare_exam_button.setMinimumWidth(260)
        prepare_row.addWidget(self._prepare_exam_button)
        prepare_row.addStretch(1)
        layout.addSpacing(4)
        layout.addLayout(prepare_row)
        layout.addStretch(1)
        layout.addLayout(self._footer(self._show_home, [("Enter", "selecionar"), ("Esc", "voltar")]))
        return page

    def _build_exam_prepare_page(self) -> QWidget:
        page, layout = self._page()
        layout.addWidget(self._title("PREPARAR PROVA"))
        layout.addWidget(ui.label("exam.conf — less", role="panel-caption"))
        self._exam_prepare_text = self._terminal_text()
        layout.addWidget(self._exam_prepare_text, 1)
        layout.addSpacing(14)
        self._start_exam_button = self._button("> START EXAM", self._start_exam, "start")
        layout.addLayout(self._centered(self._start_exam_button))
        self._cursor.set_idle_target(page, self._start_exam_button)
        layout.addSpacing(10)
        layout.addLayout(self._footer(lambda: self._go(self._exam_page), [("Enter", "iniciar"), ("Esc", "voltar")]))
        return page

    # ------------------------------------------------------------- exercício
    def _build_exercise_page(self) -> QWidget:
        page, layout = self._page(margins=22, spacing=8)
        self._exercise_title = self._title("")
        layout.addWidget(self._exercise_title)

        meta = QHBoxLayout()
        meta.setSpacing(28)
        self._exercise_id_label = ui.label("", role="meta")
        self._exercise_rank_label = ui.label("")
        self._exercise_level_label = ui.label("")
        for widget in (self._exercise_id_label, self._exercise_rank_label, self._exercise_level_label):
            meta.addWidget(widget)
        meta.addStretch(1)
        self._exam_timer_label = ui.label("", role="timer")
        meta.addWidget(self._exam_timer_label)
        layout.addLayout(meta)
        # compat: label única com metadados (usada por quem inspeciona a tela)
        self._exercise_meta = self._exercise_id_label

        layout.addSpacing(4)
        layout.addWidget(ui.label("subject.md — less", role="panel-caption"))
        self._subject = ui.SubjectMarkdownView()
        self._subject.setMinimumHeight(240)
        layout.addWidget(self._subject, 1)

        self._feedback = ui.FeedbackBanner()
        layout.addWidget(self._feedback)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self._open_editor_button = self._button("[ ABRIR IDE ]", self._open_editor)
        self._correct_button = self._button("> CORRIGIR", self._submit_current, "primary")
        self._trace_button = self._button("[ VER TRACE ]", self._show_trace)
        self._next_button = self._button("[ PRÓXIMO/TROCAR ]", self._next_exercise)
        back_button = self._button("[ VOLTAR ]", self._back_from_exercise)
        buttons.addWidget(self._open_editor_button, 3)
        buttons.addWidget(self._correct_button, 3)
        buttons.addWidget(self._trace_button, 2)
        buttons.addWidget(self._next_button, 3)
        buttons.addWidget(back_button, 2)
        layout.addLayout(buttons)
        return page

    def _build_trace_page(self) -> QWidget:
        page, layout = self._page()
        layout.addWidget(self._title("TRACE"))
        layout.addWidget(ui.label("trace.log — less", role="panel-caption"))
        self._trace_text = self._terminal_text()
        layout.addWidget(self._trace_text, 1)
        row = QHBoxLayout()
        row.addWidget(self._button("[ SALVAR TRACE COMO... ]", self._save_trace_as))
        row.addStretch(1)
        layout.addLayout(row)
        layout.addLayout(
            self._footer(lambda: self._go(self._exercise_page), [("Esc", "voltar ao exercício")], "[ VOLTAR AO EXERCÍCIO ]")
        )
        return page

    # ------------------------------------------------------------- histórico
    def _build_history_page(self) -> QWidget:
        page, layout = self._page(spacing=8)
        layout.addWidget(self._title("HISTÓRICO"))
        layout.addSpacing(4)
        layout.addWidget(ui.section_label("═══ PROGRESSO POR EXERCÍCIO ═══"))
        self._history_summary = ui.label("")
        layout.addWidget(self._history_summary)
        counts = QHBoxLayout()
        counts.setSpacing(24)
        self._history_pass = ui.label("", status="pass")
        self._history_fail = ui.label("", status="fail")
        self._history_pending = ui.label("", status="pending")
        for widget in (self._history_pass, self._history_fail, self._history_pending):
            counts.addWidget(widget)
        counts.addStretch(1)
        layout.addLayout(counts)

        self._history_table = self._table(("LEVEL", "EXERCÍCIO", "STATUS", "TENTATIVAS", "ÚLTIMO RESULTADO", "DATA"), stretch=5)
        layout.addWidget(self._history_table, 3)

        layout.addSpacing(6)
        layout.addWidget(ui.section_label("═══ HISTÓRICO DE PROVA ═══"))
        self._exam_history_table = self._table(("DATA", "RANK", "STATUS", "NOTA", "DURAÇÃO", "EXERCÍCIOS"), stretch=5)
        self._exam_history_empty = ui.label("Nenhuma prova realizada ainda.", role="muted")
        layout.addWidget(self._exam_history_empty)
        layout.addWidget(self._exam_history_table, 2)
        layout.addLayout(self._footer(self._show_home, [("Esc", "voltar")]))
        return page

    @staticmethod
    def _table(headers: tuple[str, ...], stretch: int) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(30)
        header = table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setHighlightSections(False)
        for column in range(len(headers)):
            mode = QHeaderView.ResizeMode.Stretch if column == stretch else QHeaderView.ResizeMode.ResizeToContents
            header.setSectionResizeMode(column, mode)
        return table

    # --------------------------------------------------------- configurações
    def _build_settings_page(self) -> QWidget:
        page, layout = self._page(spacing=10)
        self._settings_title = self._title("CONFIGURAÇÕES")
        layout.addWidget(self._settings_title)

        content = QWidget()
        sections = QVBoxLayout(content)
        sections.setContentsMargins(0, 4, 8, 4)
        sections.setSpacing(14)

        # tema
        self._theme_combo = QComboBox()
        for tokens in self._theme.available():
            self._theme_combo.addItem(tokens.name, tokens.key)
        self._theme_combo.setCurrentIndex(max(0, self._theme_combo.findData(self._theme.tokens.key)))
        self._theme_combo.currentIndexChanged.connect(self._change_theme)
        sections.addWidget(self._settings_card("TEMA", [self._theme_combo], []))

        # workspace
        self._settings_workspace = ui.label("", wrap=True)
        sections.addWidget(
            self._settings_card("WORKSPACE", [self._settings_workspace], [("[ ALTERAR WORKSPACE ]", self._change_workspace)])
        )

        # editor
        self._editor_combo = QComboBox()
        self._editor_combo.addItems(("VS Code", "Zed", "Cursor", "Outro..."))
        self._editor_combo.currentTextChanged.connect(self._editor_preset_changed)
        self._settings_editor = QLineEdit()
        sections.addWidget(
            self._settings_card(
                "EDITOR/IDE",
                [self._editor_combo, self._settings_editor],
                [("[ SELECIONAR EXECUTÁVEL ]", self._browse_editor), ("[ SALVAR EDITOR ]", self._save_editor_setting)],
            )
        )

        # runtimes
        self._runtime_labels: dict[str, QLabel] = {}
        self._settings_compiler: QLabel | None = None  # compatibilidade dos testes antigos
        for status in self._coordinator.runtime_statuses():
            language = status.language
            label = ui.label("", wrap=True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._runtime_labels[language] = label
            if self._settings_compiler is None:
                self._settings_compiler = label
            sections.addWidget(
                self._settings_card(
                    status.display_name.upper(),
                    [label],
                    [
                        ("[ DETECTAR NOVAMENTE ]", lambda lang=language: self._redetect_runtime(lang)),
                        (f"[ SELECIONAR {status.display_name.upper()} ]", lambda lang=language: self._choose_manual_runtime(lang)),
                    ],
                )
            )

        # packs
        self._packs_summary = ui.label("", wrap=True)
        sections.addWidget(
            self._settings_card(
                "PACKS",
                [self._packs_summary],
                [
                    ("[ IMPORTAR PACK ]", self._import_pack),
                    ("[ ATUALIZAR PACKS ]", self._refresh_packs),
                    ("[ COMO CRIAR UM PACK ]", self._show_pack_help),
                ],
            )
        )
        sections.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        layout.addLayout(self._footer(self._show_home, [("Esc", "voltar")]))
        return page

    def _settings_card(self, title: str, body: list[QWidget], actions: list[tuple[str, Callable[[], None]]]) -> QFrame:
        frame = ui.card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(8)
        layout.addWidget(ui.section_label(title))
        for widget in body:
            layout.addWidget(widget)
        if actions:
            row = QHBoxLayout()
            row.setSpacing(8)
            for text, handler in actions:
                row.addWidget(self._button(text, handler))
            row.addStretch(1)
            layout.addLayout(row)
        return frame

    def _build_pack_help_page(self) -> QWidget:
        page, layout = self._page()
        layout.addWidget(self._title("COMO CRIAR UM PACK"))
        layout.addWidget(ui.label("PACKS.md — less", role="panel-caption"))
        self._pack_help_text = self._terminal_text()
        self._pack_help_text.setPlainText(self._pack_help_content())
        layout.addWidget(self._pack_help_text, 1)
        row = QHBoxLayout()
        row.addWidget(self._button("[ ABRIR DOCUMENTAÇÃO COMPLETA ]", self._open_full_documentation))
        row.addStretch(1)
        layout.addLayout(row)
        layout.addLayout(
            self._footer(lambda: self._show_settings("Packs"), [("Esc", "voltar")], "[ VOLTAR PARA CONFIGURAÇÕES ]")
        )
        return page

    # ------------------------------------------------------------- teclado
    def _install_shortcuts(self) -> None:
        for index, button in enumerate(self._menu_buttons, start=1):
            QShortcut(QKeySequence(str(index)), self._home_page).activated.connect(button.click)
        QShortcut(QKeySequence("1"), self._training_page).activated.connect(self._choose_level_training)
        QShortcut(QKeySequence("2"), self._training_page).activated.connect(self._choose_random_training)
        back_targets: dict[QWidget, Callable[[], None]] = {
            self._training_page: self._show_home,
            self._exam_page: self._show_home,
            self._history_page: self._show_home,
            self._settings_page: self._show_home,
            self._exam_prepare_page: lambda: self._go(self._exam_page),
            self._trace_page: lambda: self._go(self._exercise_page),
            self._pack_help_page: lambda: self._show_settings("Packs"),
        }
        for page, action in back_targets.items():
            QShortcut(QKeySequence(Qt.Key.Key_Escape), page).activated.connect(action)

    def _workspace_prompt(self) -> str:
        name = self._workspace_path.name or str(self._workspace_path)
        parent = self._workspace_path.parent.name
        compact = f"~/{parent}/{name}" if parent else f"~/{name}"
        if len(compact) > 54:
            compact = f"~/.../{name}"
        return f"user@42:{compact}$"

    def _set_title_label(self, label: QLabel, text: str) -> None:
        self._cursor.set_title(label, text)

    # ------------------------------------------------------------- navegação
    def _show_home(self) -> None:
        self._show_resume_if_needed()
        self._refresh_home_status()
        self._go(self._home_page)

    def _refresh_home_status(self) -> None:
        packs = len(self._coordinator.list_packs())
        ready = sum(1 for status in self._coordinator.runtime_statuses() if status.tool)
        total = len(self._coordinator.runtime_statuses())
        runtimes = f"{ready}/{total} verificados" if total else "0 registrados"
        exam = "   ·   prova em andamento" if self._coordinator.load_active_exam() is not None else ""
        self._home_status.setText(f"packs: {packs}   ·   runtimes: {runtimes}{exam}")

    def _open_training_setup(self) -> None:
        if not self._handle_preflight(self._coordinator.preflight_training(), self._open_training_setup):
            return
        if not (self._level_training_button.isChecked() or self._random_training_button.isChecked()):
            self._choose_level_training()
        self._go(self._training_page)

    def _open_exam_setup(self) -> None:
        if not self._exam_preflight_checked(self._open_exam_setup):
            return
        self._show_resume_if_needed()
        self._go(self._exam_page)

    # ------------------------------------------------ tarefas em segundo plano
    def _run_task(
        self,
        key: str,
        work: Callable[[], object],
        on_done: Callable[[object], None],
        title: str,
        on_finally: Callable[[], None] | None = None,
    ) -> bool:
        """Roda `work` fora da thread da UI. Erros viram mensagem, nunca traceback."""

        def done(result: object) -> None:
            if on_finally is not None:
                on_finally()
            on_done(result)

        def failed(error: BaseException) -> None:
            if on_finally is not None:
                on_finally()
            QMessageBox.warning(self, title, str(error) or error.__class__.__name__)

        return self._tasks.start(key, work, done, failed)

    def _runtime_checked(self, language: str, then: Callable[[], None]) -> bool:
        """True se o runtime da linguagem já foi validado. Senão valida em segundo plano e chama `then`.

        A detecção roda processos externos (probe do compilador/interpretador) e pode demorar.
        Se falhar, o preflight mostra a mensagem e leva às Configurações.
        """
        if self._coordinator.runtime_ready(language):
            return True
        if self._tasks.is_busy("runtime"):
            return False
        self._home_status.setText("verificando ambiente de execução...")
        self._run_task(
            "runtime",
            lambda: self._coordinator.preflight_runtime(language),
            lambda preflight: then() if preflight.ok else self._handle_preflight(preflight, then),
            "Ambiente de execução",
            on_finally=self._refresh_home_status,
        )
        return False

    def _exam_preflight_checked(self, then: Callable[[], None]) -> bool:
        pack_id = self._selected_exam_pack_id()
        if self._coordinator.pack_runtimes_ready(pack_id):
            preflight = self._coordinator.preflight_exam(pack_id)
            return self._handle_preflight(preflight, then)
        if self._tasks.is_busy("runtime"):
            return False
        self._home_status.setText("verificando ambientes de execução...")
        self._run_task(
            "runtime",
            lambda: self._coordinator.preflight_exam(pack_id),
            lambda preflight: then() if preflight.ok else self._handle_preflight(preflight, then),
            "Ambiente de execução",
            on_finally=self._refresh_home_status,
        )
        return False

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
        self._training_mode_label.setText("Treino por Level — escolha os levels e comece.")
        self._random_options.setVisible(False)
        self._training_options_panel.setVisible(True)
        self._level_training_button.setChecked(True)
        self._random_training_button.setChecked(False)

    def _choose_random_training(self) -> None:
        self._training_kind = "random"
        self._training_mode_label.setText("Treino Aleatório — sorteia exercícios dos levels marcados.")
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
                f"● {pack.name}   id={pack.id}   v{pack.version}   levels={len(pack.levels)}"
                for pack in packs
            )
            or "○ nenhum pack instalado"
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
            check = ui.OptionButton(level, kind="check", checked=True)
            self._cursor.track(check)
            self._level_checks.append(check)
            self._level_checks_layout.addWidget(check)

    def _selected_training_pack_id(self) -> str | None:
        value = self._training_pack_combo.currentData()
        return None if value is None else str(value)

    def _selected_exam_pack_id(self) -> str | None:
        value = self._exam_pack_combo.currentData()
        return None if value is None else str(value)

    def _selected_levels(self) -> tuple[str, ...]:
        return tuple(check.value for check in self._level_checks if check.isChecked())

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

    # ------------------------------------------------------------- exercício
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
        self._exercise_id_label.setText(f"ID: {active.ref.definition.id}")
        self._exercise_rank_label.setText(f"RANK: {active.ref.pack.name}")
        self._exercise_level_label.setText(f"LEVEL: {active.ref.level_id}")
        self._exam_timer_label.setVisible(mode == "exam")
        if mode == "exam" and self._exam_state is not None:
            self._render_exam_timer(self._exam_state)
        self._subject.set_subject_markdown(active.subject_text)
        self._feedback.clear()
        self._open_editor_button.setToolTip(f"Abrir a pasta do exercício no {self._coordinator.editor_display_name()}")
        self._trace_button.setEnabled(False)
        self._next_button.setVisible(mode == "training")
        self._next_button.setEnabled(mode == "training")
        self._go(self._exercise_page)

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
        if self._active is None or self._tasks.is_busy("submit"):
            return
        if not self._runtime_checked(self._active.ref.definition.language, self._submit_current):
            return
        active = self._active
        if self._mode == "exam":
            if self._exam_state is None:
                return
            self._tick_exam()
            if self._exam_state is None:  # o tempo acabou antes de enviar
                return
            state = self._exam_state
            work = lambda: self._coordinator.submit_exam(state, active)  # noqa: E731
            on_done = lambda result: self._on_exam_graded(active, result)  # noqa: E731
        else:
            work = lambda: self._coordinator.submit_training(active)  # noqa: E731
            on_done = lambda outcome: self._on_training_graded(active, outcome)  # noqa: E731
        self._set_grading(True)
        self._run_task("submit", work, on_done, "Correção", on_finally=lambda: self._set_grading(False))

    def _set_grading(self, busy: bool) -> None:
        self._correct_button.setEnabled(not busy)
        self._cursor.set_button_text(self._correct_button, "CORRIGINDO..." if busy else "> CORRIGIR")
        self._next_button.setEnabled(not busy and self._mode == "training")

    def _on_training_graded(self, active: ActiveExercise, outcome: CorrectionOutcome) -> None:
        if self._active is not active:
            return  # o usuário saiu do exercício; a tentativa já foi salva
        self._last_outcome = outcome
        self._trace_button.setEnabled(True)
        if outcome.result.passed:
            self._show_training_pass_feedback()
        else:
            self._show_training_fail_feedback()

    def _on_exam_graded(self, active: ActiveExercise, result: tuple[CorrectionOutcome, ExamState | None]) -> None:
        outcome, next_state = result
        self._last_outcome = outcome
        self._trace_button.setEnabled(True)
        if next_state is None:
            self._timer.stop()
            self._exam_state = None
            self._show_pass_feedback("PROVA CONCLUÍDA — nota 100%.")
            self._show_resume_if_needed()
            return
        self._exam_state = next_state
        # Se o prazo venceu enquanto corrigia, encerra agora (com a nota já atualizada).
        self._tick_exam()
        if self._exam_state is None:
            return
        if outcome.result.passed:
            try:
                self._load_exercise(self._coordinator.exam_ref(next_state), mode="exam")
            except Exception as error:
                QMessageBox.warning(self, "Prova", str(error))
                return
            self._show_pass_feedback("Exercício anterior concluído. Próximo exercício carregado.")
            return
        if self._active is active:
            self._show_fail_feedback("Você continua neste exercício. Corrija e envie de novo.")

    def _show_training_fail_feedback(self) -> None:
        self._show_fail_feedback("Veja o trace técnico, ajuste no editor e corrija de novo.")

    def _show_training_pass_feedback(self) -> None:
        self._show_pass_feedback("EXERCÍCIO CONCLUÍDO.", with_next=True)

    def _show_fail_feedback(self, message: str) -> None:
        editor = self._coordinator.editor_display_name()
        actions = [
            ui.button("[ VER TRACE ]", self._show_trace, "small"),
            ui.button(f"[ ABRIR NO {editor.upper()} ]", self._open_editor, "small"),
            ui.button("[ VOLTAR PARA CORRIGIR ]", self._feedback.clear, "small"),
        ]
        self._feedback.show_result("fail", "[✗] FAIL", message, actions, animate=self._theme.tokens.animations)

    def _show_pass_feedback(self, message: str, with_next: bool = False) -> None:
        actions: list[QPushButton] = []
        if with_next and self._mode == "training":
            actions.append(ui.button("[ PRÓXIMO EXERCÍCIO ]", self._next_exercise, "small"))
        self._feedback.show_result("pass", "[✓] PASS", message, actions, animate=self._theme.tokens.animations)

    def _show_trace(self) -> None:
        if self._last_outcome is None:
            return
        self._trace_text.setPlainText(self._last_outcome.result.trace_data.as_text())
        self._go(self._trace_page)

    def _save_trace_as(self) -> None:
        if self._last_outcome is None:
            return
        target, _ = QFileDialog.getSaveFileName(self, "Salvar trace", "trace.txt")
        if target:
            Path(target).write_text(self._last_outcome.result.trace_data.as_text(), encoding="utf-8")

    def _next_exercise(self) -> None:
        if self._training_options is None or self._mode != "training":
            return
        try:
            self._load_exercise(self._coordinator.choose_training_exercise(self._training_options), mode="training")
        except Exception as error:
            QMessageBox.warning(self, "Treino", str(error))

    # ------------------------------------------------------------------ prova
    def _start_exam(self) -> None:
        if not self._exam_preflight_checked(self._start_exam):
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
        if not self._exam_preflight_checked(self._show_exam_prepare):
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
        lines = [
            f"Pack/Rank : {pack.name}",
            f"ID        : {pack.id}",
            f"Levels    : {len(levels)}",
            "",
            "Estrutura da prova baseada no pack real:",
            *(f"  {index}. {level}" for index, level in enumerate(levels, start=1)),
            "",
            f"Duração   : {self._format_seconds(self._coordinator.exam_duration_seconds(pack_id))}"
            + ("" if pack.exam_duration_seconds else "  (padrão; o pack não declara exam.duration_minutes)"),
            "Aprovação : 100%",
            "",
            "Regras:",
            "- ao errar, permanece no mesmo exercício;",
            "- ao passar, avança automaticamente;",
            "- não é permitido trocar exercício;",
            "- o relógio NÃO pausa: fechar o app não para o tempo;",
            "- se o tempo acabar, a prova encerra e salva nota parcial;",
            "- se fechar no meio, a sessão pode ser retomada enquanto houver tempo.",
        ]
        self._exam_prepare_text.setPlainText("\n".join(lines))
        self._go(self._exam_prepare_page)

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
        if self._tasks.is_busy("submit"):
            # Não encerra a prova no meio de uma correção: o timer continua
            # desenhando e o encerramento acontece quando a correção volta.
            remaining = self._coordinator.remaining_seconds(self._exam_state)
            self._render_exam_timer(replace(self._exam_state, remaining_seconds=remaining))
            return
        state = self._coordinator.tick_exam(self._exam_state)
        if state is None:
            self._timer.stop()
            self._exam_state = None
            self._exam_timer_label.setText("TEMPO ESGOTADO")
            ui.set_status(self._exam_timer_label, "fail")
            QMessageBox.information(self, "Prova", "Tempo esgotado. Prova encerrada.")
            return
        self._exam_state = state
        self._render_exam_timer(state)

    def _render_exam_timer(self, state: ExamState) -> None:
        self._exam_timer_label.setText(f"⏱ {self._format_seconds(state.remaining_seconds)}   NOTA {state.score:.0f}%")

    @staticmethod
    def _format_seconds(total: int) -> str:
        minutes, seconds = divmod(max(0, int(total)), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _show_resume_if_needed(self) -> None:
        state = self._coordinator.load_active_exam()
        expired = self._coordinator.pop_expired_exam()
        if expired is not None:
            self._timer.stop()
            self._exam_state = None
            QMessageBox.information(
                self,
                "Prova",
                "O tempo da prova terminou enquanto o app estava fechado.\n"
                f"A prova foi encerrada com nota parcial de {expired.score:.0f}%.",
            )
        has_state = state is not None
        self._exam_resume_card.setVisible(has_state)
        self._resume_exam_button.setVisible(has_state)
        self._end_exam_button.setVisible(has_state)
        if state is None:
            self._exam_resume_label.setText("")
            return
        self._exam_resume_label.setText(
            f"Rank      : {state.pack_id}\n"
            f"Exercício : {state.exercise_id}\n"
            f"Restante  : {self._format_seconds(state.remaining_seconds)}"
        )

    # -------------------------------------------------------------- histórico
    def _show_history(self) -> None:
        rows = self._coordinator.exercise_history_rows()
        completed = sum(1 for row in rows if row["status"] == "concluído")
        attempted = sum(1 for row in rows if row["status"] == "tentado")
        pending = max(0, len(rows) - completed - attempted)
        bar_width = 20
        filled = 0 if not rows else round((completed / len(rows)) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        self._history_summary.setText(f"[{bar}] {completed}/{len(rows)} concluídos")
        self._history_pass.setText(f"PASS: {completed}")
        self._history_fail.setText(f"FAIL: {attempted}")
        self._history_pending.setText(f"PENDENTES: {pending}")
        self._populate_history_table(rows)
        self._populate_exam_history()
        if self._stack.currentWidget() is not self._history_page:
            self._go(self._history_page)

    def _item(self, text: str, color: str | None = None, align_right: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if color:
            item.setForeground(self._theme.color(color))
        alignment = Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignRight if align_right else Qt.AlignmentFlag.AlignLeft)
        item.setTextAlignment(alignment)
        return item

    def _populate_history_table(self, rows: list[dict[str, object]]) -> None:
        self._history_table.setRowCount(len(rows))
        # Agrupa por (pack, level): o mesmo id de level/exercício pode existir em packs diferentes.
        multi_pack = len({str(row.get("pack_id", row["pack"])) for row in rows}) > 1

        def group_of(row: dict[str, object]) -> str:
            level = str(row["level"])
            if not multi_pack:
                return level
            return str(row["pack"]) if level == "-" else f"{row.get('pack_id', row['pack'])}/{level}"

        sorted_rows = sorted(rows, key=lambda row: (group_of(row), str(row["exercise_id"])))
        totals: dict[str, int] = {}
        for row in sorted_rows:
            totals[group_of(row)] = totals.get(group_of(row), 0) + 1
        seen: dict[str, int] = {}
        for row_index, row in enumerate(sorted_rows):
            level = group_of(row)
            seen[level] = seen.get(level, 0) + 1
            branch = "└──" if seen[level] == totals[level] else "├──"
            status = str(row["status"])
            latest = str(row["latest_result"])
            attempts = int(row["attempts"])
            if status == "concluído":
                marker, status_color = "[✓]", "success"
            elif status == "tentado" and latest == "FAIL":
                marker, status_color = "[✗]", "fail"
            elif status == "tentado":
                marker, status_color = "[…]", "warning"
            else:
                marker, status_color = "[ ]", "text_secondary"
            latest_color = {"PASS": "success", "FAIL": "fail"}.get(latest, "text_secondary")
            cells = (
                self._item(f"{level}/" if seen[level] == 1 else "", "text_secondary"),
                self._item(f"{branch} {row['exercise_id']}"),
                self._item(f"{marker} {status}", status_color),
                self._item(str(attempts), None if attempts else "text_secondary", align_right=True),
                self._item(latest, latest_color),
                self._item(self._format_date(row["last_attempt_at"]), "text_secondary"),
            )
            for column, item in enumerate(cells):
                self._history_table.setItem(row_index, column, item)

    def _populate_exam_history(self) -> None:
        exam_rows = self._coordinator.exam_history_rows()
        self._exam_history_empty.setVisible(not exam_rows)
        self._exam_history_table.setVisible(bool(exam_rows))
        self._exam_history_table.setRowCount(len(exam_rows))
        for row_index, row in enumerate(exam_rows):
            raw_status = str(row.get("status") or "-")
            status, status_color = EXAM_STATUS_LABELS.get(raw_status, (raw_status, "text_secondary"))
            score = row.get("final_score")
            try:
                score_text = f"{float(score):.0f}%"
            except (TypeError, ValueError):
                score_text = "-"
            try:
                duration = self._format_seconds(int(row.get("used_seconds") or 0))
            except (TypeError, ValueError):
                duration = "-"
            cells = (
                self._item(self._format_date(row.get("finished_at")), "text_secondary"),
                self._item(str(row.get("rank") or "-")),
                self._item(status, status_color),
                self._item(score_text, align_right=True),
                self._item(duration, align_right=True),
                self._item(str(row.get("exercises") or "-"), "text_secondary"),
            )
            for column, item in enumerate(cells):
                self._exam_history_table.setItem(row_index, column, item)

    @staticmethod
    def _format_date(value: object) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return str(value)[:16]

    # ---------------------------------------------------------- configurações
    def _import_pack(self) -> None:
        if self._tasks.is_busy("import"):
            return
        source, _ = QFileDialog.getOpenFileName(self, "Selecionar pack ZIP", "", "Pack ZIP (*.zip);;Todos os arquivos (*)")
        if not source:
            source = QFileDialog.getExistingDirectory(self, "Selecionar pasta do pack")
        if not source:
            return
        path = Path(source)
        self._packs_summary.setText("validando pack...")
        self._run_task(
            "import",
            lambda: self._coordinator.inspect_pack(path),
            lambda report: self._confirm_pack_import(path, report),
            "Importar Pack",
            on_finally=self._refresh_packs,
        )

    def _confirm_pack_import(self, path: Path, report) -> None:
        if report.has_executable_code:
            listed = "\n".join(f"  - {name}" for name in report.executable_files[:8])
            more = "" if len(report.executable_files) <= 8 else f"\n  ... e mais {len(report.executable_files) - 8}"
            answer = QMessageBox.warning(
                self,
                "Importar Pack",
                f"O pack \"{report.pack.name}\" contém código que será compilado e EXECUTADO "
                "no seu computador durante a correção (fixtures/references):\n\n"
                f"{listed}{more}\n\n"
                "Não há sandbox: esse código roda com as permissões do seu usuário. "
                "Importe apenas packs de fontes em que você confia.\n\nImportar mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._packs_summary.setText("importando pack...")
        self._run_task(
            "import",
            lambda: self._coordinator.import_pack(path),
            self._on_pack_imported,
            "Importar Pack",
            on_finally=self._refresh_packs,
        )

    def _on_pack_imported(self, pack) -> None:
        QMessageBox.information(self, "Importar Pack", f"Pack importado: {pack.name}")
        self._resume_pending_if_ready()

    def _show_settings(self, section: str | None = None) -> None:
        self._set_title_label(self._settings_title, "CONFIGURAÇÕES" if section is None else f"CONFIGURAÇÕES > {section.upper()}")
        self._settings_workspace.setText(str(self._coordinator.workspace_root))
        self._settings_editor.setText(self._coordinator.editor_command())
        for language in self._runtime_labels:
            self._show_runtime_cached(language)
        self._go(self._settings_page)

    def _show_pack_help(self) -> None:
        self._pack_help_text.setPlainText(self._pack_help_content())
        self._go(self._pack_help_page)

    def _open_full_documentation(self) -> None:
        document = self._documentation_path()
        if document is None:
            QMessageBox.warning(self, "Documentação", "Documentação não encontrada nesta instalação.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(document)))

    @staticmethod
    def _documentation_path() -> Path | None:
        """README do checkout ou o empacotado no executável; senão o contrato de pack."""
        candidates = []
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle:
            candidates.append(Path(bundle) / "README.md")
        candidates.append(Path(__file__).resolve().parents[5] / "README.md")
        try:
            candidates.append(resource_path(PACK_CONTRACT))
        except (OSError, TypeError, ValueError):
            pass
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _pack_help_content() -> str:
        """Contrato de pack (fonte única: resources/pack-contract.md) + capabilities ativas."""
        capabilities = default_exercise_capabilities()
        executions = ", ".join(sorted(capabilities.executions.supported))
        generators = ", ".join(sorted(capabilities.generators.supported))
        expectations = ", ".join(sorted(capabilities.expectations.supported))
        languages = ", ".join(sorted(capabilities.languages))
        active = (
            "Capabilities deste app\n"
            f"  linguagens   : {languages}\n"
            f"  execution    : {executions}\n"
            f"  generators   : {generators}\n"
            f"  expectations : {expectations}\n\n"
        )
        try:
            contract = pack_contract_text()
        except OSError:
            contract = "Documentação do contrato não encontrada nesta instalação."
        return active + contract

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
            QMessageBox.information(self, "Editor", "Editor atualizado.")
            self._resume_pending_if_ready()
        except Exception as error:
            QMessageBox.warning(self, "Editor", str(error))

    def _refresh_compiler_setting(self) -> None:
        language = self._first_runtime_language()
        if language is not None:
            self._redetect_runtime(language)

    def _show_compiler_result(self, compiler: object) -> None:
        language = self._first_runtime_language()
        if language is not None:
            self._show_runtime_result(language, compiler)

    def _show_compiler_cached(self) -> None:
        language = self._first_runtime_language()
        if language is not None:
            self._show_runtime_cached(language)

    def _show_runtime_result(self, language: str, tool: object, cached: bool = False) -> None:
        label = self._runtime_labels[language]
        if tool:
            label.setText(f"● {'' if cached else 'OK   '}{tool}")
            ui.set_status(label, "pass")
        elif cached:
            label.setText("● não verificado — use [ DETECTAR NOVAMENTE ]")
            ui.set_status(label, "pending")
        else:
            label.setText("● não encontrado — selecione o executável manualmente")
            ui.set_status(label, "fail")

    def _show_runtime_cached(self, language: str) -> None:
        self._show_runtime_result(language, self._coordinator.runtime_current_tool(language), cached=True)

    def _redetect_runtime(self, language: str) -> None:
        label = self._runtime_labels[language]
        label.setText("● detectando...")
        ui.set_status(label, "pending")
        self._run_task(
            "runtime",
            lambda: self._coordinator.redetect_runtime(language),
            lambda tool: self._show_runtime_result(language, tool),
            self._coordinator.runtime_display_name(language),
        )

    def _choose_manual_runtime(self, language: str) -> None:
        display_name = self._coordinator.runtime_display_name(language)
        filter_text = "Executáveis (*.exe);;Todos os arquivos (*)" if sys.platform == "win32" else "Todos os arquivos (*)"
        selected, _ = QFileDialog.getOpenFileName(self, f"Selecionar {display_name}", "", filter_text)
        if not selected:
            return
        path = Path(selected)
        self._runtime_labels[language].setText("● validando...")

        def done(tool: object) -> None:
            self._show_runtime_result(language, self._coordinator.runtime_current_tool(language))
            QMessageBox.information(self, display_name, f"{display_name} atualizado.")
            self._resume_pending_if_ready()

        self._run_task(
            "runtime",
            lambda: self._coordinator.save_manual_runtime(language, path),
            done,
            display_name,
            on_finally=lambda: self._show_runtime_cached(language),
        )

    def _editor_preset_changed(self, label: str) -> None:
        if label == "Outro...":
            self._browse_editor()
            return
        resolved = self._coordinator.resolve_known_editor(label)
        if resolved is not None:
            self._settings_editor.setText(resolved)

    def _browse_editor(self) -> None:
        filter_text = "Executáveis (*.exe);;Todos os arquivos (*)" if sys.platform == "win32" else "Todos os arquivos (*)"
        selected, _ = QFileDialog.getOpenFileName(self, "Selecionar executável do editor", "", filter_text)
        if selected:
            self._settings_editor.setText(str(Path(selected)))

    def _choose_manual_compiler(self) -> None:
        language = self._first_runtime_language()
        if language is not None:
            self._choose_manual_runtime(language)

    def _first_runtime_language(self) -> str | None:
        return next(iter(self._runtime_labels), None)

    def closeEvent(self, event) -> None:  # noqa: N802 — API do Qt
        # Deixa uma correção/importação em andamento terminar de gravar antes de fechar.
        self._tasks.wait(15_000)
        super().closeEvent(event)

    def _back_from_exercise(self) -> None:
        self._go(self._exam_page if self._mode == "exam" else self._training_page)

