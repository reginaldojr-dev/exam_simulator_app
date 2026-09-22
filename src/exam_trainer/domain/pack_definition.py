from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath


@dataclass(frozen=True)
class PackLevelDefinition:
    id: str
    path: PurePath


@dataclass(frozen=True)
class PackDefinition:
    id: str
    name: str
    version: str
    levels: tuple[PackLevelDefinition, ...]
