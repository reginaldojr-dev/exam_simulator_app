"""Fase 5: validates `JsonThemeLoader`, the declarative `theme.json` parser.

Pure Python -- no PySide6, no Qt platform plugin needed to run this file.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rankeddojo.adapters.theme.theme_contract import JsonThemeLoader, ThemeDefinitionError
from rankeddojo.adapters.ui.qt.theme.themes import TERMINAL
from rankeddojo.adapters.ui.qt.theme.tokens import ThemeTokens


def _write(tmp_dir: str, data: dict) -> Path:
    path = Path(tmp_dir) / "theme.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _write_raw(tmp_dir: str, text: str) -> Path:
    path = Path(tmp_dir) / "theme.json"
    path.write_text(text, encoding="utf-8")
    return path


VALID = {
    "schema_version": 1,
    "id": "my-theme",
    "name": "My Theme",
    "author": "someone",
    "version": "1.0",
    "tokens": {
        "background": "#111111",
        "accent_secondary": "#abcdef",
        "font_mono": "Fira Code, monospace",
        "radius": 12,
        "blink_cursor": False,
    },
}


class JsonThemeLoaderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.loader = JsonThemeLoader()

    def test_valid_full_theme_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, VALID)
            tokens = self.loader.load(path, base=TERMINAL)

        self.assertIsInstance(tokens, ThemeTokens)
        self.assertEqual(tokens.key, "my-theme")
        self.assertEqual(tokens.name, "My Theme")
        self.assertEqual(tokens.background, "#111111")

    def test_partial_theme_inherits_missing_tokens_from_base(self) -> None:
        partial = {
            "schema_version": 1,
            "id": "partial-theme",
            "name": "Partial Theme",
            "tokens": {"accent": "#00ff00"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, partial)
            tokens = self.loader.load(path, base=TERMINAL)

        self.assertEqual(tokens.accent, "#00ff00")
        # Every other field came from the base, untouched.
        self.assertEqual(tokens.surface, TERMINAL.surface)
        self.assertEqual(tokens.border, TERMINAL.border)
        self.assertEqual(tokens.font_body, TERMINAL.font_body)
        self.assertEqual(tokens.font_size, TERMINAL.font_size)
        self.assertEqual(tokens.blink_cursor, TERMINAL.blink_cursor)

    def test_accent_secondary_and_font_mono_work_externally(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, VALID)
            tokens = self.loader.load(path, base=TERMINAL)

        self.assertEqual(tokens.accent_secondary, "#abcdef")
        self.assertEqual(tokens.font_mono, "Fira Code, monospace")

    def test_author_and_version_are_optional(self) -> None:
        minimal = {
            "schema_version": 1,
            "id": "minimal-theme",
            "name": "Minimal Theme",
            "tokens": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, minimal)
            tokens = self.loader.load(path, base=TERMINAL)

        self.assertEqual(tokens.key, "minimal-theme")
        # Empty tokens object -> everything inherited from base.
        self.assertEqual(tokens.accent, TERMINAL.accent)

    def test_empty_tokens_object_is_valid_and_fully_inherits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, {**VALID, "tokens": {}})
            tokens = self.loader.load(path, base=TERMINAL)

        for field in ("background", "accent", "accent_secondary", "font_mono", "radius"):
            self.assertEqual(getattr(tokens, field), getattr(TERMINAL, field))

    def test_invalid_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_raw(tmp, "{not json")
            with self.assertRaises(ThemeDefinitionError):
                self.loader.load(path, base=TERMINAL)

    def test_missing_theme_json_file_is_rejected_not_crashed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ThemeDefinitionError):
                self.loader.load(Path(tmp) / "does-not-exist.json", base=TERMINAL)

    def test_missing_schema_version_is_rejected(self) -> None:
        data = {k: v for k, v in VALID.items() if k != "schema_version"}
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, data)
            with self.assertRaises(ThemeDefinitionError):
                self.loader.load(path, base=TERMINAL)

    def test_unsupported_schema_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, {**VALID, "schema_version": 99})
            with self.assertRaises(ThemeDefinitionError) as ctx:
                self.loader.load(path, base=TERMINAL)
        self.assertIn("schema_version", str(ctx.exception))

    def test_invalid_id_is_rejected(self) -> None:
        for bad_id in ("../evil", "has spaces", "has.dots", "CON", ""):
            with self.subTest(bad_id=bad_id):
                with tempfile.TemporaryDirectory() as tmp:
                    path = _write(tmp, {**VALID, "id": bad_id})
                    with self.assertRaises(ThemeDefinitionError):
                        self.loader.load(path, base=TERMINAL)

    def test_missing_or_empty_name_is_rejected(self) -> None:
        missing = {k: v for k, v in VALID.items() if k != "name"}
        empty = {**VALID, "name": "   "}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertRaises(ThemeDefinitionError, self.loader.load, _write(tmp, missing), TERMINAL)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertRaises(ThemeDefinitionError, self.loader.load, _write(tmp, empty), TERMINAL)

    def test_tokens_must_be_an_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, {**VALID, "tokens": ["not", "an", "object"]})
            with self.assertRaises(ThemeDefinitionError):
                self.loader.load(path, base=TERMINAL)

    def test_unknown_token_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, {**VALID, "tokens": {**VALID["tokens"], "made_up_token": "x"}})
            with self.assertRaises(ThemeDefinitionError):
                self.loader.load(path, base=TERMINAL)

    def test_invalid_color_is_rejected(self) -> None:
        for bad_color in ("red", "#fff", "#gggggg", "39ff14", 123):
            with self.subTest(bad_color=bad_color):
                with tempfile.TemporaryDirectory() as tmp:
                    path = _write(tmp, {**VALID, "tokens": {**VALID["tokens"], "background": bad_color}})
                    with self.assertRaises(ThemeDefinitionError):
                        self.loader.load(path, base=TERMINAL)

    def test_invalid_font_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, {**VALID, "tokens": {**VALID["tokens"], "font_mono": ""}})
            with self.assertRaises(ThemeDefinitionError):
                self.loader.load(path, base=TERMINAL)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, {**VALID, "tokens": {**VALID["tokens"], "font_mono": 42}})
            with self.assertRaises(ThemeDefinitionError):
                self.loader.load(path, base=TERMINAL)

    def test_invalid_int_token_is_rejected(self) -> None:
        for bad_radius in (-1, 1000, "12", True, 12.5):
            with self.subTest(bad_radius=bad_radius):
                with tempfile.TemporaryDirectory() as tmp:
                    path = _write(tmp, {**VALID, "tokens": {**VALID["tokens"], "radius": bad_radius}})
                    with self.assertRaises(ThemeDefinitionError):
                        self.loader.load(path, base=TERMINAL)

    def test_invalid_bool_token_is_rejected(self) -> None:
        for bad_bool in ("true", 1, 0):
            with self.subTest(bad_bool=bad_bool):
                with tempfile.TemporaryDirectory() as tmp:
                    path = _write(tmp, {**VALID, "tokens": {**VALID["tokens"], "blink_cursor": bad_bool}})
                    with self.assertRaises(ThemeDefinitionError):
                        self.loader.load(path, base=TERMINAL)

    def test_unknown_top_level_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, {**VALID, "made_up_field": "x"})
            with self.assertRaises(ThemeDefinitionError):
                self.loader.load(path, base=TERMINAL)

    def test_contract_has_no_execution_fields(self) -> None:
        # The whitelist approach means any field that looks like code is
        # rejected the same way as any other unknown field -- proven here for
        # the specific names this phase calls out.
        for forbidden in ("script", "command", "entrypoint", "plugin", "exec", "callback", "import"):
            with self.subTest(forbidden=forbidden):
                with tempfile.TemporaryDirectory() as tmp:
                    path = _write(tmp, {**VALID, forbidden: "anything"})
                    with self.assertRaises(ThemeDefinitionError):
                        self.loader.load(path, base=TERMINAL)

    def test_result_is_a_real_theme_tokens_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, VALID)
            tokens = self.loader.load(path, base=TERMINAL)

        # Frozen dataclass compatible with every other ThemeTokens consumer
        # (QSS generation, ThemeManager, ...).
        self.assertTrue(hasattr(tokens, "__dataclass_fields__"))
        with self.assertRaises(Exception):
            tokens.background = "#000000"  # frozen: mutation must fail


if __name__ == "__main__":
    unittest.main()
