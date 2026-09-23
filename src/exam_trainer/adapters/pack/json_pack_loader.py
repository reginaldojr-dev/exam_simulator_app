from __future__ import annotations

import json
from pathlib import Path, PurePath
from typing import Any

from exam_trainer.domain.identifiers import UnsafeValueError, parse_relative_path, validate_identifier
from exam_trainer.domain.pack_definition import PackDefinition, PackLevelDefinition

MAX_EXAM_DURATION_MINUTES = 24 * 60


class PackDefinitionError(ValueError):
    pass


class JsonPackLoader:
    def load(self, pack_json_path: Path | str) -> PackDefinition:
        path = Path(pack_json_path)
        try:
            raw_data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise PackDefinitionError(f"Invalid JSON in pack definition: {error.msg}.") from error
        except OSError as error:
            raise PackDefinitionError(f"Could not read pack definition: {error}.") from error

        data = self._require_object(raw_data, "pack definition")
        pack_id = self._require_identifier(data, "id")
        name = self._require_non_empty_string(data, "name")
        version = self._require_non_empty_string(data, "version")
        levels = self._read_levels(data)
        return PackDefinition(id=pack_id, name=name, version=version, levels=levels)

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
