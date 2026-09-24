from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from exam_trainer.adapters.ui.qt.theme.qss import build_stylesheet
from exam_trainer.adapters.ui.qt.theme.themes import THEMES, get_theme
from exam_trainer.adapters.ui.qt.theme.tokens import ThemeTokens


class ThemeManager(QObject):
    """Único ponto que sabe qual tema está ativo.

    Telas pedem cores via `color("success")` e se inscrevem em `theme_changed`
    quando desenham algo fora do QSS (ex.: itens de tabela).
    """

    theme_changed = Signal(object)

    def __init__(self, theme_key: str | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tokens = get_theme(theme_key)
        self._targets: list[QWidget] = []

    @property
    def tokens(self) -> ThemeTokens:
        return self._tokens

    @staticmethod
    def available() -> list[ThemeTokens]:
        return list(THEMES.values())

    def stylesheet(self) -> str:
        return build_stylesheet(self._tokens)

    def color(self, token: str) -> QColor:
        return QColor(self._tokens.get(token))

    def apply(self, widget: QWidget) -> None:
        if widget not in self._targets:
            self._targets.append(widget)
            widget.destroyed.connect(lambda *_: self._forget(widget))
        widget.setStyleSheet(self.stylesheet())

    def set_theme(self, key: str) -> None:
        tokens = get_theme(key)
        if tokens is self._tokens:
            return
        self._tokens = tokens
        qss = self.stylesheet()
        for widget in list(self._targets):
            widget.setStyleSheet(qss)
        self.theme_changed.emit(tokens)

    def _forget(self, widget: QWidget) -> None:
        try:
            self._targets.remove(widget)
        except ValueError:
            pass
