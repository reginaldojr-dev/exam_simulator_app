from __future__ import annotations

import json
from pathlib import Path, PurePath
from typing import Any

from exam_trainer.application.capabilities import (
    ExerciseCapabilities,
    default_exercise_capabilities,
)
from exam_trainer.domain.exercise_definition import (
    ExerciseDefinition,
    ExecutionDefinition,
    LimitsDefinition,
    SubmissionDefinition,
    TestCaseDefinition,
    TestDefinition,
)


DEFAULT_TIMEOUT_SECONDS = 2


class ExerciseDefinitionError(ValueError):
    """Raised when an exercise definition cannot be loaded or validated."""


class JsonExerciseDefinitionLoader:
    def __init__(
        self,
        capabilities: ExerciseCapabilities | None = None,
        default_timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._capabilities = capabilities or default_exercise_capabilities()
        self._default_timeout_seconds = default_timeout_seconds

    def load(self, exercise_json_path: Path | str) -> ExerciseDefinition:
        path = Path(exercise_json_path)
        try:
            raw_data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ExerciseDefinitionError(
                f"Invalid JSON in exercise definition: {error.msg}."
            ) from error
        except OSError as error:
            raise ExerciseDefinitionError(
                f"Could not read exercise definition: {error}."
            ) from error

        return self.load_data(raw_data)

    def load_data(self, raw_data: Any) -> ExerciseDefinition:
        data = self._require_object(raw_data, "exercise definition")

        exercise_id = self._require_identifier(data, "id")
        name = self._require_non_empty_string(data, "name")
        subject = self._require_relative_path(data, "subject")
        submission = self._read_submission(self._require_object_field(data, "submission"))
        execution = self._read_execution(self._require_object_field(data, "execution"))
        tests = self._read_tests(self._require_object_field(data, "tests"))
        limits = self._read_limits(data.get("limits", {}))
        support_files = self._read_support_files(data.get("support_files", []))

        return ExerciseDefinition(
            id=exercise_id,
            name=name,
            subject=subject,
            submission=submission,
            execution=execution,
            tests=tests,
            limits=limits,
            support_files=support_files,
        )

    def _read_submission(self, data: dict[str, Any]) -> SubmissionDefinition:
        filename = self._require_non_empty_string(data, "filename")
        self._validate_filename(filename)
        return SubmissionDefinition(filename=filename)

    def _read_execution(self, data: dict[str, Any]) -> ExecutionDefinition:
        execution_type = self._require_identifier(data, "type")
        if not self._capabilities.executions.supports(execution_type):
            raise ExerciseDefinitionError(f"Unknown execution type: {execution_type}.")

        fixture = None
        if "fixture" in data:
            fixture = self._read_relative_path_value(data["fixture"], "execution.fixture")
        reference = None
        if "reference" in data:
            reference = self._read_relative_path_value(data["reference"], "execution.reference")

        if execution_type == "function_with_main" and fixture is None:
            raise ExerciseDefinitionError(
                "execution.fixture is required for function_with_main."
            )
        if execution_type == "reference_compare" and reference is None:
            raise ExerciseDefinitionError(
                "execution.reference is required for reference_compare."
            )

        return ExecutionDefinition(type=execution_type, fixture=fixture, reference=reference)

    def _read_tests(self, data: dict[str, Any]) -> TestDefinition:
        generator = self._require_identifier(data, "generator")
        if not self._capabilities.generators.supports(generator):
            raise ExerciseDefinitionError(f"Unknown test generator: {generator}.")

        expectation = self._require_identifier(data, "expectation")
        if not self._capabilities.expectations.supports(expectation):
            raise ExerciseDefinitionError(f"Unknown test expectation: {expectation}.")

        cases = self._read_cases(data.get("cases", []))
        if generator == "fixed_cases" and not cases:
            raise ExerciseDefinitionError("tests.cases is required for fixed_cases.")

        return TestDefinition(generator=generator, expectation=expectation, cases=cases)

    def _read_cases(self, raw_cases: Any) -> tuple[TestCaseDefinition, ...]:
        if not isinstance(raw_cases, list):
            raise ExerciseDefinitionError("tests.cases must be a list.")

        cases: list[TestCaseDefinition] = []
        for index, raw_case in enumerate(raw_cases):
            case_name = f"tests.cases[{index}]"
            case = self._require_object(raw_case, case_name)
            raw_args = case.get("args", [])
            if not isinstance(raw_args, list) or not all(
                isinstance(arg, str) for arg in raw_args
            ):
                raise ExerciseDefinitionError(f"{case_name}.args must be a list of strings.")
            stdin = case.get("stdin", "")
            if not isinstance(stdin, str):
                raise ExerciseDefinitionError(f"{case_name}.stdin must be a string.")
            expected = case.get("expected")
            if expected is not None and not isinstance(expected, str):
                raise ExerciseDefinitionError(f"{case_name}.expected must be a string.")
            cases.append(
                TestCaseDefinition(args=tuple(raw_args), stdin=stdin, expected=expected)
            )
        return tuple(cases)

    def _read_limits(self, raw_limits: Any) -> LimitsDefinition:
        limits = self._require_object(raw_limits, "limits")
        timeout_seconds = limits.get("timeout_seconds", self._default_timeout_seconds)

        if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
            raise ExerciseDefinitionError("limits.timeout_seconds must be an integer.")
        if timeout_seconds <= 0:
            raise ExerciseDefinitionError("limits.timeout_seconds must be greater than zero.")

        return LimitsDefinition(timeout_seconds=timeout_seconds)

    def _read_support_files(self, raw_support_files: Any) -> tuple[PurePath, ...]:
        if not isinstance(raw_support_files, list):
            raise ExerciseDefinitionError("support_files must be a list.")
        return tuple(
            self._read_relative_path_value(value, f"support_files[{index}]")
            for index, value in enumerate(raw_support_files)
        )

    def _require_object_field(
        self,
        data: dict[str, Any],
        field_name: str,
    ) -> dict[str, Any]:
        if field_name not in data:
            raise ExerciseDefinitionError(f"Missing required field: {field_name}.")
        return self._require_object(data[field_name], field_name)

    @staticmethod
    def _require_object(raw_data: Any, field_name: str) -> dict[str, Any]:
        if not isinstance(raw_data, dict):
            raise ExerciseDefinitionError(f"{field_name} must be an object.")
        return raw_data

    def _require_identifier(self, data: dict[str, Any], field_name: str) -> str:
        value = self._require_non_empty_string(data, field_name)
        if any(separator in value for separator in (" ", "/", "\\")):
            raise ExerciseDefinitionError(
                f"{field_name} must be a stable identifier without spaces or path separators."
            )
        return value

    @staticmethod
    def _require_non_empty_string(data: dict[str, Any], field_name: str) -> str:
        if field_name not in data:
            raise ExerciseDefinitionError(f"Missing required field: {field_name}.")

        value = data[field_name]
        if not isinstance(value, str):
            raise ExerciseDefinitionError(f"{field_name} must be a string.")

        stripped = value.strip()
        if not stripped:
            raise ExerciseDefinitionError(f"{field_name} cannot be empty.")

        return stripped

    def _require_relative_path(self, data: dict[str, Any], field_name: str) -> PurePath:
        value = self._require_non_empty_string(data, field_name)
        return self._read_relative_path_value(value, field_name)

    @staticmethod
    def _read_relative_path_value(value: Any, field_name: str) -> PurePath:
        if not isinstance(value, str):
            raise ExerciseDefinitionError(f"{field_name} must be a string.")
        if not value.strip():
            raise ExerciseDefinitionError(f"{field_name} cannot be empty.")

        path = PurePath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ExerciseDefinitionError(f"{field_name} must be a relative path.")
        return path

    @staticmethod
    def _validate_filename(filename: str) -> None:
        path = PurePath(filename)
        if path.is_absolute() or len(path.parts) != 1 or filename in (".", ".."):
            raise ExerciseDefinitionError("submission.filename must be a simple filename.")
