from __future__ import annotations

from pathlib import Path

from exam_trainer.ports.pack_repository import ExamPack, PackRepository


class ImportPack:
    def __init__(self, pack_repository: PackRepository) -> None:
        self._pack_repository = pack_repository

    def execute(self, source_path: Path) -> ExamPack:
        return self._pack_repository.import_pack(source_path)
