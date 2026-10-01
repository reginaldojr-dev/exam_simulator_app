"""Validates and parses `plugin.json`: a plugin's declarative manifest.

This module never imports or executes a plugin's Python code -- it only reads
JSON and validates it against an explicit field whitelist, producing a
`PluginManifest`. Importing/executing the plugin's own module is a separate,
later step gated by API-version compatibility and by the plugin being
explicitly enabled (see `loader.py`). Unknown top-level fields are always
rejected, the same whitelist discipline used for `theme.json`
(`adapters/theme/theme_contract.py`) and for pack contracts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rankeddojo.domain.identifiers import UnsafeValueError, validate_identifier

PLUGIN_MANIFEST_FILENAME = "plugin.json"

SUPPORTED_SCHEMA_VERSIONS = frozenset({1})

TOP_LEVEL_KEYS = frozenset({"schema_version", "id", "version", "api_version", "entrypoint", "capabilities"})
# Every field is required in v1 -- there is no optional metadata to keep the
# manifest minimal (see resources/plugin-api-v1.md).
REQUIRED_TOP_LEVEL_KEYS = TOP_LEVEL_KEYS

# The only capabilities Plugin API v1 can actually register (context.py).
# Declaring anything else is rejected outright -- never silently ignored.
KNOWN_CAPABILITIES = frozenset({"runtime", "editor"})

# "module:function", both plain Python identifiers. This keeps the entrypoint
# to a single flat file directly inside the plugin's own folder: no dots, no
# path separators, so it cannot name anything outside that folder and cannot
# reference a sub-package.
_ENTRYPOINT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:[A-Za-z_][A-Za-z0-9_]*$")
_MAX_VERSION_LENGTH = 32


class PluginManifestError(ValueError):
    """`plugin.json` failed validation. Never crashes the app; callers catch
    this, skip the plugin, and keep going."""


@dataclass(frozen=True)
class PluginManifest:
    """A validated `plugin.json`. `entrypoint_module` names a `.py` file
    directly inside the plugin's own folder; `entrypoint_function` is the
    callable inside it that receives the `PluginRegistrationContext`."""

    id: str
    version: str
    api_version: int
    entrypoint_module: str
    entrypoint_function: str
    capabilities: tuple[str, ...]


def load_manifest(manifest_path: Path | str) -> PluginManifest:
    path = Path(manifest_path)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PluginManifestError(f"Could not read plugin manifest: {error}.") from error
    try:
        raw_data = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise PluginManifestError(f"Invalid JSON in plugin manifest: {error.msg}.") from error

    if not isinstance(raw_data, dict):
        raise PluginManifestError("plugin.json must be an object.")

    unknown = sorted(set(raw_data) - TOP_LEVEL_KEYS)
    if unknown:
        raise PluginManifestError(f"Unknown field(s) in plugin.json: {', '.join(unknown)}.")
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(raw_data))
    if missing:
        raise PluginManifestError(f"Missing required field(s): {', '.join(missing)}.")

    _read_schema_version(raw_data)
    plugin_id = _read_identifier(raw_data, "id")
    version = _read_non_empty_string(raw_data, "version", max_length=_MAX_VERSION_LENGTH)
    api_version = _read_api_version(raw_data)
    entrypoint_module, entrypoint_function = _read_entrypoint(raw_data)
    capabilities = _read_capabilities(raw_data)

    return PluginManifest(
        id=plugin_id,
        version=version,
        api_version=api_version,
        entrypoint_module=entrypoint_module,
        entrypoint_function=entrypoint_function,
        capabilities=capabilities,
    )


def _read_schema_version(data: dict[str, Any]) -> int:
    value = data["schema_version"]
    if not isinstance(value, int) or isinstance(value, bool) or value not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(str(item) for item in sorted(SUPPORTED_SCHEMA_VERSIONS))
        raise PluginManifestError(f"Unsupported schema_version: {value!r} (supported: {supported}).")
    return value


def _read_identifier(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str):
        raise PluginManifestError(f"{field_name} must be a string.")
    try:
        return validate_identifier(value, field_name)
    except UnsafeValueError as error:
        raise PluginManifestError(str(error)) from error


def _read_non_empty_string(data: dict[str, Any], field_name: str, *, max_length: int) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise PluginManifestError(f"{field_name} must be a non-empty string.")
    stripped = value.strip()
    if len(stripped) > max_length:
        raise PluginManifestError(f"{field_name} must be at most {max_length} characters.")
    return stripped


def _read_api_version(data: dict[str, Any]) -> int:
    value = data["api_version"]
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise PluginManifestError(f"api_version must be a positive integer, got {value!r}.")
    return value


def _read_entrypoint(data: dict[str, Any]) -> tuple[str, str]:
    value = data["entrypoint"]
    if not isinstance(value, str) or not _ENTRYPOINT_PATTERN.fullmatch(value):
        raise PluginManifestError(
            'entrypoint must look like "module:function", using plain Python '
            'identifiers only (letters, digits, "_", not starting with a digit), '
            'e.g. "plugin:register". It names a single .py file directly inside '
            "the plugin's own folder."
        )
    module_name, function_name = value.split(":", 1)
    return module_name, function_name


def _read_capabilities(data: dict[str, Any]) -> tuple[str, ...]:
    value = data["capabilities"]
    if not isinstance(value, list) or not value:
        raise PluginManifestError("capabilities must be a non-empty list.")
    capabilities: list[str] = []
    for item in value:
        if not isinstance(item, str) or item not in KNOWN_CAPABILITIES:
            known = ", ".join(sorted(KNOWN_CAPABILITIES))
            raise PluginManifestError(f"Unknown capability: {item!r} (known capabilities: {known}).")
        capabilities.append(item)
    return tuple(dict.fromkeys(capabilities))
