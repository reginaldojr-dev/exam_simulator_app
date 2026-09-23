"""Regras puras para identificadores e caminhos declarados por packs.

Nada aqui toca o disco: só decide se um valor vindo de JSON externo é seguro
para virar nome de pasta, nome de arquivo ou caminho relativo.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# Nomes reservados do Windows: não podem ser pasta nem arquivo, com ou sem extensão.
WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


class UnsafeValueError(ValueError):
    """Valor externo que não pode ser usado com segurança como id ou caminho."""


def validate_identifier(value: str, field_name: str = "id") -> str:
    """Aceita só `[A-Za-z0-9][A-Za-z0-9_-]{0,63}` e recusa nomes reservados do Windows.

    Isso impede `..`, `.`, `C:`, separadores, espaços, pontos e caracteres especiais,
    então um id pode virar nome de pasta sem escapar do diretório pai.
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
    """Converte um caminho relativo declarado no pack num PurePosixPath seguro.

    Recusa: vazio, absoluto (POSIX ou Windows), drive (`C:`), UNC, `..`, `:` em
    qualquer parte (drive relativo, alternate data streams) e nomes reservados.
    Aceita `/` e `\\` como separadores.
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
    """Nome de arquivo simples (sem diretório), seguro em Windows e POSIX."""
    path = parse_relative_path(value, field_name)
    if len(path.parts) != 1:
        raise UnsafeValueError(f"{field_name} must be a simple filename.")
    return path.parts[0]
