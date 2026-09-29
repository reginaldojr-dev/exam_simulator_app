"""Execution strategies by neutral type (program_output / function_call).

The strategy only resolves which pack/workspace files form the program. How the
program is prepared and executed is the language runtime's responsibility. There
is no `if language == ...` here.
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
    try:
        root = exercise_path.resolve()
        path = (exercise_path / relative).resolve()
    except OSError as error:
        raise ExecutionPlanError(f"Could not resolve {label}: {error}") from error
    if path != root and root not in path.parents:
        raise ExecutionPlanError(f"Required {label} escapes exercise root: {relative}")
    if not path.is_file():
        raise ExecutionPlanError(f"Required {label} not found: {path}")
    return path


def support_include_dirs(definition: ExerciseDefinition, exercise_path: Path) -> tuple[Path, ...]:
    include_dirs: list[Path] = []
    seen: set[Path] = set()
    for support_file in definition.support_files:
        include_dir = pack_file(exercise_path, support_file, "support file").parent
        if include_dir not in seen:
            include_dirs.append(include_dir)
            seen.add(include_dir)
    return tuple(include_dirs)


class ExecutionStrategy(Protocol):
    kind: str

    def submission(self, definition: ExerciseDefinition, exercise_path: Path, source: Path) -> ProgramSpec: ...


@dataclass(frozen=True)
class ProgramOutputStrategy:
    kind: str = PROGRAM_OUTPUT

    def submission(self, definition: ExerciseDefinition, exercise_path: Path, source: Path) -> ProgramSpec:
        harness = definition.execution.harness
        # v1 reference_compare without a fixture also lands here (harness None).
        return ProgramSpec(
            main_source=source,
            harness=None if harness is None else pack_file(exercise_path, harness, "harness"),
            entry=definition.execution.entry,
            extra_sources=tuple(source.parent / extra for extra in definition.submission.extra_files),
            include_dirs=support_include_dirs(definition, exercise_path),
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
            include_dirs=support_include_dirs(definition, exercise_path),
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
        include_dirs=support_include_dirs(definition, exercise_path),
    )


def default_execution_strategies() -> dict[str, ExecutionStrategy]:
    return {strategy.kind: strategy for strategy in (ProgramOutputStrategy(), FunctionCallStrategy())}
