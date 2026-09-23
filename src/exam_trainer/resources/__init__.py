"""Arquivos de dados empacotados com o app (também no executável do PyInstaller)."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

PACK_CONTRACT = "pack-contract.md"


def resource_path(name: str) -> Path:
    """Caminho real do recurso (funciona em editable install e no exe do PyInstaller)."""
    return Path(str(resources.files(__name__).joinpath(name)))


def pack_contract_text() -> str:
    return resources.files(__name__).joinpath(PACK_CONTRACT).read_text(encoding="utf-8")
