from __future__ import annotations

import random
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from exam_trainer.adapters.editor.subprocess_editor import (
    EditorLaunchError,
    SubprocessEditor,
    editor_display_name,
    validate_editor_executable,
)
from exam_trainer.application.mvp_models import (
    ActiveExercise,
    CorrectionOutcome,
    ExerciseRef,
    ProgressEntry,
)
from exam_trainer.domain.grading import GradingPolicy, GradingResult
from exam_trainer.domain.pack_definition import PackDefinition
from exam_trainer.domain.workspace import Workspace
from exam_trainer.ports.editor_port import EditorPort
from exam_trainer.ports.exercise_workspace_port import ExerciseWorkspacePort
from exam_trainer.ports.grader_port import GraderPort, GradingRequest


@dataclass
class TrainingOptions:
    pack_id: str
    level_ids: tuple[str, ...]
    selection_mode: str = "prioritize_uncompleted"
    allow_repeated: bool = False


@dataclass
class ExamState:
    id: str
    pack_id: str
    level_index: int
    exercise_id: str
    score: float
    remaining_seconds: int
    seed: int
    workspace_path: Path
    deadline_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: int = 0


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    missing: str | None = None
    message: str = ""

    @classmethod
    def passed(cls) -> "PreflightResult":
        return cls(ok=True)

    @classmethod
    def failed(cls, missing: str, message: str) -> "PreflightResult":
        return cls(ok=False, missing=missing, message=message)


class MVPTrainerCoordinator:
    def __init__(
        self,
        pack_catalog,
        progress_repository,
        workspace: ExerciseWorkspacePort,
        grader: GraderPort,
        editor: EditorPort,
        pack_importer,
        compiler,
        workspace_root: Path,
        config_repository=None,
        workspace_port=None,
        clock: Callable[[], datetime] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._pack_catalog = pack_catalog
        self._progress_repository = progress_repository
        self._workspace = workspace
        self._grader = grader
        self._editor = editor
        self._pack_importer = pack_importer
        self._compiler = compiler
        self._config_repository = config_repository
        self._workspace_port = workspace_port
        self._workspace_root = workspace_root
        self._seen_training_exercises: set[str] = set()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._random = rng or random.Random()
        self._expired_exam: ExamState | None = None

    def list_packs(self) -> list[PackDefinition]:
        return self._pack_catalog.list_packs()

    def list_levels(self, pack_id: str) -> tuple[str, ...]:
        packs = {pack.id: pack for pack in self.list_packs()}
        pack = packs.get(pack_id)
        return () if pack is None else tuple(level.id for level in pack.levels)

    def list_progress(self) -> list[ProgressEntry]:
        return self._progress_repository.list_progress()

    def list_exam_history(self) -> list[dict[str, object]]:
        return self._progress_repository.list_exam_history()

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def change_workspace(self, workspace_path: Path) -> None:
        workspace = Workspace.from_path(workspace_path)
        if self._workspace_port is not None:
            self._workspace_port.ensure_exists(workspace)
        if self._config_repository is not None:
            self._config_repository.save_workspace_path(workspace.path)
        self._workspace_root = workspace.path

    def theme_key(self) -> str | None:
        loader = getattr(self._config_repository, "load_theme", None)
        return loader() if callable(loader) else None

    def save_theme(self, theme_key: str) -> None:
        saver = getattr(self._config_repository, "save_theme", None)
        if callable(saver):
            saver(theme_key)

    def editor_command(self) -> str:
        if self._config_repository is None:
            return "code"
        return self._config_repository.load_editor_command()

    def editor_display_name(self) -> str:
        return editor_display_name(self.editor_command())

    def save_editor_command(self, command: str) -> None:
        executable = validate_editor_executable(command)
        if self._config_repository is not None:
            self._config_repository.save_editor_command(str(executable))
        self._editor = SubprocessEditor(str(executable), editor_display_name(str(executable)))

    def detected_compiler(self) -> str | None:
        if hasattr(self._compiler, "find_compiler"):
            return self._compiler.find_compiler()
        return None

    def current_compiler(self) -> str | None:
        if hasattr(self._compiler, "current_compiler"):
            return self._compiler.current_compiler()
        return None

    def redetect_compiler(self) -> str | None:
        if hasattr(self._compiler, "redetect"):
            return self._compiler.redetect()
        return self.detected_compiler()

    def save_manual_compiler(self, compiler_path: Path) -> None:
        if not hasattr(self._compiler, "validate_compiler"):
            raise ValueError("Compiler adapter does not support manual validation.")
        if not self._compiler.validate_compiler(compiler_path):
            raise ValueError(
                "Nenhum compilador C compatível com os exercícios foi encontrado nesse caminho."
            )
        if hasattr(self._compiler, "set_manual_compiler"):
            self._compiler.set_manual_compiler(str(compiler_path))
        if self._config_repository is not None:
            self._config_repository.save_compiler_path(str(compiler_path))

    def exercise_history_rows(self) -> list[dict[str, object]]:
        progress = self._progress_repository.progress_by_exercise()
        latest = self._progress_repository.latest_attempts_by_exercise()
        modes = self._progress_repository.modes_by_exercise()
        rows: list[dict[str, object]] = []
        for pack in self.list_packs():
            for ref in self._pack_catalog.list_exercises(pack.id):
                entry = progress.get(ref.definition.id)
                latest_attempt = latest.get(ref.definition.id, {})
                status = "não feito"
                if entry is not None:
                    status = "concluído" if entry.best_passed else "tentado"
                rows.append(
                    {
                        "pack": pack.name,
                        "level": ref.level_id,
                        "name": ref.definition.name,
                        "exercise_id": ref.definition.id,
                        "status": status,
                        "attempts": 0 if entry is None else entry.attempts_count,
                        "latest_result": self._format_latest_result(latest_attempt),
                        "last_attempt_at": None if entry is None else entry.last_attempt_at,
                        "modes": ", ".join(sorted(modes.get(ref.definition.id, set()))),
                    }
                )
        return rows

    def exam_history_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for history in self._progress_repository.list_exam_history():
            levels = self._progress_repository.list_exam_level_results(str(history["id"]))
            rows.append(
                {
                    **history,
                    "levels": levels,
                    "exercises": ", ".join(str(level["exercise_id"]) for level in levels),
                }
            )
        return rows

    def inspect_pack(self, source_path: Path):
        """Valida um pack sem copiá-lo; informa se ele traz código executável."""
        return self._pack_importer.inspect_pack(source_path)

    def import_pack(self, source_path: Path) -> PackDefinition:
        return self._pack_importer.import_pack(source_path)

    def compiler_ready(self) -> bool:
        """True se já se sabe, SEM rodar processo externo, que há compilador válido.

        False significa "ainda não verificado": a UI deve chamar `compiler_available`
        fora da thread principal.
        """
        cached = getattr(self._compiler, "cached_compiler", None)
        if cached is None:
            return self._compiler.is_available()  # adapters sem probe (fakes/testes)
        return cached() is not None

    def compiler_available(self) -> bool:
        return self._compiler.is_available()

    def preflight_training(self) -> PreflightResult:
        if not self._workspace_root.exists():
            return PreflightResult.failed("workspace", "Configure a workspace antes de treinar.")
        if not self.list_packs():
            return PreflightResult.failed("packs", "Importe ou recarregue um pack antes de treinar.")
        return PreflightResult.passed()

    def preflight_exam(self) -> PreflightResult:
        training = self.preflight_training()
        if not training.ok:
            return training
        if not self.compiler_available():
            return PreflightResult.failed(
                "compiler",
                "Configure um compilador C compatível antes de iniciar a prova.",
            )
        return PreflightResult.passed()

    def preflight_editor(self) -> PreflightResult:
        try:
            validate_editor_executable(self.editor_command())
        except EditorLaunchError:
            return PreflightResult.failed(
                "editor",
                "Configure um editor/IDE válido antes de abrir a pasta do exercício.",
            )
        return PreflightResult.passed()

    def choose_training_exercise(self, options: TrainingOptions) -> ExerciseRef:
        refs = [
            ref
            for ref in self._pack_catalog.list_exercises(options.pack_id)
            if ref.level_id in options.level_ids
        ]
        if not refs:
            raise ValueError("No exercises available for selected levels.")

        progress = self._progress_repository.progress_by_exercise()
        if not options.allow_repeated:
            unseen = [ref for ref in refs if ref.definition.id not in self._seen_training_exercises]
            if unseen:
                refs = unseen

        if options.selection_mode == "only_uncompleted":
            refs = [
                ref
                for ref in refs
                if not progress.get(ref.definition.id, None)
                or not progress[ref.definition.id].best_passed
            ]
            if not refs:
                raise ValueError("No uncompleted exercises available.")
        elif options.selection_mode == "prioritize_uncompleted":
            uncompleted = [
                ref
                for ref in refs
                if not progress.get(ref.definition.id, None)
                or not progress[ref.definition.id].best_passed
            ]
            if uncompleted:
                refs = uncompleted

        selected = random.choice(refs)
        self._seen_training_exercises.add(selected.definition.id)
        return selected

    def prepare_exercise(self, ref: ExerciseRef, overwrite: bool = False) -> ActiveExercise:
        prepared = self._workspace.prepare(
            definition=ref.definition,
            exercise_content_path=ref.content_path,
            workspace_root=self._workspace_root / "training",
            overwrite=overwrite,
        )
        return ActiveExercise(
            ref=ref,
            exercise_workspace_path=prepared.exercise_workspace_path,
            subject_text=prepared.subject_path.read_text(encoding="utf-8"),
            submission_path=prepared.submission_path,
            had_existing_submission=prepared.had_existing_submission,
        )

    def prepare_exam_exercise(
        self,
        ref: ExerciseRef,
        state: ExamState | None = None,
        overwrite: bool = False,
    ) -> ActiveExercise:
        workspace_root = (
            state.workspace_path.parent if state is not None else self._workspace_root / "exam"
        )
        prepared = self._workspace.prepare(
            definition=ref.definition,
            exercise_content_path=ref.content_path,
            workspace_root=workspace_root,
            overwrite=overwrite,
        )
        return ActiveExercise(
            ref=ref,
            exercise_workspace_path=prepared.exercise_workspace_path,
            subject_text=prepared.subject_path.read_text(encoding="utf-8"),
            submission_path=prepared.submission_path,
            had_existing_submission=prepared.had_existing_submission,
        )

    def open_in_editor(self, active: ActiveExercise) -> None:
        try:
            self._editor.open_directory(active.exercise_workspace_path)
        except EditorLaunchError:
            raise

    def submit_training(self, active: ActiveExercise) -> CorrectionOutcome:
        result = self._grade(active, GradingPolicy.training())
        return self._persist_outcome(active, result, "training")

    def start_exam(self, pack_id: str, duration_seconds: int | None = None) -> ExamState:
        pack = self._pack(pack_id)
        levels = self._exam_levels(pack)
        if not levels:
            raise ValueError("No exercises available for exam.")
        duration = duration_seconds or pack.exam_duration_seconds_or_default
        first = self._random.choice(levels[0][1])
        session_id = str(uuid4())
        now = self._clock()
        state = ExamState(
            id=session_id,
            pack_id=pack_id,
            level_index=0,
            exercise_id=first.definition.id,
            score=0,
            remaining_seconds=duration,
            seed=random.SystemRandom().randint(1, 2**31),
            workspace_path=self._workspace_root / "exam" / session_id / first.definition.id,
            deadline_at=now + timedelta(seconds=duration),
            duration_seconds=duration,
        )
        self._save_exam_state(state, "active")
        return state

    def load_active_exam(self) -> ExamState | None:
        """Carrega a prova ativa. Se o prazo absoluto já passou (inclusive com o app
        fechado), encerra como timeout com a nota parcial e devolve None."""
        row = self._progress_repository.load_active_exam()
        if row is None:
            return None
        now = self._clock()
        deadline = _parse_datetime(row.get("deadline_at"))
        if deadline is None:
            deadline = now + timedelta(seconds=int(row.get("remaining_seconds") or 0))
        state = ExamState(
            id=str(row["id"]),
            pack_id=str(row["rank"]),
            level_index=int(row["current_level"]),
            exercise_id=str(row["current_exercise_id"]),
            score=float(row["score"]),
            remaining_seconds=max(0, int((deadline - now).total_seconds())),
            seed=int(row["seed"]),
            workspace_path=Path(str(row["workspace_path"])),
            deadline_at=deadline,
            duration_seconds=int(row.get("duration_seconds") or row.get("remaining_seconds") or 0),
        )
        if state.remaining_seconds <= 0:
            self.finish_exam(state, "timeout", state.score)
            self._expired_exam = state
            return None
        return state

    def pop_expired_exam(self) -> ExamState | None:
        """Prova que expirou enquanto o app estava fechado (para avisar o usuário uma vez)."""
        expired, self._expired_exam = self._expired_exam, None
        return expired

    def exam_ref(self, state: ExamState) -> ExerciseRef:
        for ref in self._pack_catalog.list_exercises(state.pack_id):
            if ref.definition.id == state.exercise_id:
                return ref
        raise ValueError("Active exam exercise is no longer available.")

    def exam_duration_seconds(self, pack_id: str) -> int:
        return self._pack(pack_id).exam_duration_seconds_or_default

    def submit_exam(self, state: ExamState, active: ActiveExercise) -> tuple[CorrectionOutcome, ExamState | None]:
        result = self._grade(active, GradingPolicy.exam(), seed=state.seed)
        outcome = self._persist_outcome(active, result, "exam")
        self._progress_repository.record_exam_level_result(
            state.id,
            state.level_index,
            active.ref.definition.id,
            result.passed,
            self._progress_repository.attempts_count(active.ref.definition.id),
        )
        if not result.passed:
            self._save_exam_state(state, "active")
            return outcome, state

        levels = self._exam_levels(self._pack(state.pack_id))
        next_index = state.level_index + 1
        if next_index >= len(levels):
            self.finish_exam(state, "completed", 100)
            return outcome, None

        score = (next_index / len(levels)) * 100
        next_ref = self._random.choice(levels[next_index][1])
        next_state = replace(
            state,
            level_index=next_index,
            exercise_id=next_ref.definition.id,
            score=score,
            remaining_seconds=self._remaining(state),
            seed=random.SystemRandom().randint(1, 2**31),
            workspace_path=self._workspace_root / "exam" / state.id / next_ref.definition.id,
        )
        self._save_exam_state(next_state, "active")
        return outcome, next_state

    def tick_exam(self, state: ExamState) -> ExamState | None:
        """Recalcula o tempo restante a partir do deadline absoluto.

        Não grava nada no banco: o deadline já está persistido. Só quando o prazo
        acaba a prova é encerrada (timeout, nota parcial).
        """
        remaining = self._remaining(state)
        if remaining <= 0:
            expired = replace(state, remaining_seconds=0)
            self.finish_exam(expired, "timeout", expired.score)
            return None
        return replace(state, remaining_seconds=remaining)

    def remaining_seconds(self, state: ExamState) -> int:
        """Tempo restante pelo deadline absoluto, sem efeitos colaterais."""
        return self._remaining(state)

    def _remaining(self, state: ExamState) -> int:
        return max(0, int((state.deadline_at - self._clock()).total_seconds()))

    def _pack(self, pack_id: str) -> PackDefinition:
        for pack in self.list_packs():
            if pack.id == pack_id:
                return pack
        raise ValueError(f"Pack not found: {pack_id}")

    def _exam_levels(self, pack: PackDefinition) -> list[tuple[str, list[ExerciseRef]]]:
        """Levels na ordem declarada no pack.json (nunca ordem alfabética), sem levels vazios."""
        refs = self._pack_catalog.list_exercises(pack.id)
        grouped: list[tuple[str, list[ExerciseRef]]] = []
        for level_id in pack.level_ids:
            level_refs = [ref for ref in refs if ref.level_id == level_id]
            if level_refs:
                grouped.append((level_id, level_refs))
        return grouped

    def finish_exam(self, state: ExamState, status: str, final_score: float | None = None) -> None:
        self._progress_repository.finish_exam(state.id, status, state.score if final_score is None else final_score)
        session_root = state.workspace_path.parent
        if session_root.exists() and session_root.parent == self._workspace_root / "exam":
            shutil.rmtree(session_root)

    def _grade(
        self,
        active: ActiveExercise,
        policy: GradingPolicy,
        seed: int | None = None,
    ) -> GradingResult:
        return self._grader.grade(
            GradingRequest(
                definition=active.ref.definition,
                exercise_path=active.ref.content_path,
                workspace_path=active.exercise_workspace_path,
                policy=policy,
                seed=seed,
            )
        )

    def _persist_outcome(
        self,
        active: ActiveExercise,
        result: GradingResult,
        mode: str,
    ) -> CorrectionOutcome:
        self._progress_repository.save_grading_result(
            active.ref.definition.id,
            result,
            mode,
            datetime.now(),
        )
        trace_path = active.exercise_workspace_path / "trace.txt"
        trace_path.write_text(result.trace_data.as_text(), encoding="utf-8")
        return CorrectionOutcome(
            result=result,
            trace_path=trace_path,
            attempts_count=self._progress_repository.attempts_count(active.ref.definition.id),
        )

    def _save_exam_state(self, state: ExamState, status: str) -> None:
        self._progress_repository.save_active_exam(
            {
                "id": state.id,
                "rank": state.pack_id,
                "current_level": state.level_index,
                "current_exercise_id": state.exercise_id,
                "score": state.score,
                "remaining_seconds": state.remaining_seconds,
                "seed": state.seed,
                "status": status,
                "workspace_path": str(state.workspace_path),
                "started_at": datetime.now().isoformat(),
                "finished_at": None,
                "deadline_at": state.deadline_at.isoformat(),
                "duration_seconds": state.duration_seconds,
            }
        )

    @staticmethod
    def _format_latest_result(latest_attempt: dict[str, object]) -> str:
        if not latest_attempt:
            return "-"
        return "PASS" if bool(latest_attempt.get("passed")) else "FAIL"


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
