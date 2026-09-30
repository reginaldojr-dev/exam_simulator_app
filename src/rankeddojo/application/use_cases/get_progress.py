from __future__ import annotations

from rankeddojo.domain.entities import Attempt
from rankeddojo.ports.progress_repository import ProgressRepository


class GetProgress:
    def __init__(self, progress_repository: ProgressRepository) -> None:
        self._progress_repository = progress_repository

    def execute(self) -> list[Attempt]:
        return self._progress_repository.list_attempts()
