from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ArgumentKind(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    CHOICE = "choice"
    INTEGER_SEQUENCE = "integer_sequence"


@dataclass(frozen=True)
class ArgumentContract:
    kind: ArgumentKind
    values: tuple[str, ...] = ()
    min_value: int = -1000
    max_value: int = 1000
    min_items: int = 1
    max_items: int = 8
    include_length_arg: bool = False


@dataclass(frozen=True)
class TestContract:
    args: tuple[ArgumentContract, ...] = ()
