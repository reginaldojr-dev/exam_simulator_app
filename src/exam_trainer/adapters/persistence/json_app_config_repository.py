from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


class JsonAppConfigRepository:
    def __init__(self, config_file_path: Path) -> None:
        self._config_file_path = config_file_path

    def load_workspace_path(self) -> Path | None:
        data = self._load_data()

        workspace_path = self._read_string(data, "workspace_path")
        if workspace_path is None:
            return None

        return Path(workspace_path).expanduser()

    def save_workspace_path(self, workspace_path: Path) -> None:
        data = self._load_data()
        data["workspace_path"] = str(workspace_path)
        self._save_data(data)

    def load_editor_command(self) -> str:
        data = self._load_data()
        return self._normalize_local_path(self._read_string(data, "editor_command")) or "code"

    def save_editor_command(self, editor_command: str) -> None:
        data = self._load_data()
        data["editor_command"] = self._normalize_local_path(editor_command) or "code"
        self._save_data(data)

    def load_compiler_path(self) -> str | None:
        data = self._load_data()
        return self._normalize_local_path(self._read_string(data, "compiler_path"))

    def save_compiler_path(self, compiler_path: str | None) -> None:
        data = self._load_data()
        normalized = self._normalize_local_path(compiler_path)
        if normalized is None:
            data.pop("compiler_path", None)
        else:
            data["compiler_path"] = normalized
        self._save_data(data)

    def load_theme(self) -> str | None:
        return self._read_string(self._load_data(), "theme")

    def save_theme(self, theme_key: str) -> None:
        data = self._load_data()
        data["theme"] = theme_key
        self._save_data(data)

    def _load_data(self) -> dict[str, Any]:
        if not self._config_file_path.exists():
            return {}

        try:
            data = json.loads(self._config_file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        if not isinstance(data, dict):
            return {}

        return data

    def _save_data(self, data: dict[str, Any]) -> None:
        self._config_file_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_file_path.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _read_string(data: Any, key: str) -> str | None:
        if not isinstance(data, dict):
            return None

        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value

        return None

    @staticmethod
    def _normalize_local_path(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        parsed = urlparse(stripped)
        if parsed.scheme == "file":
            path = unquote(parsed.path)
            if parsed.netloc:
                path = f"//{parsed.netloc}{path}"
            if len(path) >= 3 and path[0] == "/" and path[2] == ":":
                path = path[1:]
            return str(Path(path))
        return stripped
