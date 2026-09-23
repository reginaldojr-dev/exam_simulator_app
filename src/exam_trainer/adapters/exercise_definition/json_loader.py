from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path, PurePath
from typing import Any

from exam_trainer.application.capabilities import (
    HARNESS_FROM_APP,
    HARNESS_FROM_PACK,
    ExerciseCapabilities,
    default_exercise_capabilities,
)
from exam_trainer.domain.identifiers import (
    UnsafeValueError,
    parse_relative_path,
    validate_identifier,
    validate_simple_filename,
)
from exam_trainer.domain.exercise_definition import (
    FUNCTION_CALL,
    PROGRAM_OUTPUT,
    ExerciseDefinition,
    ExecutionDefinition,
    LimitsDefinition,
    ReferenceDefinition,
    SubmissionDefinition,
    TestCaseDefinition,
    TestDefinition,
)
from exam_trainer.adapters.contract_fields import read_schema_version, read_topics
from exam_trainer.domain.pack_definition import DEFAULT_LANGUAGE


DEFAULT_TIMEOUT_SECONDS = 2
V2_EXERCISE_KEYS = frozenset(
    (
        "schema_version",
        "id",
        "name",
        "subject",
        "topics",
        "submission",
        "execution",
        "reference",
        "tests",
        "limits",
        "support_files",
    )
)



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

    def load(self, exercise_json_path: Path | str, language: str = DEFAULT_LANGUAGE) -> ExerciseDefinition:
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

        return self.load_data(raw_data, language)

    def load_data(self, raw_data: Any, language: str = DEFAULT_LANGUAGE) -> ExerciseDefinition:
        """Carrega v1 ou v2 e normaliza para o modelo neutro.

        `language` vem do pack (v1 = "c"). O exercício herda a linguagem do pack.
        """
        data = self._require_object(raw_data, "exercise definition")
        schema_version = read_schema_version(data, ExerciseDefinitionError)
        support = self._capabilities.language(language)
        if support is None:
            raise ExerciseDefinitionError(f"Unsupported language: {language}.")
        if schema_version >= 2:
            unknown = sorted(set(data) - V2_EXERCISE_KEYS)
            if unknown:
                raise ExerciseDefinitionError(f"Unknown field(s) in exercise.json v2: {', '.join(unknown)}.")

        exercise_id = self._require_identifier(data, "id")
        name = self._require_non_empty_string(data, "name")
        subject = self._require_relative_path(data, "subject")
        submission = self._read_submission(self._require_object_field(data, "submission"))
        execution, legacy_reference = self._read_execution(
            self._require_object_field(data, "execution"), language
        )
        reference = legacy_reference
        if "reference" in data:
            if schema_version < 2:
                raise ExerciseDefinitionError("Top-level reference requires schema_version 2.")
            if legacy_reference is not None:
                raise ExerciseDefinitionError("Declare the reference only once (top-level reference).")
            reference = self._read_reference(data["reference"])
        tests = self._read_tests(self._require_object_field(data, "tests"))
        if tests.expectation == "reference_output" and reference is None and schema_version >= 2:
            raise ExerciseDefinitionError("expectation reference_output requires a reference.")
        limits = self._read_limits(data.get("limits", {}))
        support_files = self._read_support_files(data.get("support_files", []))
        topics = read_topics(data.get("topics", []), ExerciseDefinitionError)
        if reference is not None and execution.reference != reference.source:
            execution = replace(execution, reference=reference.source)

        return ExerciseDefinition(
            id=exercise_id,
            name=name,
            subject=subject,
            submission=submission,
            execution=execution,
            tests=tests,
            limits=limits,
            support_files=support_files,
            reference=reference,
            topics=topics,
            schema_version=schema_version,
            language=language,
        )

    def _read_submission(self, data: dict[str, Any]) -> SubmissionDefinition:
        filename = self._require_non_empty_string(data, "filename")
        self._validate_filename(filename)
        return SubmissionDefinition(filename=filename)

    def _read_execution(
        self, data: dict[str, Any], language: str
    ) -> tuple[ExecutionDefinition, ReferenceDefinition | None]:
        declared = self._require_identifier(data, "type")
        if not self._capabilities.executions.supports(declared):
            raise ExerciseDefinitionError(f"Unknown execution type: {declared}.")
        support = self._capabilities.language(language)
        assert support is not None  # validado em load_data

        if "fixture" in data and "harness" in data:
            raise ExerciseDefinitionError("Use execution.harness or execution.fixture, not both.")
        fixture = None
        for key in ("harness", "fixture"):
            if key in data:
                fixture = self._read_relative_path_value(data[key], f"execution.{key}")
        legacy_reference_path = None
        if "reference" in data:
            legacy_reference_path = self._read_relative_path_value(data["reference"], "execution.reference")
        entry = None
        if "entry" in data:
            entry = self._require_identifier(data, "entry")
        args_format = None
        if "args_format" in data:
            args_format = self._require_identifier(data, "args_format")

        # ---- normalização dos aliases do v1 -------------------------------------
        kind = declared
        legacy_reference = None
        if declared == "function_with_main":
            if fixture is None:
                raise ExerciseDefinitionError("execution.fixture is required for function_with_main.")
            kind = FUNCTION_CALL
        elif declared == "reference_compare":
            if legacy_reference_path is None:
                raise ExerciseDefinitionError("execution.reference is required for reference_compare.")
            kind = FUNCTION_CALL if fixture is not None else PROGRAM_OUTPUT
            legacy_reference = ReferenceDefinition(source=legacy_reference_path, harness=fixture)
        elif legacy_reference_path is not None:
            raise ExerciseDefinitionError(
                "execution.reference is only valid with reference_compare; use a top-level reference."
            )

        # ---- regras por linguagem ------------------------------------------------
        if kind not in support.executions:
            raise ExerciseDefinitionError(
                f"Execution type {declared} is not supported for language {language}."
            )
        if kind == FUNCTION_CALL and support.function_harness == HARNESS_FROM_PACK and fixture is None:
            raise ExerciseDefinitionError(
                f"execution.harness is required for function_call in {language} (the pack provides it)."
            )
        if support.function_harness == HARNESS_FROM_APP:
            if fixture is not None:
                raise ExerciseDefinitionError(
                    f"execution.harness is not allowed for {language}: the app provides the harness."
                )
            if kind == FUNCTION_CALL:
                if entry is None:
                    raise ExerciseDefinitionError(f"execution.entry is required for function_call in {language}.")
                args_format = args_format or "json"
                if args_format not in support.args_formats:
                    raise ExerciseDefinitionError(f"Unsupported execution.args_format: {args_format}.")
        elif entry is not None or args_format is not None:
            raise ExerciseDefinitionError(
                f"execution.entry/args_format are not used for {language}; declare a harness instead."
            )

        execution = ExecutionDefinition(
            type=kind,
            fixture=fixture,
            reference=legacy_reference_path,
            entry=entry,
            args_format=args_format,
            declared_type=declared,
        )
        return execution, legacy_reference

    def _read_reference(self, raw: Any) -> ReferenceDefinition:
        data = self._require_object(raw, "reference")
        unknown = sorted(set(data) - {"source", "harness"})
        if unknown:
            raise ExerciseDefinitionError(f"Unknown field(s) in reference: {', '.join(unknown)}.")
        source = self._require_relative_path(data, "source")
        harness = None
        if "harness" in data:
            harness = self._read_relative_path_value(data["harness"], "reference.harness")
        return ReferenceDefinition(source=source, harness=harness)

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
        try:
            return validate_identifier(value, field_name)
        except UnsafeValueError as error:
            raise ExerciseDefinitionError(str(error)) from error

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
        try:
            return parse_relative_path(value, field_name)
        except UnsafeValueError as error:
            raise ExerciseDefinitionError(str(error)) from error

    @staticmethod
    def _validate_filename(filename: str) -> None:
        try:
            validate_simple_filename(filename, "submission.filename")
        except UnsafeValueError as error:
            raise ExerciseDefinitionError(str(error)) from error
