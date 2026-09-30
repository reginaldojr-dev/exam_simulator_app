"""Theme registry: the single source of truth for which themes exist.

Pure Python, no PySide6 -- same rule as `tokens.py`/`themes.py`, so this stays
importable and testable without a Qt platform plugin.
"""

from __future__ import annotations

from collections.abc import Iterable

from exam_trainer.adapters.ui.qt.theme.tokens import ThemeTokens


class DuplicateThemeError(ValueError):
    """Raised when two themes are registered under the same key."""


class ThemeRegistry:
    """key -> ThemeTokens. Registration, lookup, listing, and default fallback."""

    def __init__(self, themes: Iterable[ThemeTokens] = ()) -> None:
        self._themes: dict[str, ThemeTokens] = {}
        self._order: list[str] = []
        for theme in themes:
            self.register(theme)

    def register(self, theme: ThemeTokens) -> None:
        if theme.key in self._themes:
            raise DuplicateThemeError(f"Theme already registered: {theme.key}.")
        self._themes[theme.key] = theme
        self._order.append(theme.key)

    def get(self, key: str) -> ThemeTokens | None:
        return self._themes.get(key)

    def has(self, key: str) -> bool:
        return key in self._themes

    def keys(self) -> tuple[str, ...]:
        return tuple(self._order)

    def themes(self) -> tuple[ThemeTokens, ...]:
        return tuple(self._themes[key] for key in self._order)

    def resolve(self, key: str | None, default_key: str) -> ThemeTokens:
        """Return the theme for `key`, falling back to `default_key` for an unknown or missing key."""
        return self._themes.get(key or default_key, self._themes[default_key])
