from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from exam_trainer.domain.entities import Exercise


@dataclass(frozen=True)
class ExamPack:
    id: str
    name: str
    ranks: tuple[str, ...] = ()


class PackRepository(Protocol):
    def list_packs(self) -> list[ExamPack]:
        raise NotImplementedError

    def list_exercises(self, pack_id: str) -> list[Exercise]:
        raise NotImplementedError

    def import_pack(self, source_path: Path) -> ExamPack:
        raise NotImplementedError
