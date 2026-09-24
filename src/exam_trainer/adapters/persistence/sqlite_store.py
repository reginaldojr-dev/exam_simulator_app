from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from exam_trainer.adapters.persistence import migrations


class SQLiteStore:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @property
    def database_path(self) -> Path:
        return self._database_path

    def connect(self) -> sqlite3.Connection:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        had_data = self._database_path.is_file() and self._database_path.stat().st_size > 0
        self._create_base_tables()
        self.schema_version = migrations.migrate(self._database_path, self.connect, had_data)

    def _create_base_tables(self) -> None:
        """Tabelas da versão 0 (legado). Mudanças posteriores vêm das migrações."""
        with self.session() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS exercises (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    rank TEXT,
                    level TEXT,
                    pack_id TEXT
                );

                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY,
                    exercise_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    passed INTEGER,
                    score REAL,
                    message TEXT,
                    submitted_at TEXT,
                    mode TEXT
                );

                CREATE TABLE IF NOT EXISTS progress (
                    exercise_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    attempts_count INTEGER NOT NULL DEFAULT 0,
                    last_attempt_at TEXT,
                    best_passed INTEGER NOT NULL DEFAULT 0,
                    best_score REAL,
                    last_mode TEXT
                );

                CREATE TABLE IF NOT EXISTS training_sessions (
                    id TEXT PRIMARY KEY,
                    rank TEXT,
                    levels TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    status TEXT
                );

                CREATE TABLE IF NOT EXISTS exam_sessions (
                    id TEXT PRIMARY KEY,
                    rank TEXT,
                    current_level INTEGER,
                    current_exercise_id TEXT,
                    score REAL,
                    remaining_seconds INTEGER,
                    seed INTEGER,
                    status TEXT,
                    workspace_path TEXT,
                    started_at TEXT,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS exam_history (
                    id TEXT PRIMARY KEY,
                    rank TEXT,
                    final_score REAL,
                    status TEXT,
                    used_seconds INTEGER,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS exam_level_results (
                    session_id TEXT NOT NULL,
                    level_index INTEGER NOT NULL,
                    exercise_id TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    attempts_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, level_index)
                );
                """
            )
