"""Sistema de temas da UI Qt: tokens -> ThemeRegistry -> QSS -> ThemeManager."""

from exam_trainer.adapters.ui.qt.theme.manager import ThemeManager
from exam_trainer.adapters.ui.qt.theme.qss import build_stylesheet
from exam_trainer.adapters.ui.qt.theme.registry import ThemeRegistry
from exam_trainer.adapters.ui.qt.theme.themes import DEFAULT_THEME_KEY, THEME_REGISTRY, THEMES, get_theme
from exam_trainer.adapters.ui.qt.theme.tokens import ThemeTokens

__all__ = [
    "DEFAULT_THEME_KEY",
    "THEME_REGISTRY",
    "THEMES",
    "ThemeManager",
    "ThemeRegistry",
    "ThemeTokens",
    "build_stylesheet",
    "get_theme",
]
