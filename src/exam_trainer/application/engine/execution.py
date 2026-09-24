"""Estratégias de execução por tipo NEUTRO (program_output / function_call).

A estratégia só resolve QUAIS arquivos do pack/workspace formam o programa; COMO ele é
preparado e executado é problema do runtime da linguagem. Não há `if language == ...` aqui.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Protocol

from exam_trainer.domain.exercise_definition import FUNCTION_CALL, PROGRAM_OUTPUT, ExerciseDefinition
from exam_trainer.ports.runtime_port import ProgramSpec


class ExecutionPlanError(ValueError):
    pass


def pack_file(exercise_path: Path, relative: PurePath, label: str) -> Path:
    path = exercise_path / relative
    if not path.is_file():
        raise ExecutionPlanError(f"Required {label} not found: {path}")
    return path


class ExecutionStrategy(Protocol):
    kind: str

    def submission(self, definition: ExerciseDefinition, exercise_path: Path, source: Path) -> ProgramSpec: ...


@dataclass(frozen=True)
class ProgramOutputStrategy:
    kind: str = PROGRAM_OUTPUT

    def submission(self, definition: ExerciseDefinition, exercise_path: Path, source: Path) -> ProgramSpec:
        harness = definition.execution.harness
        # v1 reference_compare sem fixture também cai aqui (harness None).
        return ProgramSpec(
            main_source=source,
            harness=None if harness is None else pack_file(exercise_path, harness, "harness"),
            entry=definition.execution.entry,
            extra_sources=tuple(source.parent / extra for extra in definition.submission.extra_files),
        )


@dataclass(frozen=True)
class FunctionCallStrategy:
    kind: str = FUNCTION_CALL

    def submission(self, definition: ExerciseDefinition, exercise_path: Path, source: Path) -> ProgramSpec:
        execution = definition.execution
        if execution.harness is None and execution.entry is None:
            raise ExecutionPlanError("Missing harness declaration for function_call.")
        return ProgramSpec(
            main_source=source,
            harness=None if execution.harness is None else pack_file(exercise_path, execution.harness, "harness"),
            entry=execution.entry,
            args_format=execution.args_format,
            extra_sources=tuple(source.parent / extra for extra in definition.submission.extra_files),
        )


def reference_spec(definition: ExerciseDefinition, exercise_path: Path) -> ProgramSpec:
    reference = definition.reference
    if reference is None:
        raise ExecutionPlanError("Missing reference declaration.")
    return ProgramSpec(
        main_source=pack_file(exercise_path, reference.source, "reference"),
        harness=None if reference.harness is None else pack_file(exercise_path, reference.harness, "harness"),
        entry=definition.execution.entry,
        args_format=definition.execution.args_format,
        extra_sources=tuple(pack_file(exercise_path, extra, "reference extra source") for extra in reference.extra_files),
    )


def default_execution_strategies() -> dict[str, ExecutionStrategy]:
    return {strategy.kind: strategy for strategy in (ProgramOutputStrategy(), FunctionCallStrategy())}
