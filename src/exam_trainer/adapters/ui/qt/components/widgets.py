"""Componentes reutilizáveis.

Telas criam widgets por aqui e só escolhem o *papel* (variant/role/status).
A aparência vem do QSS do tema ativo.
"""

from __future__ import annotations

from collections.abc import Callable

from markdown_it import MarkdownIt

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
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


class SubjectMarkdownView(QTextBrowser):
    """Read-only subject viewer.

    Pipeline: subject.md -> markdown-it-py (CommonMark, raw HTML disabled)
    -> sandboxed HTML -> QTextBrowser.setHtml() -> CSS centralized here.

    Raw HTML in the source Markdown is never parsed as HTML: markdown-it-py
    is configured with ``html=False``, so any literal "<", ">" or "&" the
    author typed (inside or outside fenced/inline code) is escaped by the
    Markdown renderer into HTML entities in the generated markup. Qt's HTML
    engine then decodes those entities back to the literal character when it
    displays the text -- the same two-step "escape for transport, decode for
    display" that any HTML consumer does. That is what makes both guarantees
    hold at once: a subject containing "<script>alert(1)</script>" shows up
    as plain, inert text (never becomes an active tag), and a fenced shell
    example containing "$> ./program" or C code containing "a < b && c > d"
    renders with the literal characters, not "&gt;"/"&lt;"/"&amp;".
    """

    EMPTY_MESSAGE = "_Subject vazio._"

    _renderer = MarkdownIt(
        "commonmark",
        {"html": False, "linkify": False, "typographer": False},
    )

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setProperty("role", "subject")
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.document().setDocumentMargin(20)
        self.document().setDefaultStyleSheet(self._document_stylesheet())

    def set_subject_markdown(self, markdown: str) -> None:
        content = markdown if markdown.strip() else self.EMPTY_MESSAGE
        self.setHtml(self._renderer.render(content))
        self.moveCursor(QTextCursor.MoveOperation.Start)

    @staticmethod
    def _document_stylesheet() -> str:
        return """
body {
  margin: 0;
  font-size: 1.18em;
  line-height: 1.72;
}
h1, h2, h3, h4 {
  font-weight: 800;
  color: #a6f7a6;
}
h1 {
  margin: 8px 0 20px 0;
  font-size: 1.55em;
  color: #b8ffb8;
}
h2 {
  margin: 32px 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #2f5f3b;
  font-size: 1.32em;
  font-weight: 800;
  letter-spacing: 0.04em;
}
h3 {
  margin: 24px 0 12px 0;
  font-size: 1.16em;
  font-weight: 750;
  color: #9be89b;
}
p {
  margin: 12px 0 18px 0;
}
ul, ol {
  margin: 12px 0 18px 30px;
  padding: 0;
}
li {
  margin: 6px 0 10px 0;
}
code {
  font-family: Consolas, "Cascadia Mono", "JetBrains Mono", monospace;
  font-size: 1.02em;
  background-color: #102010;
  color: #e4ffe4;
  border: 1px solid #24472d;
  padding: 2px 6px;
  white-space: pre;
}
pre {
  margin: 20px 0 24px 0;
  padding: 16px 18px;
  background-color: #071307;
  border: 1px solid #2f5f3b;
  line-height: 1.5;
  white-space: pre;
}
pre code {
  background-color: transparent;
  border: none;
  padding: 0;
}
blockquote {
  margin: 14px 0 18px 18px;
  padding-left: 12px;
  border-left: 2px solid #2f5f3b;
}
hr {
  margin: 22px 0;
  color: #24472d;
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
