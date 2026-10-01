"""Filesystem protections for external packs.

A pack is third-party content. Before reading or copying any file from it:
- no path may escape the pack root, including through symlinks/junctions;
- ZIP files are inspected before extraction;
- the import destination must stay inside the managed folder.

Nothing here executes pack content.
"""

from __future__ import annotations

import os
import stat
import zipfile
from pathlib import Path, PurePath

from rankeddojo.domain.identifiers import UnsafeValueError, parse_relative_path

MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_UNCOMPRESSED_BYTES = 200 * 1024 * 1024


class PackSecurityError(ValueError):
    pass


def _is_link(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def ensure_inside(root: Path, candidate: Path) -> Path:
    """Resolve `candidate` and ensure it stays inside `root`, not equal to root itself."""
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise PackSecurityError(f"Path escapes the allowed folder: {candidate}")
    return resolved


def safe_join(root: Path, relative: PurePath | str) -> Path:
    """Join a pack-declared relative path to root and confirm it remains inside."""
    try:
        parsed = parse_relative_path(str(relative))
    except UnsafeValueError as error:
        raise PackSecurityError(str(error)) from error
    joined = root.joinpath(*parsed.parts)
    if _is_link(joined):
        raise PackSecurityError(f"Symbolic links are not allowed in packs: {parsed}")
    return ensure_inside(root, joined)


def find_links(root: Path) -> list[Path]:
    """List symlinks/junctions inside the tree without following them."""
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
    """Reject ZIPs with absolute paths, `..`, drives, symlinks, or excessive size."""
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
