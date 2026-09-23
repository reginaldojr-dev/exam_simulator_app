from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath

LEGACY_EXAM_DURATION_SECONDS = 4 * 60 * 60
DEFAULT_LANGUAGE = "c"
SUPPORTED_SCHEMA_VERSIONS = (1, 2)


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
    # Duração da prova declarada pelo pack (`exam.duration_minutes`).
    # None = pack não declarou; use `exam_duration_seconds_or_default`.
    exam_duration_seconds: int | None = None
    # Contrato v2. Pack v1 (sem schema_version) é normalizado: language="c", topics=().
    schema_version: int = 1
    language: str = DEFAULT_LANGUAGE
    topics: tuple[str, ...] = ()

    @property
    def exam_duration_seconds_or_default(self) -> int:
        return self.exam_duration_seconds or LEGACY_EXAM_DURATION_SECONDS

    @property
    def level_ids(self) -> tuple[str, ...]:
        return tuple(level.id for level in self.levels)
