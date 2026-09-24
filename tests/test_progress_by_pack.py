"""Passo 4: progresso por (pack_id, exercise_id), treino separado de prova, migração legada."""

from __future__ import annotations

import json
import random
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from exam_trainer.adapters.compiler.system_c_compiler import SystemCCompiler
from exam_trainer.adapters.editor.subprocess_editor import SubprocessEditor, SubprocessEditorFactory
from exam_trainer.adapters.pack.local_pack_catalog import LocalPackCatalog
from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter
from exam_trainer.adapters.persistence import migrations
from exam_trainer.adapters.persistence.sqlite_progress_repository import SQLiteProgressRepository
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.adapters.runtime.c_runtime import CRuntime
from exam_trainer.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from exam_trainer.adapters.workspace.local_workspace import LocalWorkspace
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry
from exam_trainer.application.use_cases.mvp_coordinator import MVPTrainerCoordinator, TrainingOptions
from exam_trainer.domain.attempt_modes import LEGACY_PACK_ID

from test_exam_rules import FakeClock, SwitchGrader, build_pack

LEGACY_V0_SCHEMA = """
CREATE TABLE attempts (
    id TEXT PRIMARY KEY, exercise_id TEXT NOT NULL, status TEXT NOT NULL, passed INTEGER,
    score REAL, message TEXT, submitted_at TEXT, mode TEXT
);
CREATE TABLE progress (
    exercise_id TEXT PRIMARY KEY, status TEXT NOT NULL, attempts_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT, best_passed INTEGER NOT NULL DEFAULT 0, best_score REAL, last_mode TEXT
);
CREATE TABLE exam_sessions (
    id TEXT PRIMARY KEY, rank TEXT, current_level INTEGER, current_exercise_id TEXT, score REAL,
    remaining_seconds INTEGER, seed INTEGER, status TEXT, workspace_path TEXT,
    started_at TEXT, finished_at TEXT
);
CREATE TABLE exam_level_results (
    session_id TEXT NOT NULL, level_index INTEGER NOT NULL, exercise_id TEXT NOT NULL,
    passed INTEGER NOT NULL, attempts_count INTEGER NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY (session_id, level_index)
);
-- treino antigo sem mode (save_attempt legado) e com mode
INSERT INTO attempts VALUES ('a1', 'ex_0_0', 'graded', 0, 0, '', '2026-01-01T10:00:00', NULL);
INSERT INTO attempts VALUES ('a2', 'ex_0_0', 'graded', 1, 100, '', '2026-01-01T11:00:00', 'training');
-- prova antiga: PASS em ex_0_1 dentro de uma sessão do pack 'alpha'
INSERT INTO attempts VALUES ('a3', 'ex_0_1', 'graded', 1, 100, '', '2026-01-02T10:00:00', 'exam');
INSERT INTO exam_sessions VALUES ('s1', 'alpha', 1, 'ex_1_0', 50, 0, 1, 'completed', '/x', '2026-01-02T09:00:00', '2026-01-02T12:00:00');
INSERT INTO exam_level_results VALUES ('s1', 0, 'ex_0_1', 1, 1, '2026-01-02T10:00:00');
-- exercício que não existe em nenhum pack instalado
INSERT INTO attempts VALUES ('a4', 'ghost', 'graded', 0, 0, '', '2026-01-03T10:00:00', 'training');
-- progress legado mistura prova com treino
INSERT INTO progress VALUES ('ex_0_0', 'completed', 2, '2026-01-01T11:00:00', 1, 100, 'training');
INSERT INTO progress VALUES ('ex_0_1', 'completed', 1, '2026-01-02T10:00:00', 1, 100, 'exam');
INSERT INTO progress VALUES ('ghost', 'attempted', 1, '2026-01-03T10:00:00', 0, 0, 'training');
"""


class ProgressByPackTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.bundled = self.root / "bundled"
        # alpha e beta compartilham ids de exercício (ex_0_0, ex_0_1, ...)
        build_pack(self.bundled / "alpha", "alpha", levels=2, per_level=2)
        build_pack(self.bundled / "beta", "beta", levels=1, per_level=2)
        self.grader = SwitchGrader()
        self.database = self.root / "trainer.sqlite3"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def coordinator(self) -> MVPTrainerCoordinator:
        compiler = SystemCCompiler(candidates=("definitely-not-a-c-compiler",))
        return MVPTrainerCoordinator(
            pack_catalog=LocalPackCatalog(self.root / "managed", bundled_packs_dir=self.bundled),
            progress_repository=SQLiteProgressRepository(SQLiteStore(self.database)),
            workspace=LocalExerciseWorkspace(),
            grader=self.grader,
            editor=SubprocessEditor("definitely-not-used"),
            pack_importer=LocalPackImporter(self.root / "managed"),
            runtimes=RuntimeRegistry([CRuntime(compiler, manager=compiler)]),
            workspace_root=self.root / "workspace",
            editor_factory=SubprocessEditorFactory(),
            workspace_port=LocalWorkspace(),
            clock=FakeClock(),
            rng=random.Random(3),
        )

    def _ref(self, coordinator: MVPTrainerCoordinator, pack_id: str, exercise_id: str):
        return next(
            ref for ref in coordinator._pack_catalog.list_exercises(pack_id) if ref.definition.id == exercise_id
        )

    def _train(self, coordinator: MVPTrainerCoordinator, pack_id: str, exercise_id: str, passed: bool):
        self.grader.passed = passed
        active = coordinator.prepare_exercise(self._ref(coordinator, pack_id, exercise_id), overwrite=True)
        return coordinator.submit_training(active)

    # ------------------------------------------------------------ chave por pack
    def test_same_exercise_id_in_two_packs_has_separate_progress(self) -> None:
        coordinator = self.coordinator()
        self._train(coordinator, "alpha", "ex_0_0", passed=True)
        self._train(coordinator, "beta", "ex_0_0", passed=False)

        repo = coordinator._progress_repository
        self.assertTrue(repo.progress_by_exercise("alpha")["ex_0_0"].best_passed)
        self.assertFalse(repo.progress_by_exercise("beta")["ex_0_0"].best_passed)
        self.assertEqual(repo.attempts_count("alpha", "ex_0_0"), 1)
        self.assertEqual(repo.attempts_count("beta", "ex_0_0"), 1)

    def test_training_selection_prioritizes_uncompleted_within_the_selected_pack(self) -> None:
        coordinator = self.coordinator()
        self._train(coordinator, "alpha", "ex_0_0", passed=True)
        options = TrainingOptions(pack_id="beta", level_ids=("level0",), selection_mode="only_uncompleted")
        chosen = {coordinator.choose_training_exercise(options).definition.id for _ in range(2)}
        # concluir em alpha não esconde ex_0_0 de beta
        self.assertEqual(chosen, {"ex_0_0", "ex_0_1"})

    def test_training_workspace_is_scoped_by_pack(self) -> None:
        coordinator = self.coordinator()
        active = coordinator.prepare_exercise(self._ref(coordinator, "beta", "ex_0_1"), overwrite=True)
        self.assertEqual(
            active.exercise_workspace_path,
            self.root / "workspace" / "training" / "beta" / "ex_0_1",
        )

    def test_legacy_training_workspace_is_moved_not_deleted(self) -> None:
        legacy = self.root / "workspace" / "training" / "ex_0_1"
        legacy.mkdir(parents=True)
        (legacy / "subject.txt").write_text("old", encoding="utf-8")
        (legacy / "ex_0_1.c").write_text("int main(void){return 0;}", encoding="utf-8")

        coordinator = self.coordinator()
        active = coordinator.prepare_exercise(self._ref(coordinator, "alpha", "ex_0_1"))

        self.assertFalse(legacy.exists())
        self.assertTrue(active.had_existing_submission)
        self.assertEqual(active.submission_path.read_text(encoding="utf-8"), "int main(void){return 0;}")

    # ------------------------------------------------------ treino x prova
    def test_exam_attempts_are_history_but_not_training_progress(self) -> None:
        coordinator = self.coordinator()
        state = coordinator.start_exam("beta", 600)
        self.grader.passed = True
        active = coordinator.prepare_exam_exercise(coordinator.exam_ref(state), state, overwrite=True)
        outcome, _ = coordinator.submit_exam(state, active)

        repo = coordinator._progress_repository
        self.assertEqual(repo.list_progress("beta"), [])
        self.assertEqual(repo.attempts_count("beta", state.exercise_id), 0)
        self.assertEqual(repo.attempts_count("beta", state.exercise_id, "exam", session_id=state.id), 1)
        self.assertEqual(outcome.attempts_count, 1)
        row = next(
            row for row in coordinator.exercise_history_rows()
            if row["pack_id"] == "beta" and row["exercise_id"] == state.exercise_id
        )
        self.assertEqual(row["status"], "não feito")
        self.assertEqual(row["modes"], "exam")
        self.assertEqual(row["latest_result"], "PASS")

    def test_repository_rejects_unknown_mode(self) -> None:
        repo = SQLiteProgressRepository(SQLiteStore(self.database))
        from exam_trainer.domain.grading import GradingResult, TraceData

        with self.assertRaises(ValueError):
            repo.save_grading_result("alpha", "ex_0_0", GradingResult(passed=True, trace_data=TraceData(())), "practice")

    # ----------------------------------------------------------- migração v0
    def _legacy_database(self) -> None:
        connection = sqlite3.connect(self.database)
        connection.executescript(LEGACY_V0_SCHEMA)
        connection.commit()
        connection.close()

    def test_legacy_database_migrates_without_losing_history(self) -> None:
        self._legacy_database()
        coordinator = self.coordinator()  # inicializa, migra e adota
        repo = coordinator._progress_repository
        db = sqlite3.connect(self.database)

        self.assertEqual(db.execute("SELECT version FROM schema_meta").fetchone()[0], migrations.LATEST_VERSION)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 4)
        # tabela antiga preservada, com os mesmos dados
        self.assertEqual(db.execute("SELECT COUNT(*) FROM progress_legacy_v0").fetchone()[0], 3)
        self.assertEqual(len(list(self.root.glob("trainer.sqlite3.bak-v0-*"))), 1)
        # mode nulo virou training
        self.assertEqual(db.execute("SELECT mode FROM attempts WHERE id='a1'").fetchone()[0], "training")
        # prova antiga: pack descoberto pela sessão de prova
        self.assertEqual(db.execute("SELECT pack_id FROM attempts WHERE id='a3'").fetchone()[0], "alpha")
        # 'ghost' não existe em nenhum pack: continua legado
        self.assertEqual(db.execute("SELECT pack_id FROM attempts WHERE id='a4'").fetchone()[0], LEGACY_PACK_ID)
        # ex_0_0 existe em alpha E beta: ambíguo, continua legado (não chuta)
        self.assertEqual(db.execute("SELECT pack_id FROM attempts WHERE id='a1'").fetchone()[0], LEGACY_PACK_ID)
        db.close()

        # progresso de treino só com treino; a prova em ex_0_1 não conta
        self.assertNotIn("ex_0_1", repo.progress_by_exercise("alpha"))
        legacy = repo.progress_by_exercise(LEGACY_PACK_ID)
        self.assertTrue(legacy["ex_0_0"].best_passed)
        self.assertEqual(legacy["ex_0_0"].attempts_count, 2)
        # linhas legadas continuam visíveis no histórico
        labels = {(row["pack"], row["exercise_id"]) for row in coordinator.exercise_history_rows()}
        self.assertIn(("(legado)", "ghost"), labels)
        self.assertIn(("(legado)", "ex_0_0"), labels)

    def test_unambiguous_legacy_attempts_are_adopted_by_the_installed_pack(self) -> None:
        shutil.rmtree(self.bundled / "beta")  # agora ex_0_0 só existe em alpha
        self._legacy_database()
        coordinator = self.coordinator()
        repo = coordinator._progress_repository

        entry = repo.progress_by_exercise("alpha")["ex_0_0"]
        self.assertTrue(entry.best_passed)
        self.assertEqual(entry.attempts_count, 2)
        self.assertNotIn("ex_0_0", repo.progress_by_exercise(LEGACY_PACK_ID))
        self.assertIn("ghost", repo.progress_by_exercise(LEGACY_PACK_ID))

    def test_migration_is_idempotent(self) -> None:
        self._legacy_database()
        self.coordinator()
        self.coordinator()
        db = sqlite3.connect(self.database)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 4)
        self.assertEqual(len(list(self.root.glob("trainer.sqlite3.bak-*"))), 1)
        db.close()

    def test_failed_migration_rolls_back_and_keeps_backup(self) -> None:
        self._legacy_database()
        original = migrations.MIGRATIONS[:]

        def broken(connection: sqlite3.Connection) -> None:
            connection.execute("UPDATE attempts SET exercise_id = 'changed'")
            raise RuntimeError("boom")

        migrations.MIGRATIONS[:] = [*original, (99, broken)]
        try:
            with self.assertRaises(RuntimeError):
                SQLiteStore(self.database).initialize()
        finally:
            migrations.MIGRATIONS[:] = original
        db = sqlite3.connect(self.database)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM attempts WHERE exercise_id='changed'").fetchone()[0], 0)
        db.close()
        self.assertTrue(list(self.root.glob("trainer.sqlite3.bak-v0-*")))


if __name__ == "__main__":
    unittest.main()
