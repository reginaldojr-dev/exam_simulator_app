"""Proteções de sistema de arquivos para packs externos.

Um pack é conteúdo de terceiros. Antes de ler ou copiar qualquer arquivo dele:
- nenhum caminho pode sair da raiz do pack (nem via symlink/junction);
- ZIPs são inspecionados antes de extrair;
- o destino da importação precisa ficar dentro da pasta gerenciada.

Nada aqui executa conteúdo do pack.
"""

from __future__ import annotations

import os
import stat
import zipfile
from pathlib import Path, PurePath

from exam_trainer.domain.identifiers import UnsafeValueError, parse_relative_path

MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_UNCOMPRESSED_BYTES = 200 * 1024 * 1024


class PackSecurityError(ValueError):
    pass


def _is_link(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def ensure_inside(root: Path, candidate: Path) -> Path:
    """Resolve `candidate` e garante que ele fica dentro de `root` (e não é o próprio root)."""
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise PackSecurityError(f"Path escapes the allowed folder: {candidate}")
    return resolved


def safe_join(root: Path, relative: PurePath | str) -> Path:
    """Junta um caminho relativo declarado pelo pack à raiz e confirma que continua dentro dela."""
    try:
        parsed = parse_relative_path(str(relative))
    except UnsafeValueError as error:
        raise PackSecurityError(str(error)) from error
    joined = root.joinpath(*parsed.parts)
    if _is_link(joined):
        raise PackSecurityError(f"Symbolic links are not allowed in packs: {parsed}")
    return ensure_inside(root, joined)


def find_links(root: Path) -> list[Path]:
    """Lista symlinks/junctions dentro da árvore, sem segui-los."""
    links: list[Path] = []
    for current, directories, files in os.walk(root, followlinks=False):
        base = Path(current)
        for name in (*directories, *files):
            path = base / name
            if _is_link(path):
                links.append(path)
    return links


def reject_links(root: Path) -> None:
    links = find_links(root)
    if links:
        shown = ", ".join(str(link.relative_to(root)) for link in links[:5])
        raise PackSecurityError(f"Symbolic links are not allowed in packs: {shown}")


def validate_zip(archive: zipfile.ZipFile) -> None:
    """Recusa ZIPs com caminhos absolutos, `..`, drives, symlinks ou tamanho excessivo."""
    entries = archive.infolist()
    if len(entries) > MAX_ZIP_ENTRIES:
        raise PackSecurityError(f"ZIP has too many entries ({len(entries)}).")
    total = 0
    for info in entries:
        name = info.filename
        if not name or name.endswith("/") and name.strip("/") == "":
            continue
        try:
            parse_relative_path(name.rstrip("/"), "ZIP entry")
        except UnsafeValueError as error:
            raise PackSecurityError(f"Unsafe ZIP entry {name!r}: {error}") from error
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise PackSecurityError(f"Symbolic links are not allowed in packs: {name}")
        total += info.file_size
        if total > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise PackSecurityError("ZIP is too large once extracted.")
