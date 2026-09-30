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
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
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
from exam_trainer.adapters.ui.qt.i18n import LOCALE_LABELS, LocaleService, SUPPORTED_UI_LOCALES, tr
from exam_trainer.adapters.ui.qt.task_runner import TaskRunner
from exam_trainer.adapters.ui.qt.theme import ThemeManager, ThemeTokens
from exam_trainer.application.capabilities import default_exercise_capabilities
from exam_trainer.application.history_service import HistoryQuery
from exam_trainer.application.study_intent import StudyIntent
from exam_trainer.application.engine.activity_preflight import ActivityPreflightStatus
from exam_trainer.resources import PACK_CONTRACT, pack_contract_text, resource_path
from exam_trainer.application.mvp_models import (
    ActiveExercise,
    ActivityProgress,
    CorrectionOutcome,
    ExerciseRef,
    GradingOutcome,
)
from exam_trainer.application.use_cases.mvp_coordinator import (
    ExamState,
    MVPTrainerCoordinator,
    PreflightResult,
    TrainingOptions,
)

MENU_WIDTH = 460
ACTIVITY_PROGRESS_LABELS: dict[ActivityProgress, str] = {
    ActivityProgress.COMPLETED: "Concluído",
    ActivityProgress.ATTEMPTED: "Tentado",
    ActivityProgress.NOT_STARTED: "Não feito",
}
EXAM_STATUS_KEYS = {
    "completed": ("completed_exam", "success"),
    "timeout": ("timeout_exam", "fail"),
    "abandoned": ("abandoned_exam", "fail"),
    "in_progress": ("in_progress_exam", "warning"),
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        workspace_path: Path,
        coordinator: MVPTrainerCoordinator,
        theme_manager: ThemeManager | None = None,
        locale_service: LocaleService | None = None,
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
        self._editor_targets: dict[tuple[str, str], Path] = {}
        self._level_checks: list[ui.OptionButton] = []
        self._footer_buttons: list[tuple[QPushButton, str]] = []

        self._theme = theme_manager or ThemeManager(self._saved_theme_key())
        self._locale = locale_service or LocaleService(coordinator)
        self._locale.locale_changed.connect(self._on_locale_changed)
        self._cursor = CursorController(self)

        self.setWindowTitle("RankedDojo")
        self.setMinimumSize(760, 560)

        self._stack = QStackedWidget()
        self._home_page = self._build_home_page()
        self._study_page = self._build_study_page()
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
            self._study_page,
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
        self._refresh_study_languages()
        self._retranslate_static_ui()
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

    # --------------------------------------------------------------- i18n
    def _t(self, text: str, **values: object) -> str:
        translated = self._locale.translate(text)
        return translated.format(**values) if values else translated

    def _action(self, text: str, style: str = "bracket", **values: object) -> str:
        translated = self._t(text, **values).upper()
        if style == "primary":
            return f"> {translated}"
        if style == "indexed":
            return translated
        return f"[ {translated} ]"

    def _set_button(self, button: QPushButton, text: str) -> None:
        self._cursor.set_button_text(button, text)

    def _on_locale_changed(self, _locale: str) -> None:
        self._retranslate_static_ui()
        self._refresh_home_status()
        self._refresh_study_languages()
        self._refresh_packs()
        self._refresh_levels()
        if self._active is not None:
            self._refresh_exercise_frame()
            if self._exam_state is not None:
                self._render_exam_timer(self._exam_state)
        if self._stack.currentWidget() is self._history_page:
            self._show_history()
        elif self._stack.currentWidget() is self._settings_page:
            self._show_settings()
        elif self._stack.currentWidget() is self._exam_prepare_page:
            self._show_exam_prepare()

    def _set_locale_from_combo(self, index: int) -> None:
        locale = self._locale_combo.itemData(index)
        if isinstance(locale, str):
            self._locale.set_locale(locale)

    def _retranslate_static_ui(self) -> None:
        self._set_title_label(self._title_home, "RankedDojo")
        menu_labels = (
            self._t("Quero estudar algo novo"),
            self._t("Treinar"),
            self._t("Modo prova"),
            self._t("Histórico"),
            self._t("Configurações"),
        )
        for index, (button, label) in enumerate(zip(self._menu_buttons, menu_labels, strict=True), start=1):
            self._set_button(button, f"> [{index}] {label.upper()}")

        self._set_title_label(self._study_title, self._t("Quero estudar algo novo título"))
        self._study_description.setText(self._t("Descreva o que quer estudar, gere um prompt compatível e importe o pack resultante."))
        self._study_topic.setPlaceholderText(self._t("Ex.: ponteiros e strings, OOP em Python, arrays em Java..."))
        self._study_section_label.setText(f"> {self._t('O que você quer estudar?').upper()}")
        for label, text in self._study_field_labels:
            label.setText(self._t(text))
        self._reset_combo_items(self._study_level_combo, ("Básico", "Intermediário", "Avançado"))
        self._reset_combo_items(self._study_goal_combo, ("Aprender", "Praticar", "Revisar", "Validar conhecimento"))
        self._reset_combo_items(self._study_format_combo, ("Exercícios", "Projeto", "Misto", "Revisão", "Simulado"))
        self._reset_combo_items(self._study_content_language_combo, ("Português (pt-BR)", "Inglês (en)"), ("pt-BR", "en"))
        self._reset_combo_items(self._study_size_combo, ("Curto", "Médio", "Completo"))
        self._set_button(self._generate_prompt_button, self._action("Gerar prompt", "primary"))
        self._set_button(self._copy_prompt_button, self._action("Copiar prompt"))
        self._set_button(self._study_import_button, self._action("Importar Pack"))
        self._study_prompt_output.setPlaceholderText(self._t("O prompt gerado aparecerá aqui."))
        if not self._study_prompt_output.toPlainText().strip():
            self._study_status.setText(self._t("1. gere o prompt · 2. copie · 3. cole na IA que preferir · 4. importe o pack"))

        self._set_title_label(self._training_title, self._t("Treino").upper())
        self._set_button(self._level_training_button, f"[1] {self._t('Treino por Level').upper()}")
        self._set_button(self._random_training_button, f"[2] {self._t('Treino aleatório').upper()}")
        self._training_pack_label.setText(f"> {self._t('Rank / Pack').upper()}")
        self._training_levels_label.setText(f"> {self._t('Levels').upper()}")
        self._random_draw_label.setText(f"> {self._t('Sorteio').upper()}")
        self._prioritize_radio.set_label(self._t("Priorizar não concluídos"))
        self._only_uncompleted_radio.set_label(self._t("Somente não concluídos"))
        self._all_radio.set_label(self._t("Todos os exercícios"))
        self._allow_repeated_check.set_label(self._t("Permitir repetidos"))
        self._set_button(self._start_training_button, self._action("Start training", "primary"))
        self._choose_level_training() if self._training_kind == "level" else self._choose_random_training()

        self._set_title_label(self._exam_title, self._t("Modo prova").upper())
        self._exam_resume_header.setText(f"● {self._t('Prova em andamento').upper()}")
        self._set_button(self._resume_exam_button, self._action("Continuar prova", "primary"))
        self._set_button(self._end_exam_button, self._action("Encerrar prova"))
        self._exam_new_label.setText(f"> {self._t('Nova prova — Rank / Pack').upper()}")
        self._set_button(self._prepare_exam_button, self._action("Preparar prova", "primary"))
        self._set_title_label(self._exam_prepare_title, self._t("Preparar prova").upper())
        self._set_button(self._start_exam_button, self._action("Start exam", "primary"))

        self._set_button(self._open_editor_button, self._action("Abrir IDE"))
        self._set_button(self._correct_button, self._action("Corrigir", "primary"))
        self._set_button(self._trace_button, self._action("Ver trace"))
        self._set_button(self._next_button, self._action("Próximo/trocar"))
        self._set_button(self._exercise_back_button, self._action("Voltar"))
        self._set_title_label(self._trace_title, "TRACE")
        self._set_button(self._save_trace_button, self._action("Salvar trace como..."))

        self._set_title_label(self._history_title, self._t("Histórico").upper())
        history_tabs = {
            "overview": "Visão geral",
            "packs": "Por Pack",
            "activities": "Atividades",
            "sessions": "Sessões",
            "timeline": "Linha do tempo",
        }
        for key, button in self._history_view_buttons.items():
            self._set_button(button, self._action(history_tabs[key]))
        self._history_pack_label.setText(self._t("Pack"))
        self._history_policy_label.setText(self._t("Sessão"))
        self._refresh_history_policy_filter()

        self._set_title_label(self._settings_title, self._t("Configurações").upper())
        self._locale_label.setText(self._t("Idioma da interface"))
        self._refresh_locale_combo()
        self._refresh_editor_combo()
        self._refresh_settings_cards()
        self._set_title_label(self._pack_help_title, self._t("Como criar um Pack").upper())
        self._set_button(self._open_full_docs_button, self._action("Abrir documentação completa"))
        for button, source in self._footer_buttons:
            self._set_button(button, self._footer_text(source))

    def _footer_text(self, source: str) -> str:
        if source == "[ VOLTAR ]":
            return self._action("Voltar")
        if source == "[ VOLTAR AO EXERCÍCIO ]":
            return self._action("Voltar ao exercício")
        if source == "[ VOLTAR PARA CONFIGURAÇÕES ]":
            return self._action("Voltar para Configurações")
        return source

    def _reset_combo_items(self, combo: QComboBox, labels: tuple[str, ...], values: tuple[str, ...] | None = None) -> None:
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for index, label in enumerate(labels):
            value = values[index] if values is not None else label
            combo.addItem(self._t(label), value)
        if current is not None:
            index = combo.findData(current)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _refresh_locale_combo(self) -> None:
        current = self._locale.locale
        self._locale_combo.blockSignals(True)
        self._locale_combo.clear()
        for locale in SUPPORTED_UI_LOCALES:
            self._locale_combo.addItem(LOCALE_LABELS[locale], locale)
        index = self._locale_combo.findData(current)
        self._locale_combo.setCurrentIndex(max(0, index))
        self._locale_combo.blockSignals(False)

    def _refresh_editor_combo(self) -> None:
        current = self._editor_combo.currentData() or self._editor_combo.currentText()
        self._editor_combo.blockSignals(True)
        self._editor_combo.clear()
        for label in (*self._coordinator.known_editor_labels(), "Outro..."):
            self._editor_combo.addItem(self._t(label), label)
        index = self._editor_combo.findData(current)
        if index < 0:
            index = self._editor_combo.findData("Outro...")
        self._editor_combo.setCurrentIndex(max(0, index))
        self._editor_combo.blockSignals(False)

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
            self._footer_buttons.append((back_button, back_text))
            back_button.setMinimumWidth(180)
            row.addWidget(back_button)
            row.addStretch(1)
            footer.addLayout(row)
        footer.addWidget(ui.HintBar(hints))
        return footer

    # ------------------------------------------------------------------ home
    def _build_home_page(self) -> QWidget:
        page, layout = self._page(margins=28)
        self._home_logo = ui.logo_mark()
        self._title_home = self._title("RankedDojo")
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(self._home_logo)
        title_row.addWidget(self._title_home)
        title_row.addStretch(1)
        self._workspace_label = ui.label(self._workspace_prompt(), role="prompt", wrap=True)
        layout.addLayout(title_row)
        layout.addWidget(self._workspace_label)
        layout.addStretch(1)

        menu = QWidget()
        menu.setMaximumWidth(MENU_WIDTH)
        menu_layout = QVBoxLayout(menu)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(10)
        self._menu_buttons: list[QPushButton] = []
        for index, (text, handler) in enumerate(
            (
                ("QUERO ESTUDAR ALGO NOVO", self._open_study_flow),
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
        layout.addStretch(2)
        layout.addLayout(self._footer(None, [("1-5", "navegar"), ("Tab", "foco"), ("Enter", "abrir")]))
        return page

    def _build_study_page(self) -> QWidget:
        page, layout = self._page(margins=28)
        self._study_title = self._title("QUERO ESTUDAR ALGO NOVO")
        layout.addWidget(self._study_title)
        self._study_description = ui.label(
                "Descreva o que quer estudar, gere um prompt compatível e importe o pack resultante.",
                role="muted",
                wrap=True,
            )
        layout.addWidget(self._study_description)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 10, 0, 10)
        content_layout.setSpacing(14)

        study = ui.card()
        study.setMaximumWidth(900)
        study_layout = QVBoxLayout(study)
        study_layout.setContentsMargins(16, 12, 16, 14)
        study_layout.setSpacing(10)
        self._study_topic = QTextEdit()
        self._study_topic.setPlaceholderText("Ex.: ponteiros e strings, OOP em Python, arrays em Java...")
        self._study_topic.setFixedHeight(72)
        self._study_topic.setAcceptRichText(False)
        self._study_section_label = ui.section_label("> O QUE VOCÊ QUER ESTUDAR?")
        study_layout.addWidget(self._study_section_label)
        study_layout.addWidget(self._study_topic)

        fields = QGridLayout()
        fields.setHorizontalSpacing(10)
        fields.setVerticalSpacing(8)
        self._study_level_combo = self._combo(("Básico", "Intermediário", "Avançado"))
        self._study_goal_combo = self._combo(("Aprender", "Praticar", "Revisar", "Validar conhecimento"))
        self._study_format_combo = self._combo(("Exercícios", "Projeto", "Misto", "Revisão", "Simulado"))
        self._study_language_combo = QComboBox()
        self._study_content_language_combo = self._combo(("Português (pt-BR)", "Inglês (en)"))
        self._study_content_language_combo.setItemData(0, "pt-BR")
        self._study_content_language_combo.setItemData(1, "en")
        self._study_size_combo = self._combo(("Curto", "Médio", "Completo"))
        self._study_field_labels: list[tuple[QLabel, str]] = []
        for index, (caption, widget) in enumerate(
            (
                ("Nível", self._study_level_combo),
                ("Objetivo", self._study_goal_combo),
                ("Formato", self._study_format_combo),
                ("Linguagem", self._study_language_combo),
                ("Idioma", self._study_content_language_combo),
                ("Tamanho", self._study_size_combo),
            )
        ):
            row, column = divmod(index, 2)
            label = ui.label(caption, role="muted")
            self._study_field_labels.append((label, caption))
            fields.addWidget(label, row * 2, column)
            fields.addWidget(widget, row * 2 + 1, column)
        study_layout.addLayout(fields)

        study_actions = QHBoxLayout()
        self._generate_prompt_button = self._button("> GERAR PROMPT", self._generate_study_prompt, "primary")
        self._copy_prompt_button = self._button("[ COPIAR PROMPT ]", self._copy_study_prompt)
        self._study_import_button = self._button("[ IMPORTAR PACK ]", self._import_pack)
        study_actions.addWidget(self._generate_prompt_button)
        study_actions.addWidget(self._copy_prompt_button)
        study_actions.addWidget(self._study_import_button)
        study_actions.addStretch(1)
        study_layout.addLayout(study_actions)
        self._study_prompt_output = QTextEdit()
        self._study_prompt_output.setReadOnly(True)
        self._study_prompt_output.setAcceptRichText(False)
        self._study_prompt_output.setPlaceholderText("O prompt gerado aparecerá aqui.")
        self._study_prompt_output.setMinimumHeight(128)
        study_layout.addWidget(self._study_prompt_output)
        self._study_status = ui.label("1. gere o prompt · 2. copie · 3. cole na IA que preferir · 4. importe o pack", role="muted", wrap=True)
        study_layout.addWidget(self._study_status)
        content_layout.addLayout(self._centered(study))
        content_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        layout.addLayout(self._footer(self._show_home, [("Esc", "voltar"), ("Ctrl+C", "copiar prompt")]))
        return page

    @staticmethod
    def _combo(items: tuple[str, ...]) -> QComboBox:
        combo = QComboBox()
        for item in items:
            combo.addItem(item, item)
        return combo

    # --------------------------------------------------------------- training
    def _build_training_page(self) -> QWidget:
        page, layout = self._page()
        self._training_title = self._title("TREINO")
        layout.addWidget(self._training_title)

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
        self._prioritize_radio = ui.OptionButton("prioritize_uncompleted", kind="radio", checked=True, label="Priorizar não concluídos")
        self._only_uncompleted_radio = ui.OptionButton("only_uncompleted", kind="radio", label="Somente não concluídos")
        self._all_radio = ui.OptionButton("all_exercises", kind="radio", label="Todos os exercícios")
        for radio in (self._prioritize_radio, self._only_uncompleted_radio, self._all_radio):
            self._selection_group.addButton(radio)
        self._allow_repeated_check = ui.OptionButton("allow_repeats", kind="check", label="Permitir repetidos")
        self._random_draw_label = ui.section_label("> SORTEIO")
        random_options.addWidget(self._random_draw_label)
        for widget in (self._prioritize_radio, self._only_uncompleted_radio, self._all_radio):
            random_options.addWidget(widget)
        random_options.addSpacing(6)
        random_options.addWidget(self._allow_repeated_check)

        options.addWidget(self._training_mode_label)
        self._training_pack_label = ui.section_label("> RANK / PACK")
        options.addWidget(self._training_pack_label)
        options.addWidget(self._training_pack_combo)
        options.addSpacing(6)
        self._training_levels_label = ui.section_label("> LEVELS")
        options.addWidget(self._training_levels_label)
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

    # --------------------------------------------------------------- exam mode
    def _build_exam_page(self) -> QWidget:
        page, layout = self._page()
        self._exam_title = self._title("MODO PROVA")
        layout.addWidget(self._exam_title)

        self._exam_resume_card = ui.card(status="pending")
        resume = QVBoxLayout(self._exam_resume_card)
        resume.setContentsMargins(16, 12, 16, 14)
        resume.setSpacing(8)
        self._exam_resume_header = ui.label("● PROVA EM ANDAMENTO", status="pending")
        resume.addWidget(self._exam_resume_header)
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
        self._exam_new_label = ui.section_label("> NOVA PROVA — RANK / PACK")
        layout.addWidget(self._exam_new_label)
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
        self._exam_prepare_title = self._title("PREPARAR PROVA")
        layout.addWidget(self._exam_prepare_title)
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

    # --------------------------------------------------------------- exercise
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
        # compat: single label with metadata, used by screen inspection tests
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
        self._exercise_back_button = self._button("[ VOLTAR ]", self._back_from_exercise)
        buttons.addWidget(self._open_editor_button, 3)
        buttons.addWidget(self._correct_button, 3)
        buttons.addWidget(self._trace_button, 2)
        buttons.addWidget(self._next_button, 3)
        buttons.addWidget(self._exercise_back_button, 2)
        layout.addLayout(buttons)
        return page

    def _build_trace_page(self) -> QWidget:
        page, layout = self._page()
        self._trace_title = self._title("TRACE")
        layout.addWidget(self._trace_title)
        layout.addWidget(ui.label("trace.log — less", role="panel-caption"))
        self._trace_text = self._terminal_text()
        layout.addWidget(self._trace_text, 1)
        row = QHBoxLayout()
        self._save_trace_button = self._button("[ SALVAR TRACE COMO... ]", self._save_trace_as)
        row.addWidget(self._save_trace_button)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addLayout(
            self._footer(lambda: self._go(self._exercise_page), [("Esc", "voltar ao exercício")], "[ VOLTAR AO EXERCÍCIO ]")
        )
        return page

    # ---------------------------------------------------------------- history
    def _build_history_page(self) -> QWidget:
        page, layout = self._page(spacing=8)
        self._history_title = self._title("HISTÓRICO")
        layout.addWidget(self._history_title)
        layout.addSpacing(4)
        self._history_view = "overview"
        view_row = QHBoxLayout()
        view_row.setSpacing(0)
        self._history_view_buttons: dict[str, QPushButton] = {}
        for key, text in (
            ("overview", "[ VISÃO GERAL ]"),
            ("packs", "[ POR PACK ]"),
            ("activities", "[ ATIVIDADES ]"),
            ("sessions", "[ SESSÕES ]"),
            ("timeline", "[ LINHA DO TEMPO ]"),
        ):
            button = self._button(text, lambda checked=False, view=key: self._set_history_view(view), "tab")
            button.setCheckable(True)
            self._history_view_buttons[key] = button
            view_row.addWidget(button)
        view_row.addStretch(1)
        layout.addLayout(view_row)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self._history_pack_filter = QComboBox()
        self._history_pack_filter.currentIndexChanged.connect(lambda _index=0: self._show_history(refresh_filters=False))
        self._history_policy_filter = QComboBox()
        self._history_policy_filter.addItem(self._t("Todas as sessões"), "")
        self._history_policy_filter.addItem(self._t("Training filter"), "training")
        self._history_policy_filter.addItem(self._t("Exam filter"), "exam")
        self._history_policy_filter.currentIndexChanged.connect(lambda _index=0: self._show_history(refresh_filters=False))
        self._history_pack_label = ui.label("Pack", role="muted")
        filters.addWidget(self._history_pack_label)
        filters.addWidget(self._history_pack_filter, 2)
        self._history_policy_label = ui.label("Sessão", role="muted")
        filters.addWidget(self._history_policy_label)
        filters.addWidget(self._history_policy_filter, 1)
        filters.addStretch(1)
        layout.addLayout(filters)

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

        self._history_table = self._table(("ITEM", "VALOR"), stretch=1)
        layout.addWidget(self._history_table, 1)
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

    # ---------------------------------------------------------------- settings
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

        # idioma da interface
        self._locale_label = ui.label("", role="muted")
        self._locale_combo = QComboBox()
        self._locale_combo.currentIndexChanged.connect(self._set_locale_from_combo)
        sections.addWidget(self._settings_card("IDIOMA", [self._locale_label, self._locale_combo], []))

        # workspace
        self._settings_workspace = ui.label("", wrap=True)
        sections.addWidget(
            self._settings_card("WORKSPACE", [self._settings_workspace], [("[ ALTERAR WORKSPACE ]", self._change_workspace)])
        )

        # editor
        self._editor_combo = QComboBox()
        self._editor_combo.currentIndexChanged.connect(self._editor_preset_changed)
        self._settings_editor = QLineEdit()
        sections.addWidget(
            self._settings_card(
                "EDITOR/IDE",
                [self._editor_combo, self._settings_editor],
                [
                    ("[ DETECTAR AUTOMATICAMENTE ]", self._detect_editor_automatically),
                    ("[ SELECIONAR EXECUTÁVEL ]", self._browse_editor),
                    ("[ SALVAR EDITOR ]", self._save_editor_setting),
                ],
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
                    f"runtime:{language}",
                    [label],
                    [
                        (f"detect-runtime:{language}", lambda checked=False, lang=language: self._redetect_runtime(lang)),
                        (f"select-runtime:{language}", lambda checked=False, lang=language: self._choose_manual_runtime(lang)),
                    ],
                )
            )

        # packs
        self._packs_summary = ui.label("", wrap=True)
        self._pack_capabilities_summary = ui.label("", wrap=True)
        sections.addWidget(
            self._settings_card(
                "PACKS",
                [self._packs_summary, self._pack_capabilities_summary],
                [
                    ("[ IMPORTAR PACK ]", self._import_pack),
                    ("[ ATUALIZAR PACKS ]", self._refresh_packs),
                    ("[ ABRIR DOCUMENTAÇÃO DE PACKS ]", self._show_pack_help),
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
        title_label = ui.section_label(title)
        title_label.setProperty("sourceText", title)
        layout.addWidget(title_label)
        for widget in body:
            layout.addWidget(widget)
        if actions:
            row = QHBoxLayout()
            row.setSpacing(8)
            for text, handler in actions:
                button = self._button(text, handler)
                button.setProperty("sourceText", text)
                row.addWidget(button)
            row.addStretch(1)
            layout.addLayout(row)
        return frame

    def _refresh_settings_cards(self) -> None:
        for label in self._settings_page.findChildren(QLabel):
            source = label.property("sourceText")
            if isinstance(source, str):
                label.setText(self._settings_title_text(source))
        for button in self._settings_page.findChildren(QPushButton):
            source = button.property("sourceText")
            if isinstance(source, str):
                self._set_button(button, self._settings_action_text(source))

    def _settings_title_text(self, source: str) -> str:
        mapping = {
            "TEMA": "Tema",
            "IDIOMA": "Idioma da interface",
            "WORKSPACE": "Workspace",
            "EDITOR/IDE": "Editor/IDE",
            "PACKS": "Packs",
        }
        if source.startswith("runtime:"):
            return self._runtime_ui_name(source.removeprefix("runtime:")).upper()
        return self._t(mapping.get(source, source)).upper()

    def _settings_action_text(self, source: str) -> str:
        if source.startswith("detect-runtime:"):
            return self._action("Detectar novamente")
        if source.startswith("select-runtime:"):
            language = source.removeprefix("select-runtime:")
            return self._action("Selecionar {runtime}", runtime=self._runtime_ui_name(language))
        normalized = source.strip()
        if normalized.startswith("[ ") and normalized.endswith(" ]"):
            normalized = normalized[2:-2]
        action_map = {
            "ALTERAR WORKSPACE": "Alterar workspace",
            "DETECTAR AUTOMATICAMENTE": "Detectar automaticamente",
            "SELECIONAR EXECUTÁVEL": "Selecionar executável",
            "SALVAR EDITOR": "Salvar editor",
            "DETECTAR NOVAMENTE": "Detectar novamente",
            "IMPORTAR PACK": "Importar Pack",
            "ATUALIZAR PACKS": "Atualizar Packs",
            "ABRIR DOCUMENTAÇÃO DE PACKS": "Abrir documentação de Packs",
        }
        upper = normalized.upper()
        if upper in action_map:
            return self._action(action_map[upper])
        if upper.startswith("SELECIONAR "):
            runtime = normalized[len("SELECIONAR ") :]
            return self._action("Selecionar {runtime}", runtime=runtime)
        return self._action(normalized)

    def _runtime_ui_name(self, language: str) -> str:
        names = {
            "c": self._t("Compilador C"),
            "cpp": self._t("Compilador C++"),
            "python": "Python",
            "java": "Java",
        }
        if language in names:
            return names[language]
        return self._coordinator.runtime_display_name(language)

    def _build_pack_help_page(self) -> QWidget:
        page, layout = self._page()
        self._pack_help_title = self._title("COMO CRIAR UM PACK")
        layout.addWidget(self._pack_help_title)
        layout.addWidget(ui.label("PACKS.md — less", role="panel-caption"))
        self._pack_help_text = self._terminal_text()
        self._pack_help_text.setPlainText(self._pack_help_content())
        layout.addWidget(self._pack_help_text, 1)
        row = QHBoxLayout()
        self._open_full_docs_button = self._button("[ ABRIR DOCUMENTAÇÃO COMPLETA ]", self._open_full_documentation)
        row.addWidget(self._open_full_docs_button)
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
            self._study_page: self._show_home,
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
        return f"dojo@RankedDojo:{compact}$"

    def _set_title_label(self, label: QLabel, text: str) -> None:
        self._cursor.set_title(label, text)

    # -------------------------------------------------------------- navigation
    def _show_home(self) -> None:
        self._show_resume_if_needed()
        self._refresh_home_status()
        self._refresh_study_languages()
        self._go(self._home_page)

    def _open_study_flow(self) -> None:
        self._refresh_study_languages()
        self._go(self._study_page)

    def _refresh_home_status(self) -> None:
        packs = len(self._coordinator.list_packs())
        ready = sum(1 for status in self._coordinator.runtime_statuses() if status.tool)
        total = len(self._coordinator.runtime_statuses())
        runtimes = self._t("{ready}/{total} verificados", ready=ready, total=total) if total else self._t("0 registrados")
        exam = f"   ·   {self._t('prova em andamento')}" if self._coordinator.load_active_exam() is not None else ""
        self._home_status.setText(f"{self._t('packs')}: {packs}   ·   {self._t('runtimes')}: {runtimes}{exam}")

    def _refresh_study_languages(self) -> None:
        current = self._study_language_combo.currentData()
        self._study_language_combo.blockSignals(True)
        self._study_language_combo.clear()
        self._study_language_combo.addItem(self._t("Automático"), "automatic")
        for status in self._coordinator.runtime_statuses():
            label = f"{status.display_name} ({status.language})"
            if not status.available and not status.tool:
                label += f" · {self._t('não verificado')}"
            self._study_language_combo.addItem(label, status.language)
        if current is not None:
            index = self._study_language_combo.findData(current)
            if index >= 0:
                self._study_language_combo.setCurrentIndex(index)
        self._study_language_combo.blockSignals(False)

    def _study_intent(self) -> StudyIntent:
        return StudyIntent(
            topic=self._study_topic.toPlainText(),
            level=str(self._study_level_combo.currentData() or self._study_level_combo.currentText()),
            goal=str(self._study_goal_combo.currentData() or self._study_goal_combo.currentText()),
            format=str(self._study_format_combo.currentData() or self._study_format_combo.currentText()),
            programming_language=str(self._study_language_combo.currentData() or "automatic"),
            content_language=str(self._study_content_language_combo.currentData() or "pt-BR"),
            size=str(self._study_size_combo.currentData() or self._study_size_combo.currentText()),
        )

    def _generate_study_prompt(self) -> None:
        try:
            contract = pack_contract_text()
        except OSError:
            contract = self._t("Documentação do contrato não encontrada nesta instalação.")
        prompt = self._coordinator.build_pack_prompt(self._study_intent(), contract)
        self._study_prompt_output.setPlainText(prompt)
        self._study_status.setText(self._t("Prompt gerado. Copie, use no gerador/IA que preferir e importe o pack."))

    def _copy_study_prompt(self) -> None:
        prompt = self._study_prompt_output.toPlainText()
        if not prompt.strip():
            self._generate_study_prompt()
            prompt = self._study_prompt_output.toPlainText()
        QApplication.clipboard().setText(prompt)
        self._study_status.setText(self._t("Prompt copiado para a área de transferência."))

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
        """True if the language runtime has already been validated.

        Otherwise validates in the background and calls `then`. Detection runs
        external compiler/interpreter probe processes and may take time. On
        failure, preflight shows the message and opens Settings.
        """
        if self._coordinator.runtime_ready(language):
            return True
        if self._tasks.is_busy("runtime"):
            return False
        self._home_status.setText(self._t("verificando ambiente de execução..."))
        self._run_task(
            "runtime",
            lambda: self._coordinator.preflight_runtime(language),
            lambda preflight: then() if preflight.ok else self._handle_preflight(preflight, then),
            self._t("Ambiente de execução"),
            on_finally=self._refresh_home_status,
        )
        return False

    def _exercise_preflight_checked(self, active: ActiveExercise, then: Callable[[], None]) -> bool:
        if self._coordinator.runtime_ready(active.ref.definition.language):
            preflight = self._coordinator.preflight_exercise(active.ref)
            return self._handle_preflight(preflight, then)
        if self._tasks.is_busy("preflight"):
            return False
        self._home_status.setText(self._t("verificando exercício..."))
        self._run_task(
            "preflight",
            lambda: self._coordinator.preflight_exercise(active.ref),
            lambda preflight: self._finish_exercise_preflight(preflight, active, then),
            self._t("Exercício"),
            on_finally=self._refresh_home_status,
        )
        return False

    def _exam_preflight_checked(self, then: Callable[[], None]) -> bool:
        pack_id = self._selected_exam_pack_id()
        if getattr(self, "_exam_preflight_ready_pack", None) == pack_id:
            self._exam_preflight_ready_pack = None
            return True
        if self._coordinator.pack_runtimes_ready(pack_id):
            preflight = self._coordinator.preflight_exam(pack_id)
            return self._handle_preflight(preflight, then)
        if self._tasks.is_busy("runtime"):
            return False
        self._home_status.setText(self._t("verificando ambientes de execução..."))
        self._run_task(
            "runtime",
            lambda: self._coordinator.preflight_exam(pack_id),
            lambda preflight: self._finish_exam_preflight(preflight, then, pack_id),
            self._t("Ambiente de execução"),
            on_finally=self._refresh_home_status,
        )
        return False

    def _finish_exam_preflight(
        self,
        preflight: PreflightResult,
        then: Callable[[], None],
        pack_id: str | None,
    ) -> None:
        if preflight.ok:
            self._exam_preflight_ready_pack = pack_id
            then()
            return
        self._handle_preflight(preflight, then)

    def _handle_preflight(self, preflight: PreflightResult, resume: Callable[[], None]) -> bool:
        if preflight.ok:
            return True
        if preflight.status is ActivityPreflightStatus.CONTENT_INVALID:
            QMessageBox.warning(self, self._t("Conteúdo do pack inválido"), self._preflight_user_message(preflight))
            return False
        self._pending_action = resume
        QMessageBox.information(self, self._t("Configuração necessária"), self._preflight_user_message(preflight))
        self._show_settings(preflight.missing)
        return False

    def _preflight_user_message(self, preflight: PreflightResult) -> str:
        if preflight.missing == "editor":
            return self._t("Configure um editor/IDE válido antes de abrir a pasta do exercício.")
        if preflight.missing == "Runtimes":
            return self._t("Instale ou configure um runtime compatível para corrigir este exercício.")
        return preflight.message

    def _resume_pending_if_ready(self) -> None:
        if self._pending_action is None:
            return
        action = self._pending_action
        self._pending_action = None
        action()

    def _choose_level_training(self) -> None:
        self._training_kind = "level"
        self._training_mode_label.setText(self._t("Treino por Level — escolha os levels e comece."))
        self._random_options.setVisible(False)
        self._training_options_panel.setVisible(True)
        self._level_training_button.setChecked(True)
        self._random_training_button.setChecked(False)

    def _choose_random_training(self) -> None:
        self._training_kind = "random"
        self._training_mode_label.setText(self._t("Treino Aleatório — sorteia exercícios dos levels marcados."))
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
            or f"○ {self._t('nenhum pack instalado')}"
        )
        self._pack_capabilities_summary.setText(self._pack_capabilities_text())
        self._refresh_levels()
        self._refresh_study_languages()

    def _pack_capabilities_text(self) -> str:
        capabilities = self._coordinator.exercise_capabilities()
        statuses = self._coordinator.runtime_statuses()
        runtimes = ", ".join(f"{status.display_name} ({status.language})" for status in statuses) or self._t("nenhum")
        executions = ", ".join(sorted(capabilities.executions.supported)) or self._t("nenhuma")
        generators = ", ".join(sorted(capabilities.generators.supported)) or self._t("nenhum")
        expectations = ", ".join(sorted(capabilities.expectations.supported)) or self._t("nenhuma")
        return (
            f"{self._t('Contrato')}: schema_version 3\n"
            f"{self._t('Runtimes')}: {runtimes}\n"
            f"{self._t('Strategies')}: {executions}\n"
            f"{self._t('Generators')}: {generators}\n"
            f"{self._t('Validators/expectations')}: {expectations}"
        )

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
            raise ValueError(self._t("Nenhum pack selecionado."))
        levels = self._selected_levels()
        if not levels:
            raise ValueError(self._t("Selecione pelo menos um level."))
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
            QMessageBox.warning(self, self._t("Treino"), str(error))

    # --------------------------------------------------------------- exercise
    def _load_exercise(self, ref: ExerciseRef, mode: str, overwrite: bool = False) -> None:
        active = (
            self._coordinator.prepare_exam_exercise(ref, self._exam_state, overwrite=overwrite)
            if mode == "exam"
            else self._coordinator.prepare_exercise(ref, overwrite=overwrite)
        )
        if active.had_existing_submission and not overwrite:
            answer = QMessageBox.question(
                self,
                self._t("Implementação existente"),
                self._t("Já existe implementação na workspace. Continuar implementação?"),
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
        self._refresh_exercise_frame()
        self._exam_timer_label.setVisible(mode == "exam")
        if mode == "exam" and self._exam_state is not None:
            self._render_exam_timer(self._exam_state)
        self._subject.set_subject_markdown(active.subject_text)
        self._feedback.clear()
        self._open_editor_button.setToolTip(
            self._t("Abrir a pasta do exercício no {editor}", editor=self._coordinator.editor_display_name())
        )
        self._trace_button.setEnabled(False)
        self._next_button.setVisible(mode == "training")
        self._next_button.setEnabled(mode == "training")
        self._go(self._exercise_page)
        self._sync_editor_target(active)

    def _open_editor(self) -> None:
        if self._active is None:
            return
        if not self._handle_preflight(self._coordinator.preflight_editor(), self._open_editor):
            return
        try:
            context = self._editor_context(self._active)
            previous = self._editor_targets.get(context)
            reuse_window = previous is not None and previous != self._active.exercise_workspace_path
            self._coordinator.open_in_editor(self._active, reuse_window=reuse_window)
            self._editor_targets[context] = self._active.exercise_workspace_path
        except Exception as error:
            QMessageBox.warning(self, "Editor", str(error))

    def _sync_editor_target(self, active: ActiveExercise) -> None:
        context = self._editor_context(active)
        previous = self._editor_targets.get(context)
        if previous is None or previous == active.exercise_workspace_path:
            return
        try:
            self._coordinator.open_in_editor(active, reuse_window=True)
            self._editor_targets[context] = active.exercise_workspace_path
        except Exception as error:
            QMessageBox.warning(self, "Editor", str(error))

    def _editor_context(self, active: ActiveExercise) -> tuple[str, str]:
        if self._mode == "exam" and self._exam_state is not None:
            return ("exam", self._exam_state.id)
        return ("training", active.ref.pack.id)

    def _refresh_exercise_frame(self) -> None:
        if self._active is None:
            return
        active = self._active
        self._set_title_label(self._exercise_title, active.ref.definition.name)
        self._exercise_id_label.setText(f"ID: {active.ref.definition.id}")
        self._exercise_rank_label.setText(f"{self._t('Rank').upper()}: {active.ref.pack.name}")
        self._exercise_level_label.setText(f"LEVEL: {active.ref.level_id}")
        self._open_editor_button.setToolTip(
            self._t("Abrir a pasta do exercício no {editor}", editor=self._coordinator.editor_display_name())
        )

    def _submit_current(self) -> None:
        if self._active is None or self._tasks.is_busy("submit"):
            return
        active = self._active
        if getattr(self, "_submit_preflight_ready_for", None) == id(active):
            self._submit_preflight_ready_for = None
        elif not self._exercise_preflight_checked(active, self._submit_current):
            return
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
        self._run_task("submit", work, on_done, self._t("Correção"), on_finally=lambda: self._set_grading(False))

    def _finish_exercise_preflight(
        self,
        preflight: PreflightResult,
        active: ActiveExercise,
        then: Callable[[], None],
    ) -> None:
        if preflight.ok:
            self._submit_preflight_ready_for = id(active)
            then()
            return
        self._handle_preflight(preflight, then)

    def _set_grading(self, busy: bool) -> None:
        self._correct_button.setEnabled(not busy)
        self._cursor.set_button_text(
            self._correct_button,
            self._t("Corrigindo...").upper() if busy else self._action("Corrigir", "primary"),
        )
        self._next_button.setEnabled(not busy and self._mode == "training")

    def _on_training_graded(self, active: ActiveExercise, outcome: CorrectionOutcome) -> None:
        if self._active is not active:
            return  # the user left the exercise; the attempt was already saved
        self._last_outcome = outcome
        self._trace_button.setEnabled(True)
        if outcome.result.outcome is GradingOutcome.CONTENT_ERROR:
            self._show_content_error_feedback()
        elif outcome.result.passed:
            self._show_training_pass_feedback()
        else:
            self._show_training_fail_feedback()

    def _on_exam_graded(self, active: ActiveExercise, result: tuple[CorrectionOutcome, ExamState | None]) -> None:
        outcome, next_state = result
        self._last_outcome = outcome
        self._trace_button.setEnabled(True)
        if next_state is None:
            self._timer.stop()
            self._clear_exam_editor_context()
            self._exam_state = None
            self._show_pass_feedback(self._t("Prova concluída — nota 100%."))
            self._show_resume_if_needed()
            return
        self._exam_state = next_state
        # If the deadline expired while grading, finish now with the already updated score.
        self._tick_exam()
        if self._exam_state is None:
            return
        if outcome.result.outcome is GradingOutcome.CONTENT_ERROR:
            # Never shown as FAIL: this isn't the user's submission being
            # wrong, it's the exercise's own content/reference. The exam
            # stays on the same exercise (see `submit_exam`); no attempt or
            # level result was recorded.
            if self._active is active:
                self._show_content_error_feedback()
            return
        if outcome.result.passed:
            try:
                self._load_exercise(self._coordinator.exam_ref(next_state), mode="exam")
            except Exception as error:
                QMessageBox.warning(self, self._t("Modo prova"), str(error))
                return
            self._show_pass_feedback(self._t("Exercício anterior concluído. Próximo exercício carregado."))
            return
        if self._active is active:
            self._show_fail_feedback(self._t("Você continua neste exercício. Corrija e envie de novo."))

    def _show_training_fail_feedback(self) -> None:
        self._show_fail_feedback(self._t("Veja o trace técnico, ajuste no editor e corrija de novo."))

    def _show_training_pass_feedback(self) -> None:
        self._show_pass_feedback(self._t("Exercício concluído.").upper(), with_next=True)

    def _show_fail_feedback(self, message: str) -> None:
        editor = self._coordinator.editor_display_name()
        actions = [
            ui.button(self._action("Ver trace"), self._show_trace, "small"),
            ui.button(self._action("Abrir no {editor}", editor=editor), self._open_editor, "small"),
            ui.button(self._action("Voltar para corrigir"), self._feedback.clear, "small"),
        ]
        self._feedback.show_result("fail", "[✗] FAIL", message, actions, animate=self._theme.tokens.animations)

    def _show_content_error_feedback(self) -> None:
        """Content/pack error, distinct from a normal user FAIL (never uses the 'fail' status)."""
        actions = [ui.button(self._action("Ver trace"), self._show_trace, "small")]
        self._feedback.show_result(
            "pending",
            "[!] " + self._t("CONTEÚDO INVÁLIDO"),
            self._t("Este exercício tem um erro de conteúdo do pack — não é um erro seu. Não conta como tentativa."),
            actions,
            animate=self._theme.tokens.animations,
        )

    def _show_pass_feedback(self, message: str, with_next: bool = False) -> None:
        actions: list[QPushButton] = []
        if with_next and self._mode == "training":
            actions.append(ui.button(self._action("Próximo exercício"), self._next_exercise, "small"))
        self._feedback.show_result("pass", "[✓] PASS", message, actions, animate=self._theme.tokens.animations)

    def _show_trace(self) -> None:
        if self._last_outcome is None:
            return
        self._trace_text.setPlainText(self._last_outcome.result.trace_data.as_text())
        self._go(self._trace_page)

    def _save_trace_as(self) -> None:
        if self._last_outcome is None:
            return
        target, _ = QFileDialog.getSaveFileName(self, self._t("Salvar trace como..."), "trace.txt")
        if target:
            Path(target).write_text(self._last_outcome.result.trace_data.as_text(), encoding="utf-8")

    def _next_exercise(self) -> None:
        if self._training_options is None or self._mode != "training":
            return
        try:
            self._load_exercise(self._coordinator.choose_training_exercise(self._training_options), mode="training")
        except Exception as error:
            QMessageBox.warning(self, self._t("Treino"), str(error))

    # -------------------------------------------------------------------- exam
    def _start_exam(self) -> None:
        if not self._exam_preflight_checked(self._start_exam):
            return
        pack_id = self._selected_exam_pack_id()
        if pack_id is None:
            QMessageBox.warning(self, self._t("Modo prova"), self._t("Nenhum pack selecionado."))
            return
        try:
            self._exam_state = self._coordinator.start_exam(pack_id)
            self._timer.start(1000)
            self._load_exercise(self._coordinator.exam_ref(self._exam_state), mode="exam")
            self._show_resume_if_needed()
        except Exception as error:
            QMessageBox.warning(self, self._t("Modo prova"), str(error))

    def _show_exam_prepare(self) -> None:
        if not self._exam_preflight_checked(self._show_exam_prepare):
            return
        pack_id = self._selected_exam_pack_id()
        if pack_id is None:
            QMessageBox.warning(self, self._t("Modo prova"), self._t("Nenhum pack selecionado."))
            return
        pack = self._selected_pack(pack_id)
        if pack is None:
            QMessageBox.warning(self, self._t("Modo prova"), self._t("Pack selecionado não encontrado."))
            return
        levels = self._coordinator.list_levels(pack_id)
        lines = [
            f"{self._t('Pack/Rank'):<10}: {pack.name}",
            f"ID        : {pack.id}",
            f"Levels    : {len(levels)}",
            "",
            self._t("Estrutura da prova baseada no pack real:"),
            *(f"  {index}. {level}" for index, level in enumerate(levels, start=1)),
            "",
            f"{self._t('Duração'):<10}: {self._format_seconds(self._coordinator.exam_duration_seconds(pack_id))}"
            + ("" if pack.exam_duration_seconds else f"  ({self._t('padrão; o pack não declara exam.duration_minutes')})"),
            f"{self._t('Aprovação'):<10}: 100%",
            "",
            f"{self._t('Regras')}:",
            f"- {self._t('ao errar, permanece no mesmo exercício;')}",
            f"- {self._t('ao passar, avança automaticamente;')}",
            f"- {self._t('não é permitido trocar exercício;')}",
            f"- {self._t('o relógio NÃO pausa: fechar o app não para o tempo;')}",
            f"- {self._t('se o tempo acabar, a prova encerra e salva nota parcial;')}",
            f"- {self._t('se fechar no meio, a sessão pode ser retomada enquanto houver tempo.')}",
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
            QMessageBox.information(self, self._t("Modo prova"), self._t("Não há prova em andamento."))
            return
        self._exam_state = state
        self._timer.start(1000)
        self._load_exercise(self._coordinator.exam_ref(state), mode="exam")

    def _end_exam(self) -> None:
        state = self._coordinator.load_active_exam()
        if state is None:
            QMessageBox.information(self, self._t("Modo prova"), self._t("Não há prova em andamento."))
            return
        self._coordinator.finish_exam(state, "abandoned", state.score)
        self._timer.stop()
        self._clear_exam_editor_context(state.id)
        self._exam_state = None
        self._show_resume_if_needed()
        QMessageBox.information(self, self._t("Modo prova"), self._t("Prova encerrada."))

    def _tick_exam(self) -> None:
        if self._exam_state is None:
            return
        if self._tasks.is_busy("submit"):
            # Do not finish the exam in the middle of grading: the timer keeps
            # drawing and the finish happens when grading returns.
            remaining = self._coordinator.remaining_seconds(self._exam_state)
            self._render_exam_timer(replace(self._exam_state, remaining_seconds=remaining))
            return
        state = self._coordinator.tick_exam(self._exam_state)
        if state is None:
            self._timer.stop()
            self._clear_exam_editor_context()
            self._exam_state = None
            self._exam_timer_label.setText(self._t("Tempo esgotado").upper())
            ui.set_status(self._exam_timer_label, "fail")
            QMessageBox.information(self, self._t("Modo prova"), self._t("Tempo esgotado. Prova encerrada."))
            return
        self._exam_state = state
        self._render_exam_timer(state)

    def _clear_exam_editor_context(self, session_id: str | None = None) -> None:
        if session_id is None and self._exam_state is not None:
            session_id = self._exam_state.id
        if session_id is not None:
            self._editor_targets.pop(("exam", session_id), None)

    def _render_exam_timer(self, state: ExamState) -> None:
        self._exam_timer_label.setText(f"⏱ {self._format_seconds(state.remaining_seconds)}   {self._t('Nota').upper()} {state.score:.0f}%")

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
                self._t("Modo prova"),
                self._t(
                    "O tempo da prova terminou enquanto o app estava fechado.\nA prova foi encerrada com nota parcial de {score}%.",
                    score=f"{expired.score:.0f}",
                ),
            )
        has_state = state is not None
        self._exam_resume_card.setVisible(has_state)
        self._resume_exam_button.setVisible(has_state)
        self._end_exam_button.setVisible(has_state)
        if state is None:
            self._exam_resume_label.setText("")
            return
        self._exam_resume_label.setText(
            f"{self._t('Rank'):<10}: {state.pack_id}\n"
            f"{self._t('Exercício'):<10}: {state.exercise_id}\n"
            f"{self._t('Restante'):<10}: {self._format_seconds(state.remaining_seconds)}"
        )

    # ---------------------------------------------------------------- history
    def _show_history(self, refresh_filters: bool = True) -> None:
        if refresh_filters:
            self._refresh_history_filters()
        self._render_history()
        if self._stack.currentWidget() is not self._history_page:
            self._go(self._history_page)

    def _set_history_view(self, view: str) -> None:
        self._history_view = view
        self._render_history()

    def _refresh_history_policy_filter(self) -> None:
        current = self._history_policy_filter.currentData()
        self._history_policy_filter.blockSignals(True)
        self._history_policy_filter.clear()
        self._history_policy_filter.addItem(self._t("Todas as sessões"), "")
        self._history_policy_filter.addItem(self._t("Training filter"), "training")
        self._history_policy_filter.addItem(self._t("Exam filter"), "exam")
        if current is not None:
            index = self._history_policy_filter.findData(current)
            if index >= 0:
                self._history_policy_filter.setCurrentIndex(index)
        self._history_policy_filter.blockSignals(False)

    def _refresh_history_filters(self) -> None:
        current = self._history_pack_filter.currentData()
        self._history_pack_filter.blockSignals(True)
        self._history_pack_filter.clear()
        self._history_pack_filter.addItem(self._t("Todos os packs"), "")
        for pack in self._coordinator.list_packs():
            self._history_pack_filter.addItem(f"{pack.name} ({pack.id})", pack.id)
        if current is not None:
            index = self._history_pack_filter.findData(current)
            if index >= 0:
                self._history_pack_filter.setCurrentIndex(index)
        self._history_pack_filter.blockSignals(False)

    def _history_query(self) -> HistoryQuery:
        pack = str(self._history_pack_filter.currentData() or "") or None
        policy = str(self._history_policy_filter.currentData() or "") or None
        return HistoryQuery(pack_id=pack, policy=policy)

    def _render_history(self) -> None:
        for key, button in self._history_view_buttons.items():
            button.setChecked(key == self._history_view)
        rows = self._filtered_exercise_rows()
        completed = sum(1 for row in rows if row["status"] == ActivityProgress.COMPLETED)
        attempted = sum(1 for row in rows if row["status"] == ActivityProgress.ATTEMPTED)
        pending = max(0, len(rows) - completed - attempted)
        bar_width = 20
        filled = 0 if not rows else round((completed / len(rows)) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        self._history_summary.setText(f"[{bar}] {self._t('{completed}/{total} concluídos', completed=completed, total=len(rows))}")
        self._history_pass.setText(f"PASS: {completed}")
        self._history_fail.setText(f"FAIL: {attempted}")
        self._history_pending.setText(f"{self._t('Pendentes').upper()}: {pending}")
        if self._history_view == "packs":
            self._populate_history_by_pack(rows)
        elif self._history_view == "activities":
            self._populate_history_table(rows)
        elif self._history_view == "sessions":
            self._populate_history_sessions()
        elif self._history_view == "timeline":
            self._populate_history_timeline()
        else:
            self._populate_history_overview(rows)

    def _filtered_exercise_rows(self) -> list[dict[str, object]]:
        query = self._history_query()
        rows = self._coordinator.exercise_history_rows()
        if query.pack_id is not None:
            rows = [row for row in rows if str(row.get("pack_id")) == query.pack_id]
        if query.policy is not None:
            rows = [row for row in rows if query.policy in str(row.get("modes", ""))]
        return rows

    def _item(self, text: str, color: str | None = None, align_right: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if color:
            item.setForeground(self._theme.color(color))
        alignment = Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignRight if align_right else Qt.AlignmentFlag.AlignLeft)
        item.setTextAlignment(alignment)
        return item

    def _set_history_headers(self, headers: tuple[str, ...], stretch: int) -> None:
        self._history_table.clear()
        self._history_table.setColumnCount(len(headers))
        self._history_table.setHorizontalHeaderLabels(headers)
        header = self._history_table.horizontalHeader()
        for column in range(len(headers)):
            mode = QHeaderView.ResizeMode.Stretch if column == stretch else QHeaderView.ResizeMode.ResizeToContents
            header.setSectionResizeMode(column, mode)

    def _populate_history_overview(self, rows: list[dict[str, object]]) -> None:
        sessions = self._filtered_exam_rows()
        timeline = self._coordinator.history_timeline(self._history_query())
        completed = sum(1 for row in rows if row["status"] == ActivityProgress.COMPLETED)
        attempted = sum(
            1 for row in rows if row["status"] in {ActivityProgress.COMPLETED, ActivityProgress.ATTEMPTED}
        )
        packs = len({str(row.get("pack_id")) for row in rows})
        last = "-" if not timeline else f"{timeline[0].policy} · {timeline[0].identity.activity_id} · {timeline[0].status}"
        data = (
            (self._t("Atividades concluídas"), str(completed)),
            (self._t("Atividades tentadas"), str(attempted)),
            (self._t("Packs usados"), str(packs)),
            (self._t("Sessões de prova"), str(len(sessions))),
            (self._t("Última atividade"), last),
        )
        self._set_history_headers((self._t("Item").upper(), self._t("Valor").upper()), 1)
        self._history_table.setRowCount(len(data))
        for row_index, (label, value) in enumerate(data):
            self._history_table.setItem(row_index, 0, self._item(label, "text_secondary"))
            self._history_table.setItem(row_index, 1, self._item(value))

    def _populate_history_by_pack(self, rows: list[dict[str, object]]) -> None:
        grouped: dict[str, dict[str, object]] = {}
        for row in rows:
            pack_id = str(row.get("pack_id"))
            group = grouped.setdefault(
                pack_id,
                {"pack": row.get("pack"), "activities": 0, "completed": 0, "attempts": 0, "latest": "-"},
            )
            group["activities"] = int(group["activities"]) + 1
            group["completed"] = int(group["completed"]) + (
                1 if row["status"] == ActivityProgress.COMPLETED else 0
            )
            group["attempts"] = int(group["attempts"]) + int(row["attempts"])
            if row.get("last_attempt_at"):
                group["latest"] = self._format_date(row["last_attempt_at"])
        self._set_history_headers(
            ("PACK", self._t("Atividades").upper(), self._t("Concluídas").upper(), self._t("Tentativas").upper(), self._t("Última").upper()),
            0,
        )
        items = sorted(grouped.items())
        self._history_table.setRowCount(len(items))
        for row_index, (_pack_id, group) in enumerate(items):
            cells = (
                self._item(str(group["pack"])),
                self._item(str(group["activities"]), align_right=True),
                self._item(str(group["completed"]), "success", align_right=True),
                self._item(str(group["attempts"]), align_right=True),
                self._item(str(group["latest"]), "text_secondary"),
            )
            for column, item in enumerate(cells):
                self._history_table.setItem(row_index, column, item)

    def _populate_history_table(self, rows: list[dict[str, object]]) -> None:
        self._set_history_headers(
            (
                self._t("Pack/Level").upper(),
                self._t("Atividade").upper(),
                self._t("Status").upper(),
                self._t("Tentativas").upper(),
                self._t("Último resultado").upper(),
                self._t("Data").upper(),
            ),
            1,
        )
        self._history_table.setRowCount(len(rows))
        # Group by (pack, level): the same level/exercise id may exist in different packs.
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
            status = row["status"]
            latest = str(row["latest_result"])
            attempts = int(row["attempts"])
            if status == ActivityProgress.COMPLETED:
                marker, status_color = "[✓]", "success"
            elif status == ActivityProgress.ATTEMPTED and latest == "FAIL":
                marker, status_color = "[✗]", "fail"
            elif status == ActivityProgress.ATTEMPTED:
                marker, status_color = "[…]", "warning"
            else:
                marker, status_color = "[ ]", "text_secondary"
            latest_color = {"PASS": "success", "FAIL": "fail"}.get(latest, "text_secondary")
            cells = (
                self._item(f"{level}/" if seen[level] == 1 else "", "text_secondary"),
                self._item(f"{branch} {row['exercise_id']}"),
                self._item(f"{marker} {self._display_history_status(status)}", status_color),
                self._item(str(attempts), None if attempts else "text_secondary", align_right=True),
                self._item(latest, latest_color),
                self._item(self._format_date(row["last_attempt_at"]), "text_secondary"),
            )
            for column, item in enumerate(cells):
                self._history_table.setItem(row_index, column, item)

    def _filtered_exam_rows(self) -> list[dict[str, object]]:
        query = self._history_query()
        rows = self._coordinator.exam_history_rows()
        if query.pack_id is not None:
            rows = [row for row in rows if str(row.get("rank") or row.get("pack_id") or "") == query.pack_id]
        if query.policy is not None:
            rows = [row for row in rows if str(row.get("policy") or "") == query.policy]
        return rows

    def _populate_history_sessions(self) -> None:
        exam_rows = self._filtered_exam_rows()
        self._set_history_headers(
            (
                self._t("Data").upper(),
                "PACK",
                self._t("Status").upper(),
                self._t("Nota").upper(),
                self._t("Duração tabela").upper(),
                self._t("Atividades").upper(),
            ),
            5,
        )
        self._history_table.setRowCount(len(exam_rows))
        for row_index, row in enumerate(exam_rows):
            raw_status = str(row.get("status") or "-")
            status_key, status_color = EXAM_STATUS_KEYS.get(raw_status, (raw_status, "text_secondary"))
            status = self._t(status_key)
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
                self._history_table.setItem(row_index, column, item)

    def _populate_history_timeline(self) -> None:
        entries = self._coordinator.history_timeline(self._history_query())
        self._set_history_headers(
            (self._t("Data").upper(), self._t("Sessão").upper(), "PACK", self._t("Atividade").upper(), self._t("Status").upper()),
            3,
        )
        self._history_table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            status_color = "success" if entry.passed else ("fail" if entry.passed is False else "text_secondary")
            cells = (
                self._item(self._format_date(entry.submitted_at), "text_secondary"),
                self._item(entry.policy or "-"),
                self._item(entry.identity.pack_id),
                self._item(entry.identity.activity_id),
                self._item(self._display_history_status(entry.status), status_color),
            )
            for column, item in enumerate(cells):
                self._history_table.setItem(row_index, column, item)

    @staticmethod
    def _format_date(value: object) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return str(value)[:16]

    def _display_history_status(self, status: str) -> str:
        if isinstance(status, ActivityProgress):
            return self._t(ACTIVITY_PROGRESS_LABELS[status])
        return status

    # ---------------------------------------------------------------- settings
    def _import_pack(self) -> None:
        if self._tasks.is_busy("import"):
            return
        path = self._choose_pack_source()
        if path is None:
            return
        self._packs_summary.setText(self._t("validando pack..."))
        self._run_task(
            "import",
            lambda: self._coordinator.inspect_pack(path),
            lambda report: self._confirm_pack_import(path, report),
            self._t("Importar Pack"),
            on_finally=self._refresh_packs,
        )

    def _choose_pack_source(self) -> Path | None:
        choice = self._ask_pack_source_format()
        if choice is None:
            return None
        if choice == "zip":
            selected, _ = QFileDialog.getOpenFileName(
                self,
                self._t("Selecionar pack ZIP"),
                "",
                self._t("Pack ZIP (*.zip);;Todos os arquivos (*)"),
            )
        else:
            selected = QFileDialog.getExistingDirectory(self, self._t("Selecionar pasta do pack"))
        return Path(selected) if selected else None

    def _pack_source_format_dialog(self) -> tuple[QMessageBox, QPushButton, QPushButton, QPushButton]:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self._t("Importar Pack"))
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setText(self._t("Qual é o formato do pack?"))
        dialog.setInformativeText(
            self._t("Escolha ZIP para selecionar um arquivo compactado ou Pasta para selecionar uma pasta de pack.")
        )
        zip_button = dialog.addButton("ZIP", QMessageBox.ButtonRole.ActionRole)
        folder_button = dialog.addButton(self._t("Pasta").upper(), QMessageBox.ButtonRole.ActionRole)
        cancel_button = dialog.addButton(self._t("Cancelar").upper(), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(zip_button)
        dialog.setEscapeButton(cancel_button)
        return dialog, zip_button, folder_button, cancel_button

    def _ask_pack_source_format(self) -> str | None:
        dialog, zip_button, folder_button, _cancel_button = self._pack_source_format_dialog()
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is zip_button:
            return "zip"
        if clicked is folder_button:
            return "folder"
        return None

    def _confirm_pack_import(self, path: Path, report) -> None:
        if report.has_executable_code:
            listed = "\n".join(f"  - {name}" for name in report.executable_files[:8])
            more = "" if len(report.executable_files) <= 8 else self._t("\n  ... e mais {count}", count=len(report.executable_files) - 8)
            answer = QMessageBox.warning(
                self,
                self._t("Importar Pack"),
                self._t(
                    "O pack \"{pack}\" contém código que será compilado e EXECUTADO no seu computador durante a correção (fixtures/references):\n\n{listed}{more}\n\nNão há sandbox: esse código roda com as permissões do seu usuário. Importe apenas packs de fontes em que você confia.\n\nImportar mesmo assim?",
                    pack=report.pack.name,
                    listed=listed,
                    more=more,
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._packs_summary.setText(self._t("importando pack..."))
        self._run_task(
            "import",
            lambda: self._coordinator.import_pack(path),
            self._on_pack_imported,
            self._t("Importar Pack"),
            on_finally=self._refresh_packs,
        )

    def _on_pack_imported(self, pack) -> None:
        QMessageBox.information(self, self._t("Importar Pack"), self._t("Pack importado: {pack}", pack=pack.name))
        self._resume_pending_if_ready()

    def _show_settings(self, section: str | None = None) -> None:
        title = self._t("Configurações").upper() if section is None else f"{self._t('Configurações').upper()} > {self._t(section).upper()}"
        self._set_title_label(self._settings_title, title)
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
            QMessageBox.warning(self, self._t("Documentação"), self._t("Documentação não encontrada nesta instalação."))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(document)))

    @staticmethod
    def _documentation_path() -> Path | None:
        """README from checkout or packaged executable; otherwise the pack contract."""
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
        """Pack contract (single source: resources/pack-contract.md) + active capabilities."""
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
            contract = tr("Documentação do contrato não encontrada nesta instalação.")
        return active + contract

    def _change_workspace(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, self._t("Selecionar nova workspace"))
        if not selected:
            return
        try:
            self._coordinator.change_workspace(Path(selected))
            self._workspace_path = Path(selected)
            self._workspace_label.setText(self._workspace_prompt())
            self._settings_workspace.setText(str(self._workspace_path))
            QMessageBox.information(self, "Workspace", self._t("Workspace atualizada."))
            self._resume_pending_if_ready()
        except Exception as error:
            QMessageBox.warning(self, "Workspace", str(error))

    def _save_editor_setting(self) -> None:
        try:
            self._coordinator.save_editor_command(self._settings_editor.text())
            QMessageBox.information(self, "Editor", self._t("Editor atualizado."))
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
            label.setText(f"● {self._t('não verificado — use [ DETECTAR NOVAMENTE ]')}")
            ui.set_status(label, "pending")
        else:
            label.setText(f"● {self._t('não encontrado — selecione o executável manualmente')}")
            ui.set_status(label, "fail")

    def _show_runtime_cached(self, language: str) -> None:
        self._show_runtime_result(language, self._coordinator.runtime_current_tool(language), cached=True)

    def _redetect_runtime(self, language: str) -> None:
        label = self._runtime_labels[language]
        label.setText(f"● {self._t('detectando...')}")
        ui.set_status(label, "pending")
        self._run_task(
            "runtime",
            lambda: self._coordinator.redetect_runtime(language),
            lambda tool: self._show_runtime_result(language, tool),
            self._coordinator.runtime_display_name(language),
        )

    def _choose_manual_runtime(self, language: str) -> None:
        display_name = self._coordinator.runtime_display_name(language)
        filter_text = self._t("Executáveis (*.exe);;Todos os arquivos (*)") if sys.platform == "win32" else self._t("Todos os arquivos (*)")
        selected, _ = QFileDialog.getOpenFileName(self, self._t("Selecionar {display_name}", display_name=display_name), "", filter_text)
        if not selected:
            return
        path = Path(selected)
        self._runtime_labels[language].setText(f"● {self._t('validando...')}")

        def done(tool: object) -> None:
            self._show_runtime_result(language, self._coordinator.runtime_current_tool(language))
            QMessageBox.information(self, display_name, self._t("{display_name} atualizado.", display_name=display_name))
            self._resume_pending_if_ready()

        self._run_task(
            "runtime",
            lambda: self._coordinator.save_manual_runtime(language, path),
            done,
            display_name,
            on_finally=lambda: self._show_runtime_cached(language),
        )

    def _editor_preset_changed(self, _index: int) -> None:
        label = str(self._editor_combo.currentData() or self._editor_combo.currentText())
        if label == "Outro...":
            self._browse_editor()
            return
        resolved = self._coordinator.resolve_known_editor(label)
        if resolved is not None:
            self._settings_editor.setText(resolved)

    def _browse_editor(self) -> None:
        filter_text = self._t("Executáveis (*.exe);;Todos os arquivos (*)") if sys.platform == "win32" else self._t("Todos os arquivos (*)")
        selected, _ = QFileDialog.getOpenFileName(self, self._t("Selecionar executável do editor"), "", filter_text)
        if selected:
            self._settings_editor.setText(str(Path(selected)))

    def _detect_editor_automatically(self) -> None:
        # Explicit "Detectar automaticamente" action: re-run the same known-editor
        # resolution already used by the preset combo (`resolve_known_editor`),
        # without requiring the person to touch the preset selector.
        #
        # If the currently selected preset is a known one, try it first -- this is
        # the direct redetection case. Otherwise (or if that preset is no longer
        # found), fall back to trying every known editor and filling in the first
        # one that resolves, keeping the preset combo in sync with the result.
        current = str(self._editor_combo.currentData() or self._editor_combo.currentText())
        ordered_labels = list(self._coordinator.known_editor_labels())
        if current in ordered_labels:
            ordered_labels.remove(current)
            ordered_labels.insert(0, current)

        for label in ordered_labels:
            resolved = self._coordinator.resolve_known_editor(label)
            if resolved is None:
                continue
            index = self._editor_combo.findData(label)
            if index >= 0:
                self._editor_combo.blockSignals(True)
                self._editor_combo.setCurrentIndex(index)
                self._editor_combo.blockSignals(False)
            self._settings_editor.setText(resolved)
            QMessageBox.information(
                self, "Editor", self._t("{editor} detectado automaticamente.", editor=self._t(label))
            )
            return

        QMessageBox.warning(self, "Editor", self._t("Nenhum editor conhecido foi encontrado automaticamente."))

    def _choose_manual_compiler(self) -> None:
        language = self._first_runtime_language()
        if language is not None:
            self._choose_manual_runtime(language)

    def _first_runtime_language(self) -> str | None:
        return next(iter(self._runtime_labels), None)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        # Let in-progress grading/import finish writing before closing.
        self._tasks.wait(15_000)
        super().closeEvent(event)

    def _back_from_exercise(self) -> None:
        self._go(self._exam_page if self._mode == "exam" else self._training_page)
