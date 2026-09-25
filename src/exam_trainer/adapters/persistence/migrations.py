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

from exam_trainer.domain.activity_identity import DEFAULT_ACTIVITY_KIND
from exam_trainer.domain.attempt_modes import EXAM_MODE, LEGACY_PACK_ID, TRAINING_MODE

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




def rebuild_progress(
    connection: sqlite3.Connection,
    pack_id: str | None = None,
    exercise_id: str | None = None,
) -> None:
    """Recalcula `progress` a partir das tentativas de TREINO (fonte da verdade).

    Sem argumentos recalcula tudo; com (pack_id, exercise_id) só aquela chave.
    Tentativas de prova nunca entram aqui (ADR 0003).
    """
    where = ""
    params: tuple[str, ...] = ()
    if pack_id is not None and exercise_id is not None:
        connection.execute(
            "DELETE FROM progress WHERE pack_id = ? AND exercise_id = ?", (pack_id, exercise_id)
        )
        where = "AND pack_id = ? AND exercise_id = ?"
        params = (pack_id, exercise_id)
    else:
        connection.execute("DELETE FROM progress")
    progress_columns = _columns(connection, "progress")
    if {"activity_id", "activity_kind", "policy"}.issubset(progress_columns):
        connection.execute(
            f"""
            INSERT INTO progress (
                pack_id, exercise_id, activity_id, activity_kind, policy,
                status, attempts_count, last_attempt_at, best_passed, best_score, last_mode
            )
            SELECT pack_id, exercise_id, exercise_id, '{DEFAULT_ACTIVITY_KIND}', '{TRAINING_MODE}',
                   CASE WHEN MAX(COALESCE(passed, 0)) = 1 THEN 'completed' ELSE 'attempted' END,
                   COUNT(*), MAX(submitted_at), MAX(COALESCE(passed, 0)), MAX(score), '{TRAINING_MODE}'
            FROM attempts
            WHERE mode = '{TRAINING_MODE}' AND pack_id IS NOT NULL {where}
            GROUP BY pack_id, exercise_id
            """,
            params,
        )
    else:
        connection.execute(
            f"""
            INSERT INTO progress (
                pack_id, exercise_id, status, attempts_count, last_attempt_at,
                best_passed, best_score, last_mode
            )
            SELECT pack_id, exercise_id,
                   CASE WHEN MAX(COALESCE(passed, 0)) = 1 THEN 'completed' ELSE 'attempted' END,
                   COUNT(*), MAX(submitted_at), MAX(COALESCE(passed, 0)), MAX(score), '{TRAINING_MODE}'
            FROM attempts
            WHERE mode = '{TRAINING_MODE}' AND pack_id IS NOT NULL {where}
            GROUP BY pack_id, exercise_id
            """,
            params,
        )


def _migration_2_pack_scoped_progress(connection: sqlite3.Connection) -> None:
    """Progresso por (pack_id, exercise_id) e separado entre treino e prova (ADR 0003).

    Estratégia conservadora — nada é apagado:
    - `attempts` ganha `pack_id` e `session_id`; `mode` nulo (versões antigas) vira `training`;
    - tentativas de prova legadas recebem o pack da sessão de prova em que aparecem, se único;
    - as demais ficam com `pack_id = '_legacy'`; o app as associa depois ao pack do catálogo
      que declara aquele exercise_id, quando houver exatamente um (`adopt_legacy_attempts`);
    - a tabela `progress` antiga é renomeada para `progress_legacy_v0` (mantida para consulta);
    - o novo `progress` é recalculado só com tentativas de treino.
    """
    _add_column(connection, "attempts", "pack_id", "TEXT")
    _add_column(connection, "attempts", "session_id", "TEXT")
    connection.execute(f"UPDATE attempts SET mode = '{TRAINING_MODE}' WHERE mode IS NULL")
    exam_packs = """
        FROM exam_level_results r JOIN exam_sessions s ON s.id = r.session_id
        WHERE r.exercise_id = attempts.exercise_id AND s.rank IS NOT NULL
    """
    connection.execute(
        f"""
        UPDATE attempts SET pack_id = (SELECT MIN(s.rank) {exam_packs})
        WHERE pack_id IS NULL AND mode = '{EXAM_MODE}'
          AND (SELECT COUNT(DISTINCT s.rank) {exam_packs}) = 1
        """
    )
    connection.execute("UPDATE attempts SET pack_id = ? WHERE pack_id IS NULL", (LEGACY_PACK_ID,))
    connection.execute("ALTER TABLE progress RENAME TO progress_legacy_v0")
    connection.execute(
        """
        CREATE TABLE progress (
            pack_id TEXT NOT NULL,
            exercise_id TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            best_passed INTEGER NOT NULL DEFAULT 0,
            best_score REAL,
            last_mode TEXT,
            PRIMARY KEY (pack_id, exercise_id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_attempts_pack_exercise ON attempts (pack_id, exercise_id, mode)"
    )
    rebuild_progress(connection)


def _migration_3_activity_identity_and_policy(connection: sqlite3.Connection) -> None:
    """Adiciona identidade neutra de activity e policy sem remover colunas legadas."""
    _add_column(connection, "attempts", "activity_id", "TEXT")
    _add_column(connection, "attempts", "activity_kind", "TEXT")
    _add_column(connection, "attempts", "policy", "TEXT")
    connection.execute("UPDATE attempts SET activity_id = exercise_id WHERE activity_id IS NULL")
    connection.execute(
        "UPDATE attempts SET activity_kind = ? WHERE activity_kind IS NULL",
        (DEFAULT_ACTIVITY_KIND,),
    )
    connection.execute("UPDATE attempts SET policy = mode WHERE policy IS NULL")

    _add_column(connection, "progress", "activity_id", "TEXT")
    _add_column(connection, "progress", "activity_kind", "TEXT")
    _add_column(connection, "progress", "policy", "TEXT")
    connection.execute("UPDATE progress SET activity_id = exercise_id WHERE activity_id IS NULL")
    connection.execute(
        "UPDATE progress SET activity_kind = ? WHERE activity_kind IS NULL",
        (DEFAULT_ACTIVITY_KIND,),
    )
    connection.execute("UPDATE progress SET policy = ? WHERE policy IS NULL", (TRAINING_MODE,))

    _add_column(connection, "exam_sessions", "policy", "TEXT")
    connection.execute("UPDATE exam_sessions SET policy = ? WHERE policy IS NULL", (EXAM_MODE,))

    _add_column(connection, "exam_history", "policy", "TEXT")
    connection.execute("UPDATE exam_history SET policy = ? WHERE policy IS NULL", (EXAM_MODE,))

    _add_column(connection, "exam_level_results", "activity_id", "TEXT")
    _add_column(connection, "exam_level_results", "activity_kind", "TEXT")
    connection.execute("UPDATE exam_level_results SET activity_id = exercise_id WHERE activity_id IS NULL")
    connection.execute(
        "UPDATE exam_level_results SET activity_kind = ? WHERE activity_kind IS NULL",
        (DEFAULT_ACTIVITY_KIND,),
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_attempts_activity_policy ON attempts (pack_id, activity_kind, activity_id, policy)"
    )


MIGRATIONS: list[tuple[int, Migration]] = [
    (1, _migration_1_exam_deadline),
    (2, _migration_2_pack_scoped_progress),
    (3, _migration_3_activity_identity_and_policy),
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
