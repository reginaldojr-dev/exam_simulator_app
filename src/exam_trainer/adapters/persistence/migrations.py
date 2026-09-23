"""Migrações versionadas do banco SQLite.

Regras:
- a versão fica em `schema_meta(version)`; banco sem essa tabela = versão 0 (legado);
- cada migração roda numa transação e nunca apaga histórico;
- antes de migrar um banco existente, é feita uma cópia `trainer.sqlite3.bak-v<N>-<data>`.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

Migration = Callable[[sqlite3.Connection], None]


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _add_column(connection: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if column not in _columns(connection, table):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _migration_1_exam_deadline(connection: sqlite3.Connection) -> None:
    """Prova com deadline absoluto e duração vinda do pack.

    Sessões ativas antigas só tinham `remaining_seconds` (o relógio pausava com o
    app fechado). Para não "cobrar" o tempo em que o app ficou fechado ANTES desta
    versão, o deadline delas passa a ser agora + remaining_seconds.
    """
    _add_column(connection, "exam_sessions", "deadline_at", "TEXT")
    _add_column(connection, "exam_sessions", "duration_seconds", "INTEGER")
    now = datetime.now(timezone.utc)
    rows = connection.execute(
        "SELECT id, remaining_seconds FROM exam_sessions WHERE deadline_at IS NULL"
    ).fetchall()
    for session_id, remaining in rows:
        deadline = now + timedelta(seconds=int(remaining or 0))
        connection.execute(
            "UPDATE exam_sessions SET deadline_at = ?, duration_seconds = COALESCE(duration_seconds, ?) WHERE id = ?",
            (deadline.isoformat(), int(remaining or 0), session_id),
        )


MIGRATIONS: list[tuple[int, Migration]] = [
    (1, _migration_1_exam_deadline),
]

LATEST_VERSION = MIGRATIONS[-1][0]


def current_version(connection: sqlite3.Connection) -> int:
    connection.execute("CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER NOT NULL)")
    row = connection.execute("SELECT version FROM schema_meta").fetchone()
    return 0 if row is None else int(row[0])


def _set_version(connection: sqlite3.Connection, version: int) -> None:
    connection.execute("DELETE FROM schema_meta")
    connection.execute("INSERT INTO schema_meta (version) VALUES (?)", (version,))


def backup_database(database_path: Path, from_version: int) -> Path | None:
    if not database_path.is_file() or database_path.stat().st_size == 0:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = database_path.with_name(f"{database_path.name}.bak-v{from_version}-{stamp}")
    shutil.copy2(database_path, backup)
    return backup


def migrate(database_path: Path, connect: Callable[[], sqlite3.Connection], has_user_data: bool) -> int:
    """Aplica as migrações pendentes. Retorna a versão final."""
    connection = connect()
    try:
        version = current_version(connection)
        connection.commit()
    finally:
        connection.close()
    pending = [(target, step) for target, step in MIGRATIONS if target > version]
    if not pending:
        return version
    if has_user_data:
        backup_database(database_path, version)
    for target, step in pending:
        connection = connect()
        try:
            connection.execute("BEGIN")
            step(connection)
            _set_version(connection, target)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    return pending[-1][0]
