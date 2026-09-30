"""Validates and parses `theme.json`: a purely declarative external theme.

See `resources/theme-contract.md` for the full contract. This module never
executes anything from the file -- it only reads JSON, validates it against an
explicit field whitelist, and builds a `ThemeTokens` instance. Fields outside
that whitelist (including anything resembling code: "script", "command",
"entrypoint", "plugin", ...) are always rejected, never silently accepted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from exam_trainer.adapters.ui.qt.theme.tokens import ThemeTokens
from exam_trainer.domain.identifiers import UnsafeValueError, validate_identifier

SUPPORTED_SCHEMA_VERSIONS = frozenset({1})

TOP_LEVEL_KEYS = frozenset({"schema_version", "id", "name", "author", "version", "tokens"})
REQUIRED_TOP_LEVEL_KEYS = frozenset({"schema_version", "id", "name", "tokens"})

# Every ThemeTokens field an external theme may set, grouped by how it is
# validated. `key`/`name` are not here: they come from the top-level `id`/
# `name` fields, never from `tokens`.
COLOR_FIELDS = frozenset(
    {
        "background",
        "surface",
        "surface_alt",
        "hover_background",
        "selected_background",
        "pressed_background",
        "accent",
        "accent_secondary",
        "text_primary",
        "text_bright",
        "text_secondary",
        "text_disabled",
        "border",
        "border_strong",
        "bevel",
        "border_disabled",
        "success",
        "fail",
        "warning",
        "fail_background",
        "success_background",
    }
)
FONT_FIELDS = frozenset({"font_body", "font_title", "font_mono"})
BOOL_FIELDS = frozenset({"blink_cursor", "animations"})
# field -> (min, max), inclusive.
INT_FIELDS: dict[str, tuple[int, int]] = {
    "font_size": (6, 96),
    "title_size": (6, 128),
    "radius": (0, 64),
    "bevel_width": (0, 32),
}
STRING_MISC_FIELDS = frozenset({"cursor_char"})

ALLOWED_TOKEN_FIELDS = COLOR_FIELDS | FONT_FIELDS | BOOL_FIELDS | frozenset(INT_FIELDS) | STRING_MISC_FIELDS

_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
_MAX_NAME_LENGTH = 80
_MAX_FONT_LENGTH = 200
_MAX_CURSOR_CHAR_LENGTH = 8


class ThemeDefinitionError(ValueError):
    """A `theme.json` file failed validation. Never crashes the app; callers
    catch this, skip the theme, and keep going."""


class JsonThemeLoader:
    """Reads and validates one `theme.json`, producing a `ThemeTokens`.

    Tokens the file does not declare are inherited from `base` (a fixed,
    stable internal theme), so an external theme can safely provide only a
    subset -- see `resources/theme-contract.md`.
    """

    def load(self, theme_json_path: Path | str, base: ThemeTokens) -> ThemeTokens:
        path = Path(theme_json_path)
        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise ThemeDefinitionError(f"Could not read theme definition: {error}.") from error
        try:
            raw_data = json.loads(raw_text)
        except json.JSONDecodeError as error:
            raise ThemeDefinitionError(f"Invalid JSON in theme definition: {error.msg}.") from error

        data = self._require_object(raw_data, "theme definition")
        self._require_no_unknown_keys(data, TOP_LEVEL_KEYS, "theme.json")
        missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(data))
        if missing:
            raise ThemeDefinitionError(f"Missing required field(s): {', '.join(missing)}.")

        self._read_schema_version(data)
        theme_id = self._read_identifier(data, "id")
        name = self._read_non_empty_string(data, "name", max_length=_MAX_NAME_LENGTH)
        tokens_data = self._require_object(data["tokens"], "tokens")

        values = self._resolve_tokens(tokens_data, base)
        return ThemeTokens(key=theme_id, name=name, **values)

    # ------------------------------------------------------------- top level
    @staticmethod
    def _require_object(raw: Any, field_name: str) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ThemeDefinitionError(f"{field_name} must be an object.")
        return raw

    @staticmethod
    def _require_no_unknown_keys(data: dict[str, Any], allowed: frozenset[str], field_name: str) -> None:
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ThemeDefinitionError(f"Unknown field(s) in {field_name}: {', '.join(unknown)}.")

    @staticmethod
    def _read_schema_version(data: dict[str, Any]) -> int:
        version = data["schema_version"]
        if not isinstance(version, int) or isinstance(version, bool) or version not in SUPPORTED_SCHEMA_VERSIONS:
            supported = ", ".join(str(value) for value in sorted(SUPPORTED_SCHEMA_VERSIONS))
            raise ThemeDefinitionError(f"Unsupported schema_version: {version!r} (supported: {supported}).")
        return version

    def _read_identifier(self, data: dict[str, Any], field_name: str) -> str:
        value = self._read_non_empty_string(data, field_name, max_length=64)
        try:
            return validate_identifier(value, field_name)
        except UnsafeValueError as error:
            raise ThemeDefinitionError(str(error)) from error

    @staticmethod
    def _read_non_empty_string(data: dict[str, Any], field_name: str, *, max_length: int) -> str:
        if field_name not in data:
            raise ThemeDefinitionError(f"Missing required field: {field_name}.")
        value = data[field_name]
        if not isinstance(value, str):
            raise ThemeDefinitionError(f"{field_name} must be a string.")
        stripped = value.strip()
        if not stripped:
            raise ThemeDefinitionError(f"{field_name} cannot be empty.")
        if len(stripped) > max_length:
            raise ThemeDefinitionError(f"{field_name} must be at most {max_length} characters.")
        return stripped

    # ----------------------------------------------------------------- tokens
    def _resolve_tokens(self, tokens_data: dict[str, Any], base: ThemeTokens) -> dict[str, Any]:
        self._require_no_unknown_keys(tokens_data, ALLOWED_TOKEN_FIELDS, "tokens")

        values: dict[str, Any] = {}
        for field in COLOR_FIELDS:
            values[field] = self._read_color(tokens_data, field, base)
        for field in FONT_FIELDS:
            values[field] = self._read_font(tokens_data, field, base)
        for field in STRING_MISC_FIELDS:
            values[field] = self._read_cursor_char(tokens_data, field, base)
        for field in BOOL_FIELDS:
            values[field] = self._read_bool(tokens_data, field, base)
        for field, bounds in INT_FIELDS.items():
            values[field] = self._read_int(tokens_data, field, base, bounds)
        return values

    @staticmethod
    def _read_color(tokens_data: dict[str, Any], field: str, base: ThemeTokens) -> str:
        if field not in tokens_data:
            return getattr(base, field)
        value = tokens_data[field]
        if not isinstance(value, str) or not _COLOR_PATTERN.fullmatch(value):
            raise ThemeDefinitionError(f"tokens.{field} must be a hex color like \"#39ff14\".")
        return value

    @staticmethod
    def _read_font(tokens_data: dict[str, Any], field: str, base: ThemeTokens) -> str:
        if field not in tokens_data:
            return getattr(base, field)
        value = tokens_data[field]
        if not isinstance(value, str) or not value.strip():
            raise ThemeDefinitionError(f"tokens.{field} must be a non-empty font string.")
        if len(value.strip()) > _MAX_FONT_LENGTH:
            raise ThemeDefinitionError(f"tokens.{field} must be at most {_MAX_FONT_LENGTH} characters.")
        return value.strip()

    @staticmethod
    def _read_cursor_char(tokens_data: dict[str, Any], field: str, base: ThemeTokens) -> str:
        if field not in tokens_data:
            return getattr(base, field)
        value = tokens_data[field]
        if not isinstance(value, str) or not value or len(value) > _MAX_CURSOR_CHAR_LENGTH:
            raise ThemeDefinitionError(f"tokens.{field} must be a non-empty string up to {_MAX_CURSOR_CHAR_LENGTH} characters.")
        return value

    @staticmethod
    def _read_bool(tokens_data: dict[str, Any], field: str, base: ThemeTokens) -> bool:
        if field not in tokens_data:
            return getattr(base, field)
        value = tokens_data[field]
        if not isinstance(value, bool):
            raise ThemeDefinitionError(f"tokens.{field} must be a boolean.")
        return value

    @staticmethod
    def _read_int(tokens_data: dict[str, Any], field: str, base: ThemeTokens, bounds: tuple[int, int]) -> int:
        if field not in tokens_data:
            return getattr(base, field)
        value = tokens_data[field]
        low, high = bounds
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise ThemeDefinitionError(f"tokens.{field} must be an integer between {low} and {high}.")
        return value
