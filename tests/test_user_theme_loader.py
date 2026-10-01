"""Fase 5: validates `UserThemeLoader`, which discovers `theme.json` files
under the user's themes folder and registers the valid ones into a
`ThemeRegistry`.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rankeddojo.adapters.theme.user_theme_loader import UserThemeLoader
from rankeddojo.adapters.ui.qt.theme.registry import ThemeRegistry
from rankeddojo.adapters.ui.qt.theme.themes import TERMINAL, THEMES


def _write_theme(folder: Path, data: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "theme.json").write_text(json.dumps(data), encoding="utf-8")


def _fresh_registry() -> ThemeRegistry:
    """An isolated registry seeded with the same internal themes as the app,
    so tests never mutate the real process-wide THEME_REGISTRY singleton."""
    return ThemeRegistry(THEMES.values())


class UserThemeLoaderTest(unittest.TestCase):
    def test_valid_external_theme_loads_and_registers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            themes_dir = Path(tmp) / "themes"
            _write_theme(
                themes_dir / "my-theme",
                {
                    "schema_version": 1,
                    "id": "my-theme",
                    "name": "My Theme",
                    "tokens": {"accent": "#00ff00"},
                },
            )
            registry = _fresh_registry()
            loader = UserThemeLoader(base=TERMINAL)

            loader.load_into(registry, themes_dir)

        self.assertTrue(registry.has("my-theme"))
        self.assertEqual(registry.get("my-theme").accent, "#00ff00")
        self.assertEqual(loader.load_errors, {})

    def test_invalid_theme_is_skipped_without_crash_and_others_still_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            themes_dir = Path(tmp) / "themes"
            (themes_dir / "broken").mkdir(parents=True)
            (themes_dir / "broken" / "theme.json").write_text("{not json", encoding="utf-8")
            _write_theme(
                themes_dir / "valid-one",
                {"schema_version": 1, "id": "valid-one", "name": "Valid One", "tokens": {}},
            )
            registry = _fresh_registry()
            loader = UserThemeLoader(base=TERMINAL)

            loader.load_into(registry, themes_dir)  # must not raise

        self.assertTrue(registry.has("valid-one"))
        self.assertFalse(registry.has("broken"))
        self.assertIn(str(themes_dir / "broken"), loader.load_errors)

    def test_external_theme_never_overrides_a_builtin_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            themes_dir = Path(tmp) / "themes"
            _write_theme(
                themes_dir / "fake-terminal",
                {
                    "schema_version": 1,
                    "id": "terminal",
                    "name": "Fake Terminal",
                    "tokens": {"accent": "#ff0000"},
                },
            )
            registry = _fresh_registry()
            loader = UserThemeLoader(base=TERMINAL)

            loader.load_into(registry, themes_dir)

        # The real built-in terminal theme is untouched.
        self.assertIs(registry.get("terminal"), THEMES["terminal"])
        self.assertIn(str(themes_dir / "fake-terminal"), loader.load_errors)

    def test_duplicate_external_ids_are_deterministic_first_folder_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            themes_dir = Path(tmp) / "themes"
            _write_theme(
                themes_dir / "aaa-first",
                {"schema_version": 1, "id": "dup", "name": "First", "tokens": {"accent": "#111111"}},
            )
            _write_theme(
                themes_dir / "zzz-second",
                {"schema_version": 1, "id": "dup", "name": "Second", "tokens": {"accent": "#222222"}},
            )
            registry = _fresh_registry()
            loader = UserThemeLoader(base=TERMINAL)

            loader.load_into(registry, themes_dir)

        self.assertEqual(registry.get("dup").accent, "#111111")
        self.assertEqual(registry.get("dup").name, "First")
        self.assertIn(str(themes_dir / "zzz-second"), loader.load_errors)

    def test_folder_without_theme_json_is_silently_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            themes_dir = Path(tmp) / "themes"
            not_a_theme = themes_dir / "not-a-theme"
            not_a_theme.mkdir(parents=True)
            (not_a_theme / "readme.txt").write_text("hi", encoding="utf-8")
            registry = _fresh_registry()
            loader = UserThemeLoader(base=TERMINAL)

            loader.load_into(registry, themes_dir)

        self.assertEqual(loader.load_errors, {})
        self.assertEqual(registry.keys(), tuple(THEMES.keys()))

    def test_missing_themes_dir_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = _fresh_registry()
            loader = UserThemeLoader(base=TERMINAL)

            loader.load_into(registry, Path(tmp) / "does-not-exist")

        self.assertEqual(registry.keys(), tuple(THEMES.keys()))
        self.assertEqual(loader.load_errors, {})

    def test_discovery_order_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            themes_dir = Path(tmp) / "themes"
            for name in ("bravo", "alpha", "charlie"):
                _write_theme(
                    themes_dir / name,
                    {"schema_version": 1, "id": name, "name": name.title(), "tokens": {}},
                )

            first = _fresh_registry()
            UserThemeLoader(base=TERMINAL).load_into(first, themes_dir)
            second = _fresh_registry()
            UserThemeLoader(base=TERMINAL).load_into(second, themes_dir)

        self.assertEqual(first.keys(), second.keys())

    def test_symlinked_theme_folder_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real_dir = Path(tmp) / "real-themes"
            themes_dir = Path(tmp) / "themes"
            _write_theme(
                real_dir / "linked-theme",
                {"schema_version": 1, "id": "linked-theme", "name": "Linked", "tokens": {}},
            )
            themes_dir.mkdir(parents=True)
            link = themes_dir / "linked-theme"
            try:
                link.symlink_to(real_dir / "linked-theme", target_is_directory=True)
            except OSError:
                self.skipTest("symlinks are not supported in this environment")

            registry = _fresh_registry()
            loader = UserThemeLoader(base=TERMINAL)
            loader.load_into(registry, themes_dir)

        self.assertFalse(registry.has("linked-theme"))


if __name__ == "__main__":
    unittest.main()
