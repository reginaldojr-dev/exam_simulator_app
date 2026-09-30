"""Discovers `theme.json` definitions under the user's themes folder and
registers the valid ones into a `ThemeRegistry`. See
`resources/theme-contract.md`.
"""

from __future__ import annotations

from pathlib import Path

from rankeddojo.adapters.theme.theme_contract import JsonThemeLoader, ThemeDefinitionError
from rankeddojo.adapters.ui.qt.theme.registry import ThemeRegistry
from rankeddojo.adapters.ui.qt.theme.tokens import ThemeTokens

THEME_DEFINITION_FILENAME = "theme.json"


class UserThemeLoader:
    """Loads every valid `theme.json` under a themes folder into a `ThemeRegistry`.

    - Deterministic: folders are visited in sorted order.
    - A failure in one theme never stops the others from loading.
    - An external theme whose id already exists -- a built-in theme or an
      external theme loaded earlier in this same pass -- is rejected, never
      silently overriding what is already registered. Only the registry's
      public API (`has`/`register`) is used; nothing here mutates it
      directly.
    """

    def __init__(self, base: ThemeTokens, theme_loader: JsonThemeLoader | None = None) -> None:
        self._base = base
        self._theme_loader = theme_loader or JsonThemeLoader()
        self._load_errors: dict[str, str] = {}

    @property
    def load_errors(self) -> dict[str, str]:
        """Theme folders that failed to load (folder path -> reason), from the most recent `load_into` call."""
        return dict(self._load_errors)

    def load_into(self, registry: ThemeRegistry, themes_dir: Path) -> None:
        self._load_errors = {}
        for root in self._theme_roots(themes_dir):
            self._load_one(registry, root)

    def _load_one(self, registry: ThemeRegistry, root: Path) -> None:
        definition_path = root / THEME_DEFINITION_FILENAME
        if not definition_path.is_file():
            # Not a theme folder (no theme.json inside): silently skipped,
            # same as LocalPackCatalog does for a folder with no pack.json.
            return
        try:
            tokens = self._theme_loader.load(definition_path, base=self._base)
        except ThemeDefinitionError as error:
            self._load_errors[str(root)] = str(error)
            return
        if registry.has(tokens.key):
            self._load_errors[str(root)] = (
                f"Theme id '{tokens.key}' already exists (built-in or already loaded); "
                "external themes never override an existing one."
            )
            return
        registry.register(tokens)

    @staticmethod
    def _theme_roots(themes_dir: Path) -> list[Path]:
        if not themes_dir.is_dir():
            return []
        return [
            child
            for child in sorted(themes_dir.iterdir())
            if child.is_dir() and not child.is_symlink()
        ]
