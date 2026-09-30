"""Pure rules for identifiers and paths declared by packs.

Nothing here touches disk: it only decides whether a value from external JSON is
safe to become a folder name, filename, or relative path.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# Windows reserved names cannot be folders or files, with or without extensions.
WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


class UnsafeValueError(ValueError):
    """External value that cannot be safely used as an id or path."""


def validate_identifier(value: str, field_name: str = "id") -> str:
    """Accept only `[A-Za-z0-9][A-Za-z0-9_-]{0,63}` and reject Windows reserved names.

    This blocks `..`, `.`, `C:`, separators, spaces, dots, and special
    characters, so an id can become a folder name without escaping its parent
    directory.
    """
    if not isinstance(value, str) or not IDENTIFIER_PATTERN.fullmatch(value):
        raise UnsafeValueError(
            f"{field_name} must match [A-Za-z0-9][A-Za-z0-9_-]{{0,63}} "
            "(letters, digits, '_' and '-', no dots, spaces or path separators)."
        )
    if value.upper() in WINDOWS_RESERVED_NAMES:
        raise UnsafeValueError(f"{field_name} cannot be a reserved Windows name: {value}.")
    return value


def parse_relative_path(value: str, field_name: str = "path") -> PurePosixPath:
    """Convert a relative path declared by a pack into a safe PurePosixPath.

    Rejects empty paths, absolute POSIX or Windows paths, drives (`C:`), UNC
    paths, `..`, `:` anywhere (relative drives or alternate data streams), and
    reserved names. Accepts `/` and `\\` as separators.
    """
    if not isinstance(value, str) or not value.strip():
        raise UnsafeValueError(f"{field_name} cannot be empty.")
    raw = value.strip()
    windows = PureWindowsPath(raw)
    if windows.drive or windows.root or raw.startswith(("/", "\\")):
        raise UnsafeValueError(f"{field_name} must be a relative path.")
    parts = [part for part in raw.replace("\\", "/").split("/") if part not in ("", ".")]
    if not parts:
        raise UnsafeValueError(f"{field_name} cannot be empty.")
    for part in parts:
        if part == ".." or ":" in part:
            raise UnsafeValueError(f"{field_name} must be a relative path inside the pack.")
        if part.split(".")[0].upper() in WINDOWS_RESERVED_NAMES:
            raise UnsafeValueError(f"{field_name} uses a reserved Windows name: {part}.")
    return PurePosixPath(*parts)


def validate_simple_filename(value: str, field_name: str = "filename") -> str:
    """Simple filename with no directory component, safe on Windows and POSIX."""
    path = parse_relative_path(value, field_name)
    if len(path.parts) != 1:
        raise UnsafeValueError(f"{field_name} must be a simple filename.")
    return path.parts[0]
