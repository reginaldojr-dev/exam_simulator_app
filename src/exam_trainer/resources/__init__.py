"""Data files packaged with the app, including in the PyInstaller executable."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

PACK_CONTRACT = "pack-contract.md"


def resource_path(name: str) -> Path:
    """Real resource path; works in editable installs and the PyInstaller executable."""
    return Path(str(resources.files(__name__).joinpath(name)))


def pack_contract_text() -> str:
    return resources.files(__name__).joinpath(PACK_CONTRACT).read_text(encoding="utf-8")
