"""Migrates the legacy `exam-trainer` data directory to the current
`rankeddojo` one (see `infrastructure/paths.py`).

This must run once, very early at startup -- before config, the database,
packs, themes or plugins are opened -- so everything downstream always sees
`user_config_dir()` already in its final place. See `main.py` for the call
site and README.md ("Workspace e dados") for the user-facing summary.

Safety rules:
- never deletes data on failure;
- never silently overwrites an already-existing new-style directory;
- if both the legacy and the new directory already exist, neither is
  touched -- the situation is returned explicitly instead of guessed at;
- idempotent: once the new directory exists, this is a no-op on every later
  startup (its existence alone is the completion marker; no separate flag
  file is needed);
- prefers an atomic rename on the same filesystem; falls back to a
  copy-then-verify-then-remove-original sequence only when the rename itself
  is not possible (commonly: the two directories are on different
  filesystems/drives).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from rankeddojo.infrastructure.paths import legacy_user_config_dir, user_config_dir


class DataDirMigrationStatus(str, Enum):
    NOTHING_TO_MIGRATE = "nothing_to_migrate"  # no legacy directory found
    ALREADY_MIGRATED = "already_migrated"  # current directory already exists
    BOTH_EXIST_CONFLICT = "both_exist_conflict"  # legacy and current both exist: neither touched
    MIGRATED_BY_RENAME = "migrated_by_rename"  # atomic rename succeeded
    MIGRATED_BY_COPY = "migrated_by_copy"  # cross-filesystem copy, verified, legacy removed
    FAILED = "failed"  # attempted and did not complete; legacy directory preserved


@dataclass(frozen=True)
class DataDirMigrationResult:
    status: DataDirMigrationStatus
    legacy_dir: Path
    target_dir: Path
    detail: str = ""


def migrate_legacy_data_dir(
    legacy_dir: Path | None = None,
    target_dir: Path | None = None,
) -> DataDirMigrationResult:
    """Migrate `legacy_dir` (default: `legacy_user_config_dir()`) into
    `target_dir` (default: `user_config_dir()`) if, and only if, `target_dir`
    does not exist yet. Never raises: any failure is reported in the result,
    and the legacy directory is preserved."""
    legacy = legacy_dir if legacy_dir is not None else legacy_user_config_dir()
    target = target_dir if target_dir is not None else user_config_dir()

    legacy_exists = legacy.is_dir()
    target_exists = target.is_dir()

    if target_exists and legacy_exists:
        return DataDirMigrationResult(
            DataDirMigrationStatus.BOTH_EXIST_CONFLICT,
            legacy,
            target,
            "Both the legacy and the current data directory already exist; "
            "neither was touched. Merge manually if you need data from both.",
        )
    if target_exists:
        return DataDirMigrationResult(DataDirMigrationStatus.ALREADY_MIGRATED, legacy, target)
    if not legacy_exists:
        return DataDirMigrationResult(DataDirMigrationStatus.NOTHING_TO_MIGRATE, legacy, target)

    return _migrate(legacy, target)


def _migrate(legacy: Path, target: Path) -> DataDirMigrationResult:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        legacy.rename(target)
    except OSError:
        return _migrate_by_copy(legacy, target)
    return DataDirMigrationResult(DataDirMigrationStatus.MIGRATED_BY_RENAME, legacy, target)


def _migrate_by_copy(legacy: Path, target: Path) -> DataDirMigrationResult:
    # The atomic rename above was not possible (commonly: legacy and target
    # live on different filesystems/drives). Copy into a staging folder next
    # to the target first, so a failure or interruption never leaves a
    # *partial* `target` behind -- `target` only ever appears once the full
    # copy is verified, which keeps this function safely retryable on the
    # next startup.
    staging = target.parent / f".{target.name}.migrating"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    try:
        shutil.copytree(legacy, staging)
        if not _verify_copy(legacy, staging):
            raise OSError("copied data does not match the original (file list or size mismatch)")
        staging.rename(target)
    except Exception as error:  # noqa: BLE001 - a failed migration must never crash startup or lose data
        shutil.rmtree(staging, ignore_errors=True)
        return DataDirMigrationResult(
            DataDirMigrationStatus.FAILED,
            legacy,
            target,
            f"Could not migrate the legacy data directory: {error}. "
            "The legacy directory was left untouched.",
        )

    shutil.rmtree(legacy, ignore_errors=True)
    return DataDirMigrationResult(DataDirMigrationStatus.MIGRATED_BY_COPY, legacy, target)


def _verify_copy(original: Path, copy: Path) -> bool:
    original_files = sorted(path.relative_to(original) for path in original.rglob("*") if path.is_file())
    copy_files = sorted(path.relative_to(copy) for path in copy.rglob("*") if path.is_file())
    if original_files != copy_files:
        return False
    return all(
        (original / relative).stat().st_size == (copy / relative).stat().st_size
        for relative in original_files
    )
