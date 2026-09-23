"""Cursor piscante centralizado.

Um único QTimer para a janela inteira. Regras:
- só o título da tela ativa pisca;
- no máximo UM item pisca além do título: o botão com hover/foco ou, se não houver,
  o botão START da tela (alvo "ocioso");
- ao entrar numa tela, o título é digitado letra a letra (typewriter) usando o mesmo timer.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

BASE_TEXT = "baseText"


class CursorController(QObject):
    BLINK_MS = 530
    TYPE_MS = 28

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._on = True
        self._enabled = True
        self._animations = True
        self._char = "_"
        self._titles: dict[QLabel, str] = {}
        self._tracked: set[QPushButton] = set()
        self._idle: dict[QWidget, QPushButton] = {}
        self._scope: QWidget | None = None
        self._focus: QPushButton | None = None
        self._lit: QPushButton | None = None
        self._typing: QLabel | None = None
        self._typed = 0
        self._timer.start(self.BLINK_MS)

    # ---------- configuração ----------
    def configure(self, *, enabled: bool, animations: bool, cursor_char: str) -> None:
        self._enabled = enabled
        self._animations = animations
        self._char = cursor_char or "_"
        self._render()

    @property
    def timer(self) -> QTimer:
        return self._timer

    # ---------- registro ----------
    def register_title(self, label: QLabel, text: str) -> None:
        self._titles[label] = text
        label.setText(self._title_text(label, text))

    def set_title(self, label: QLabel, text: str) -> None:
        self._titles[label] = text
        if self._typing is label:
            self._typing = None
            self._timer.setInterval(self.BLINK_MS)
        label.setText(self._title_text(label, text))

    def track(self, button: QPushButton) -> None:
        if button in self._tracked:
            return
        self._tracked.add(button)
        if button.property(BASE_TEXT) is None:
            button.setProperty(BASE_TEXT, button.text())
        button.installEventFilter(self)

    def set_button_text(self, button: QPushButton, text: str) -> None:
        button.setProperty(BASE_TEXT, text)
        button.setText(self._button_text(button, lit=button is self._lit))

    def set_idle_target(self, page: QWidget, button: QPushButton) -> None:
        self.track(button)
        self._idle[page] = button

    def enter_page(self, page: QWidget) -> None:
        self._scope = page
        self._focus = None
        self._restore(self._lit)
        self._lit = None
        title = next((label for label in self._titles if page.isAncestorOf(label) and self._titles[label]), None)
        if title is not None and self._animations:
            self._typing = title
            self._typed = 0
            title.setText("")
            self._timer.setInterval(self.TYPE_MS)
        self._render()

    # ---------- eventos ----------
    def eventFilter(self, source: QObject, event: QEvent) -> bool:
        # Na destruição da janela o Qt ainda entrega Leave/FocusOut aos botões
        # enquanto labels/estado já foram liberados: isso não pode virar traceback.
        try:
            self._handle_event(source, event)
        except (AttributeError, RuntimeError):
            pass
        return False

    def _handle_event(self, source: QObject, event: QEvent) -> None:
        if not (isinstance(source, QPushButton) and source in self._tracked):
            return
        kind = event.type()
        if kind in (QEvent.Type.Enter, QEvent.Type.FocusIn):
            self._focus = source
            self._render()
        elif kind in (QEvent.Type.Leave, QEvent.Type.FocusOut):
            if self._focus is source:
                focused = QApplication.focusWidget()
                self._focus = focused if isinstance(focused, QPushButton) and focused in self._tracked and focused is not source else None
                self._render()

    # ---------- render ----------
    def _tick(self) -> None:
        if self._typing is not None:
            label = self._typing
            text = self._titles.get(label, "")
            self._typed += 1
            if self._typed >= len(text):
                self._typing = None
                self._timer.setInterval(self.BLINK_MS)
                self._on = True
                label.setText(self._title_text(label, text))
            else:
                label.setText(text[: self._typed] + "█")
            return
        self._on = not self._on
        self._render()

    def _render(self) -> None:
        for label, text in self._titles.items():
            if label is self._typing:
                continue
            label.setText(self._title_text(label, text))
        target = self._current_target()
        if target is not self._lit:
            self._restore(self._lit)
            self._lit = target
        if target is not None:
            target.setText(self._button_text(target, lit=True))

    def _current_target(self) -> QPushButton | None:
        if not self._enabled:
            return None
        if self._focus is not None and self._in_scope(self._focus) and self._focus.isEnabled():
            return self._focus
        if self._scope is not None:
            idle = self._idle.get(self._scope)
            if idle is not None and idle.isVisible() and idle.isEnabled():
                return idle
        return None

    def _in_scope(self, widget: QWidget) -> bool:
        return self._scope is None or self._scope.isAncestorOf(widget)

    def _restore(self, button: QPushButton | None) -> None:
        if button is not None:
            button.setText(self._button_text(button, lit=False))

    def _title_text(self, label: QLabel, text: str) -> str:
        if not text:
            return ""
        blinking = self._enabled and (self._scope is None or self._scope.isAncestorOf(label))
        if not blinking:
            return text
        return f"{text} {self._char if self._on else ' '}"

    def _button_text(self, button: QPushButton, lit: bool) -> str:
        base = button.property(BASE_TEXT)
        base = base if isinstance(base, str) else button.text()
        if not lit or not self._enabled:
            return base
        return f"{base}{self._char if self._on else ' '}"
