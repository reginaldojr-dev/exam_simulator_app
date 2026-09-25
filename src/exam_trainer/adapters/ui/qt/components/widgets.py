"""Componentes reutilizáveis.

Telas criam widgets por aqui e só escolhem o *papel* (variant/role/status).
A aparência vem do QSS do tema ativo.
"""

from __future__ import annotations

from collections.abc import Callable
from html import escape

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

BUTTON_VARIANTS = ("default", "primary", "start", "menu", "tab", "option", "danger", "small")
STATUSES = ("pass", "fail", "pending", "muted", "")


def repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def button(text: str, handler: Callable[[], None] | None = None, variant: str = "default") -> QPushButton:
    if variant not in BUTTON_VARIANTS:
        raise ValueError(f"variant desconhecida: {variant}")
    widget = QPushButton(text)
    widget.setProperty("variant", variant)
    widget.setProperty("baseText", text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if handler is not None:
        widget.clicked.connect(handler)
    return widget


def label(text: str = "", role: str | None = None, status: str | None = None, wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    if role:
        widget.setProperty("role", role)
    if status:
        widget.setProperty("status", status)
    widget.setWordWrap(wrap)
    return widget


def title_label(text: str = "") -> QLabel:
    widget = label(text, role="title")
    widget.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    return widget


def section_label(text: str) -> QLabel:
    return label(text, role="section")


def set_status(widget: QWidget, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"status desconhecido: {status}")
    widget.setProperty("status", status or None)
    repolish(widget)


def card(status: str | None = None) -> QFrame:
    frame = QFrame()
    frame.setProperty("role", "card")
    if status:
        frame.setProperty("status", status)
    return frame


class OptionButton(QPushButton):
    """Opção clicável de linha inteira: `[x] level0`, `( ) Todos`.

    - kind="check": marcador [x] / [ ]
    - kind="radio": marcador (•) / ( ); exclusividade via QButtonGroup
    O texto *sem* marcador fica em `value`.
    """

    def __init__(self, value: str, kind: str = "check", checked: bool = False, caption: str = "") -> None:
        super().__init__()
        self._value = value
        self._kind = kind
        self._caption = caption
        self.setProperty("variant", "option")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._sync)
        self.setChecked(checked)
        self._sync()

    @property
    def value(self) -> str:
        return self._value

    def _sync(self, *_: object) -> None:
        on, off = ("[x]", "[ ]") if self._kind == "check" else ("(•)", "( )")
        text = f"{on if self.isChecked() else off} {self._value}"
        if self._caption:
            text += f"    {self._caption}"
        self.setProperty("baseText", text)
        self.setText(text)


class HintBar(QFrame):
    """Rodapé com atalhos de teclado: [1-4] navegar · [Esc] voltar."""

    def __init__(self, hints: list[tuple[str, str]]) -> None:
        super().__init__()
        self.setProperty("role", "hintbar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(18)
        for key, text in hints:
            layout.addWidget(label(f"[{key}] {text}", role="hint"))
        layout.addStretch(1)


class FeedbackBanner(QFrame):
    """Faixa de resultado (PASS/FAIL) com animação curta de entrada."""

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("role", "banner")
        self._icon = label("", role="headline")
        self._text = label("", wrap=True)
        self._actions = QHBoxLayout()
        self._actions.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self._icon)
        top.addWidget(self._text, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addLayout(self._actions)
        self._animation: QPropertyAnimation | None = None
        self.hide()

    @property
    def text(self) -> str:
        return self._text.text()

    @property
    def headline(self) -> str:
        return self._icon.text()

    def show_result(self, status: str, headline: str, text: str, actions: list[QPushButton] | None = None, animate: bool = True) -> None:
        self.setProperty("status", status)
        set_status(self._icon, status)
        self._icon.setText(headline)
        self._text.setText(text)
        while self._actions.count():
            item = self._actions.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        for action in actions or []:
            self._actions.addWidget(action)
        self._actions.addStretch(1)
        repolish(self)
        self.show()
        if animate:
            self._fade_in()

    def clear(self) -> None:
        self.hide()
        self.setProperty("status", None)

    def _fade_in(self) -> None:
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(260)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: self.setGraphicsEffect(None))
        self._animation = animation
        animation.start()


class SubjectMarkdownView(QTextEdit):
    """Read-only subject viewer that renders pack Markdown safely enough for UI use."""

    EMPTY_MESSAGE = "_Subject vazio._"

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setProperty("role", "subject")
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().setDocumentMargin(16)
        self.document().setDefaultStyleSheet(self._document_stylesheet())

    def set_subject_markdown(self, markdown: str) -> None:
        content = markdown if markdown.strip() else self.EMPTY_MESSAGE
        self.setMarkdown(self._escape_html(content))
        self.moveCursor(QTextCursor.MoveOperation.Start)

    @staticmethod
    def _escape_html(markdown: str) -> str:
        # Pack subjects are Markdown, not trusted HTML. QTextDocument does not run
        # JavaScript, but escaping keeps raw HTML from becoming active rich text.
        return escape(markdown, quote=False)

    @staticmethod
    def _document_stylesheet() -> str:
        return """
body {
  margin: 0;
  font-size: 1em;
  line-height: 1.42;
}
h1 {
  margin: 0 0 8px 0;
  font-size: 1.12em;
  font-weight: 800;
}
h2 {
  margin: 16px 0 6px 0;
  padding-top: 10px;
  border-top: 1px solid #2f5f3b;
  font-size: 1.02em;
  font-weight: 800;
  letter-spacing: 0.04em;
}
h3 {
  margin: 12px 0 5px 0;
  padding-top: 8px;
  border-top: 1px solid #24472d;
  font-size: 0.98em;
  font-weight: 750;
}
p {
  margin: 7px 0;
}
ul, ol {
  margin-top: 5px;
  margin-bottom: 9px;
}
li {
  margin-top: 3px;
  margin-bottom: 3px;
}
code {
  font-family: Consolas, "Cascadia Mono", "JetBrains Mono", monospace;
  white-space: pre-wrap;
}
pre {
  margin: 8px 0 12px 0;
  padding: 9px 10px;
  border: 1px solid #24472d;
  white-space: pre-wrap;
}
"""


def fade_to(stack: QStackedWidget, page: QWidget, animate: bool = True) -> None:
    """Troca de tela com fade curto; remove o efeito ao final (não pesa o repaint)."""
    if stack.currentWidget() is page:
        return
    stack.setCurrentWidget(page)
    if not animate:
        return
    effect = QGraphicsOpacityEffect(page)
    page.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", page)
    animation.setDuration(150)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda: page.setGraphicsEffect(None))
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
