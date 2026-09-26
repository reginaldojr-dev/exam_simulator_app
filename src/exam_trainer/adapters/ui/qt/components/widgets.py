"""Componentes reutilizáveis.

Telas criam widgets por aqui e só escolhem o *papel* (variant/role/status).
A aparência vem do QSS do tema ativo.
"""

from __future__ import annotations

from collections.abc import Callable
from html import escape

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QFont, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextOption
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
        self.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.document().setDocumentMargin(20)
        self.document().setDefaultStyleSheet(self._document_stylesheet())

    def set_subject_markdown(self, markdown: str) -> None:
        content = markdown if markdown.strip() else self.EMPTY_MESSAGE
        self.setMarkdown(self._escape_html(content))
        self._apply_markdown_document_styles()
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
  line-height: 1.58;
}
h1 {
  margin: 4px 0 14px 0;
  font-size: 1.22em;
  font-weight: 800;
  color: #b8ffb8;
}
h2 {
  margin: 24px 0 12px 0;
  padding-top: 12px;
  border-top: 1px solid #2f5f3b;
  font-size: 1.08em;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #a6f7a6;
}
h3 {
  margin: 18px 0 9px 0;
  padding-top: 8px;
  border-top: 1px solid #24472d;
  font-size: 1.01em;
  font-weight: 750;
  color: #9be89b;
}
p {
  margin: 9px 0 13px 0;
}
ul, ol {
  margin: 9px 0 14px 24px;
}
li {
  margin: 4px 0 6px 0;
}
code {
  font-family: Consolas, "Cascadia Mono", "JetBrains Mono", monospace;
  background-color: #102010;
  color: #e4ffe4;
  border: 1px solid #24472d;
  padding: 1px 4px;
  white-space: pre;
}
pre {
  margin: 13px 0 17px 0;
  padding: 12px 14px;
  background-color: #071307;
  border: 1px solid #2f5f3b;
  white-space: pre;
}
blockquote {
  margin: 12px 0 14px 18px;
  padding-left: 12px;
  border-left: 2px solid #2f5f3b;
}
hr {
  margin: 18px 0;
  color: #24472d;
}
"""

    def _apply_markdown_document_styles(self) -> None:
        """Normalize Qt Markdown's compact inline block formats.

        QTextEdit.setMarkdown() preserves Markdown semantics, but it imports
        paragraphs with tight inline margins and code blocks with zero vertical
        space. The document stylesheet is not enough to reliably override those
        generated block formats, so we adjust the QTextDocument formats directly.
        """

        document = self.document()
        base_size = max(self.font().pointSizeF(), 10.0)
        code_background = QColor("#071307")
        inline_code_background = QColor("#102010")
        code_foreground = QColor("#e4ffe4")
        heading_foreground = QColor("#a6f7a6")

        code_blocks: set[int] = set()
        block = document.begin()
        while block.isValid():
            if block.blockFormat().nonBreakableLines():
                code_blocks.add(block.blockNumber())
            block = block.next()

        block = document.begin()
        while block.isValid():
            block_format = block.blockFormat()
            heading_level = block_format.headingLevel()
            is_code_block = block.blockNumber() in code_blocks
            is_list_item = block.textList() is not None

            if is_code_block:
                block_format.setTopMargin(2)
                block_format.setBottomMargin(2)
                block_format.setLeftMargin(10)
                block_format.setRightMargin(10)
                block_format.setLineHeight(120.0, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
                block_format.setBackground(code_background)
                previous_is_code = block.previous().isValid() and block.previous().blockNumber() in code_blocks
                next_is_code = block.next().isValid() and block.next().blockNumber() in code_blocks
                if not previous_is_code:
                    block_format.setTopMargin(14)
                if not next_is_code:
                    block_format.setBottomMargin(16)
            elif heading_level == 1:
                block_format.setTopMargin(6)
                block_format.setBottomMargin(16)
            elif heading_level == 2:
                block_format.setTopMargin(24)
                block_format.setBottomMargin(12)
            elif heading_level == 3:
                block_format.setTopMargin(18)
                block_format.setBottomMargin(10)
            elif is_list_item:
                block_format.setTopMargin(4)
                block_format.setBottomMargin(7)
                block_format.setLeftMargin(12)
            else:
                block_format.setTopMargin(7)
                block_format.setBottomMargin(12)

            cursor = QTextCursor(block)
            cursor.setBlockFormat(block_format)

            if heading_level:
                char_format = QTextCharFormat()
                char_format.setForeground(heading_foreground)
                char_format.setFontWeight(QFont.Weight.Bold)
                if heading_level == 1:
                    char_format.setFontPointSize(base_size * 1.2)
                elif heading_level == 2:
                    char_format.setFontPointSize(base_size * 1.1)
                elif heading_level == 3:
                    char_format.setFontPointSize(base_size * 1.03)
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                cursor.mergeCharFormat(char_format)

            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    fragment_format = fragment.charFormat()
                    family = fragment_format.font().family().lower()
                    is_code_fragment = fragment_format.font().fixedPitch() or "mono" in family
                    if is_code_fragment or is_code_block:
                        code_format = QTextCharFormat()
                        code_format.setFontFamilies(["Consolas", "Cascadia Mono", "JetBrains Mono", "monospace"])
                        code_format.setForeground(code_foreground)
                        code_format.setBackground(code_background if is_code_block else inline_code_background)
                        code_cursor = QTextCursor(document)
                        code_cursor.setPosition(fragment.position())
                        code_cursor.setPosition(fragment.position() + fragment.length(), QTextCursor.MoveMode.KeepAnchor)
                        code_cursor.mergeCharFormat(code_format)
                iterator += 1

            block = block.next()


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
