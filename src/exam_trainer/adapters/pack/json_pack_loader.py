from __future__ import annotations

import json
from pathlib import Path, PurePath
from typing import Any

from exam_trainer.adapters.contract_fields import read_schema_version, read_topics
from exam_trainer.application.capabilities import default_exercise_capabilities
from exam_trainer.domain.identifiers import UnsafeValueError, parse_relative_path, validate_identifier
from exam_trainer.domain.pack_definition import DEFAULT_LANGUAGE, PackDefinition, PackLevelDefinition

MAX_EXAM_DURATION_MINUTES = 24 * 60
V2_PACK_KEYS = frozenset(
    (
        "schema_version",
        "id",
        "name",
        "version",
        "language",
        "languages",
        "topics",
        "description",
        "exam",
        "levels",
    )
)


class PackDefinitionError(ValueError):
    pass


class JsonPackLoader:
    def __init__(self, supported_languages: frozenset[str] | None = None) -> None:
        # None = pega das capabilities padrão do app.
        if supported_languages is None:
            supported_languages = frozenset(default_exercise_capabilities().languages)
        self._languages = supported_languages

    def load(self, pack_json_path: Path | str) -> PackDefinition:
        path = Path(pack_json_path)
        try:
            raw_data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise PackDefinitionError(f"Invalid JSON in pack definition: {error.msg}.") from error
        except OSError as error:
            raise PackDefinitionError(f"Could not read pack definition: {error}.") from error

        data = self._require_object(raw_data, "pack definition")
        schema_version = read_schema_version(data, PackDefinitionError)
        if schema_version >= 2:
            unknown = sorted(set(data) - V2_PACK_KEYS)
            if unknown:
                raise PackDefinitionError(f"Unknown field(s) in pack.json v2: {', '.join(unknown)}.")
            language = self._require_identifier(data, "language") if "language" in data else DEFAULT_LANGUAGE
            topics = read_topics(data.get("topics", []), PackDefinitionError)
        else:
            # v1: sem language/topics. Campos extras continuam ignorados como antes.
            language, topics = DEFAULT_LANGUAGE, ()
        if language not in self._languages:
            supported = ", ".join(sorted(self._languages))
            raise PackDefinitionError(f"Unsupported language: {language} (supported: {supported}).")
        pack_id = self._require_identifier(data, "id")
        name = self._require_non_empty_string(data, "name")
        version = self._require_non_empty_string(data, "version")
        levels = self._read_levels(data)
        exam_duration_seconds = self._read_exam_duration(data)
        return PackDefinition(
            id=pack_id,
            name=name,
            version=version,
            levels=levels,
            exam_duration_seconds=exam_duration_seconds,
            schema_version=schema_version,
            language=language,
            topics=topics,
        )

    def _read_exam_duration(self, data: dict[str, Any]) -> int | None:
        if "exam" not in data:
            return None
        exam = self._require_object(data["exam"], "exam")
        if "duration_minutes" not in exam:
            return None
        minutes = exam["duration_minutes"]
        if not isinstance(minutes, int) or isinstance(minutes, bool):
            raise PackDefinitionError("exam.duration_minutes must be an integer.")
        if not 1 <= minutes <= MAX_EXAM_DURATION_MINUTES:
            raise PackDefinitionError(
                f"exam.duration_minutes must be between 1 and {MAX_EXAM_DURATION_MINUTES}."
            )
        return minutes * 60

    def _read_levels(self, data: dict[str, Any]) -> tuple[PackLevelDefinition, ...]:
        if "levels" not in data:
            raise PackDefinitionError("Missing required field: levels.")
        raw_levels = data["levels"]
        if not isinstance(raw_levels, list) or not raw_levels:
            raise PackDefinitionError("levels must be a non-empty list.")

        levels: list[PackLevelDefinition] = []
        seen: set[str] = set()
        for index, raw_level in enumerate(raw_levels):
            level_data = self._require_object(raw_level, f"levels[{index}]")
            level_id = self._require_identifier(level_data, "id")
            level_path = self._require_relative_path(level_data, "path")
            if level_id in seen:
                raise PackDefinitionError(f"Duplicated level id: {level_id}.")
            seen.add(level_id)
            levels.append(PackLevelDefinition(id=level_id, path=level_path))
        return tuple(levels)

    @staticmethod
    def _require_object(raw_data: Any, field_name: str) -> dict[str, Any]:
        if not isinstance(raw_data, dict):
            raise PackDefinitionError(f"{field_name} must be an object.")
        return raw_data

    def _require_identifier(self, data: dict[str, Any], field_name: str) -> str:
        value = self._require_non_empty_string(data, field_name)
        try:
            return validate_identifier(value, field_name)
        except UnsafeValueError as error:
            raise PackDefinitionError(str(error)) from error

    @staticmethod
    def _require_non_empty_string(data: dict[str, Any], field_name: str) -> str:
        if field_name not in data:
            raise PackDefinitionError(f"Missing required field: {field_name}.")
        value = data[field_name]
        if not isinstance(value, str):
            raise PackDefinitionError(f"{field_name} must be a string.")
        if not value.strip():
            raise PackDefinitionError(f"{field_name} cannot be empty.")
        return value.strip()

    def _require_relative_path(self, data: dict[str, Any], field_name: str) -> PurePath:
        value = self._require_non_empty_string(data, field_name)
        try:
            return parse_relative_path(value, field_name)
        except UnsafeValueError as error:
            raise PackDefinitionError(str(error)) from error
