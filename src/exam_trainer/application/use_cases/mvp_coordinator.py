from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from exam_trainer.application.mvp_models import (
    ActiveExercise,
    CorrectionOutcome,
    ExerciseRef,
    ProgressEntry,
)
from exam_trainer.domain.attempt_modes import EXAM_MODE, LEGACY_PACK_ID, TRAINING_MODE
from exam_trainer.domain.grading import GradingPolicy, GradingResult
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry
from exam_trainer.domain.pack_definition import PackDefinition
from exam_trainer.ports.config_repository import AppSettingsRepository
from exam_trainer.ports.progress_repository import TrainerProgressRepository
from exam_trainer.ports.runtime_port import LanguageRuntime, RuntimeStatus
from exam_trainer.domain.workspace import Workspace
from exam_trainer.ports.editor_port import EditorFactory, EditorLaunchError, EditorPort
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
        progress_repository: TrainerProgressRepository,
        workspace: ExerciseWorkspacePort,
        grader: GraderPort,
        editor: EditorPort,
        pack_importer,
        runtimes: RuntimeRegistry,
        workspace_root: Path,
        editor_factory: EditorFactory,
        config_repository: AppSettingsRepository | None = None,
        workspace_port=None,
        clock: Callable[[], datetime] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        """`runtimes`: um runtime por linguagem, montado por quem compõe o app
        (composition root ou o próprio teste) — a application nunca instancia um adapter
        de runtime concreto. O mesmo vale para `editor_factory`: quem sabe criar/validar
        um editor concreto é o adapter, não o coordinator."""
        self._pack_catalog = pack_catalog
        self._progress_repository = progress_repository
        self._workspace = workspace
        self._grader = grader
        self._editor = editor
        self._pack_importer = pack_importer
        self._runtimes = runtimes
        self._editor_factory = editor_factory
        self._config_repository = config_repository
        self._workspace_port = workspace_port
        self._workspace_root = workspace_root
        self._seen_training_exercises: set[tuple[str, str]] = set()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._random = rng or random.Random()
        self._expired_exam: ExamState | None = None
        self.adopt_legacy_progress()

    def adopt_legacy_progress(self) -> int:
        """Associa tentativas antigas (sem pack) ao pack instalado que declara o exercício.

        Só quando o exercise_id existe em exatamente um pack; nunca apaga nada. Falhas
        aqui não podem impedir o app de abrir.
        """
        try:
            owners: dict[str, set[str]] = {}
            for pack in self.list_packs():
                for ref in self._pack_catalog.list_exercises(pack.id):
                    owners.setdefault(ref.definition.id, set()).add(pack.id)
            unique = {exercise_id: next(iter(packs)) for exercise_id, packs in owners.items() if len(packs) == 1}
            return self._progress_repository.adopt_legacy_attempts(unique)
        except Exception:  # noqa: BLE001 — migração oportunista, nunca bloqueia
            return 0

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
        return None if self._config_repository is None else self._config_repository.load_theme()

    def save_theme(self, theme_key: str) -> None:
        if self._config_repository is not None:
            self._config_repository.save_theme(theme_key)

    def editor_command(self) -> str:
        if self._config_repository is None:
            return "code"
        return self._config_repository.load_editor_command()

    def editor_display_name(self) -> str:
        return self._editor_factory.display_name(self.editor_command())

    def resolve_known_editor(self, label: str) -> str | None:
        return self._editor_factory.resolve_known(label)

    def save_editor_command(self, command: str) -> None:
        executable = self._editor_factory.validate(command)
        if self._config_repository is not None:
            self._config_repository.save_editor_command(str(executable))
        self._editor = self._editor_factory.create(str(executable))

    # ---------------------------------------------------------------- runtimes
    def runtime(self, language: str) -> LanguageRuntime:
        return self._runtimes.get(language)

    def supported_languages(self) -> tuple[str, ...]:
        return self._runtimes.languages()

    def runtime_statuses(self, probe: bool = False) -> tuple[RuntimeStatus, ...]:
        return self._runtimes.statuses(probe=probe)

    def runtime_status(self, language: str, probe: bool = False) -> RuntimeStatus:
        return self._runtimes.status(language, probe=probe)

    def runtime_display_name(self, language: str) -> str:
        return self.runtime_status(language).display_name

    def runtime_current_tool(self, language: str) -> str | None:
        return self.runtime_status(language).tool

    def redetect_runtime(self, language: str) -> str | None:
        return self.runtime(language).redetect()

    def pack_language(self, pack_id: str | None) -> str:
        languages = self.pack_languages(pack_id)
        if languages:
            return languages[0]
        primary = self._runtimes.primary_language()
        if primary is not None:
            return primary
        for pack in self.list_packs():
            if pack.id == pack_id:
                return pack.language
        return ""

    def pack_languages(self, pack_id: str | None) -> tuple[str, ...]:
        if pack_id is None:
            return ()
        refs = self._pack_catalog.list_exercises(pack_id)
        if refs:
            return tuple(sorted({ref.definition.language for ref in refs}))
        for pack in self.list_packs():
            if pack.id == pack_id:
                return (pack.language,)
        return ()

    def runtime_ready(self, language: str) -> bool:
        """Sem processo externo: seguro na thread da UI. False = ainda não verificado."""
        return self._runtimes.has(language) and self._runtimes.get(language).is_ready()

    def runtime_available(self, language: str) -> bool:
        """Pode rodar processos (probe). Chamar fora da thread da UI."""
        return self._runtimes.has(language) and self._runtimes.get(language).check_available()

    # C: atalhos usados pela tela de Configurações > Compilador
    def current_compiler(self) -> str | None:
        language = self._runtimes.primary_language()
        return None if language is None else self.runtime_current_tool(language)

    def redetect_compiler(self) -> str | None:
        language = self._runtimes.primary_language()
        return None if language is None else self.redetect_runtime(language)

    def save_manual_compiler(self, compiler_path: Path) -> None:
        language = self._runtimes.primary_language()
        if language is None:
            raise ValueError("Nenhum runtime registrado.")
        self.save_manual_runtime(language, compiler_path)

    def save_manual_runtime(self, language: str, path: Path) -> str:
        """Valida (roda o probe) e grava a ferramenta escolhida para a linguagem."""
        configured = self.runtime(language).configure_manual(path)
        if self._config_repository is not None:
            self._config_repository.save_runtime_path(language, str(path))
        return configured

    def exercise_history_rows(self) -> list[dict[str, object]]:
        """Uma linha por exercício de cada pack instalado + tentativas de packs ausentes/legados.

        Status/tentativas refletem só o TREINO (ADR 0003); `modes` mostra se já foi feito em prova.
        """
        progress = self._progress_repository.progress_by_key()
        latest = self._progress_repository.latest_attempts()
        modes = self._progress_repository.modes_by_key()
        rows: list[dict[str, object]] = []
        shown: set[tuple[str, str]] = set()

        def row(pack_name: str, level: str, name: str, key: tuple[str, str]) -> dict[str, object]:
            entry = progress.get(key)
            status = "não feito"
            if entry is not None:
                status = "concluído" if entry.best_passed else "tentado"
            return {
                "pack": pack_name,
                "pack_id": key[0],
                "level": level,
                "name": name,
                "exercise_id": key[1],
                "status": status,
                "attempts": 0 if entry is None else entry.attempts_count,
                "latest_result": self._format_latest_result(latest.get(key, {})),
                "last_attempt_at": None if entry is None else entry.last_attempt_at,
                "modes": ", ".join(sorted(modes.get(key, set()))),
            }

        for pack in self.list_packs():
            for ref in self._pack_catalog.list_exercises(pack.id):
                key = (pack.id, ref.definition.id)
                shown.add(key)
                rows.append(row(pack.name, ref.level_id, ref.definition.name, key))
        for key in sorted(self._progress_repository.attempt_keys() - shown):
            label = "(legado)" if key[0] == LEGACY_PACK_ID else f"{key[0]} (não instalado)"
            rows.append(row(label, "-", key[1], key))
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
        language = self._runtimes.primary_language()
        return False if language is None else self.runtime_ready(language)

    def compiler_available(self) -> bool:
        language = self._runtimes.primary_language()
        return False if language is None else self.runtime_available(language)

    def preflight_training(self) -> PreflightResult:
        if not self._workspace_root.exists():
            return PreflightResult.failed("workspace", "Configure a workspace antes de treinar.")
        if not self.list_packs():
            return PreflightResult.failed("packs", "Importe ou recarregue um pack antes de treinar.")
        return PreflightResult.passed()

    def preflight_exam(self, pack_id: str | None = None) -> PreflightResult:
        training = self.preflight_training()
        if not training.ok:
            return training
        languages = self.pack_languages(pack_id)
        if not languages:
            return PreflightResult.failed("packs", "Pack selecionado sem exercícios disponíveis.")
        return self._preflight_languages(languages)

    def preflight_runtime(self, language: str) -> PreflightResult:
        """O runtime da linguagem do pack está pronto? (pode rodar o probe)."""
        return self._preflight_languages((language,))

    def preflight_exercise(self, ref: ExerciseRef) -> PreflightResult:
        return self.preflight_runtime(ref.definition.language)

    def pack_runtimes_ready(self, pack_id: str | None) -> bool:
        languages = self.pack_languages(pack_id)
        return bool(languages) and all(self.runtime_ready(language) for language in languages)

    def _preflight_languages(self, languages: tuple[str, ...]) -> PreflightResult:
        failures: list[RuntimeStatus] = []
        for language in languages:
            status = self._runtimes.status(language, probe=True)
            if not status.supported or not status.available:
                failures.append(status)
        if not failures:
            return PreflightResult.passed()
        if len(failures) == 1:
            failure = failures[0]
            if not failure.supported:
                return PreflightResult.failed(
                    "Runtimes",
                    f"Este app não executa exercícios em '{failure.language}'. Atualize o app ou use outro pack.",
                )
            return PreflightResult.failed(
                "Runtimes",
                f"{failure.display_name} não encontrado.\n"
                "Instale ou configure um runtime compatível para corrigir este exercício.",
            )
        missing = ", ".join(f"{failure.display_name} ({failure.language})" for failure in failures)
        return PreflightResult.failed(
            "Runtimes",
            f"Runtimes/toolchains indisponíveis para este pack: {missing}.",
        )

    def preflight_editor(self) -> PreflightResult:
        try:
            self._editor_factory.validate(self.editor_command())
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

        progress = self._progress_repository.progress_by_exercise(options.pack_id)
        if not options.allow_repeated:
            unseen = [
                ref
                for ref in refs
                if (options.pack_id, ref.definition.id) not in self._seen_training_exercises
            ]
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

        selected = self._random.choice(refs)
        self._seen_training_exercises.add((options.pack_id, selected.definition.id))
        return selected

    def training_workspace_root(self, pack_id: str) -> Path:
        return self._workspace_root / "training" / pack_id

    def prepare_exercise(self, ref: ExerciseRef, overwrite: bool = False) -> ActiveExercise:
        training_root = self.training_workspace_root(ref.pack.id)
        self._migrate_legacy_training_workspace(training_root, ref.definition.id)
        prepared = self._workspace.prepare(
            definition=ref.definition,
            exercise_content_path=ref.content_path,
            workspace_root=training_root,
            overwrite=overwrite,
        )
        return ActiveExercise(
            ref=ref,
            exercise_workspace_path=prepared.exercise_workspace_path,
            subject_text=prepared.subject_path.read_text(encoding="utf-8"),
            submission_path=prepared.submission_path,
            had_existing_submission=prepared.had_existing_submission,
        )

    def _migrate_legacy_training_workspace(self, training_root: Path, exercise_id: str) -> None:
        """Move `training/<exercise_id>/` (layout antigo) para `training/<pack_id>/<exercise_id>/`.

        Só move quando o destino ainda não existe e a pasta antiga é mesmo um workspace de
        exercício (tem `subject.txt`). Nunca apaga nada; se não der para mover, deixa como está.
        """
        legacy = self._workspace_root / "training" / exercise_id
        target = training_root / exercise_id
        if legacy == training_root or target.exists() or not (legacy / "subject.txt").is_file():
            return
        self._workspace.move_directory(legacy, target)

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
        return self._persist_outcome(active, result, TRAINING_MODE)

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
        outcome = self._persist_outcome(active, result, EXAM_MODE, session_id=state.id)
        self._progress_repository.record_exam_level_result(
            state.id,
            state.level_index,
            active.ref.definition.id,
            result.passed,
            outcome.attempts_count,
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
        if session_root.parent == self._workspace_root / "exam":
            self._workspace.remove_directory(session_root)

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
        session_id: str | None = None,
    ) -> CorrectionOutcome:
        pack_id = active.ref.pack.id
        exercise_id = active.ref.definition.id
        self._progress_repository.save_grading_result(
            pack_id,
            exercise_id,
            result,
            mode,
            datetime.now(),
            session_id=session_id,
        )
        trace_path = active.exercise_workspace_path / "trace.txt"
        trace_path.write_text(result.trace_data.as_text(), encoding="utf-8")
        return CorrectionOutcome(
            result=result,
            trace_path=trace_path,
            # treino: tentativas de treino desse exercício; prova: tentativas nesta sessão
            attempts_count=self._progress_repository.attempts_count(
                pack_id, exercise_id, mode, session_id=session_id
            ),
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
