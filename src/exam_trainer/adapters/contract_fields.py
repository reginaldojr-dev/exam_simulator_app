"""Campos comuns do contrato de pack (pack.json e exercise.json). Ver resources/pack-contract.md."""

from __future__ import annotations

from typing import Any

from exam_trainer.domain.pack_definition import SUPPORTED_SCHEMA_VERSIONS

MAX_TOPICS = 20
MAX_TOPIC_LENGTH = 40


def read_schema_version(data: dict[str, Any], error_type: type[ValueError]) -> int:
    """`schema_version` ausente = 1 (contrato v1). Qualquer outro valor fora do suportado é erro."""
    version = data.get("schema_version", 1)
    if not isinstance(version, int) or isinstance(version, bool) or version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(str(value) for value in SUPPORTED_SCHEMA_VERSIONS)
        raise error_type(f"Unsupported schema_version: {version!r} (supported: {supported}).")
    return version


def read_topics(raw: Any, error_type: type[ValueError], field_name: str = "topics") -> tuple[str, ...]:
    if not isinstance(raw, list) or len(raw) > MAX_TOPICS:
        raise error_type(f"{field_name} must be a list with at most {MAX_TOPICS} strings.")
    topics: list[str] = []
    for value in raw:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > MAX_TOPIC_LENGTH:
            raise error_type(f"{field_name} entries must be non-empty strings up to {MAX_TOPIC_LENGTH} chars.")
        topics.append(value.strip())
    return tuple(topics)
