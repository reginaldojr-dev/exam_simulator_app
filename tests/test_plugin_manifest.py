"""Fase 6: validates `load_manifest`, the whitelist parser for `plugin.json`.

This module never imports or executes a plugin's Python code -- these tests
only exercise JSON parsing and field validation.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rankeddojo.adapters.plugins.manifest import PluginManifest, PluginManifestError, load_manifest


def _write_manifest(folder: Path, data: dict) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "plugin.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


VALID_MANIFEST = {
    "schema_version": 1,
    "id": "my-plugin",
    "version": "1.0.0",
    "api_version": 1,
    "entrypoint": "plugin:register",
    "capabilities": ["runtime"],
}


class PluginManifestValidTest(unittest.TestCase):
    def test_valid_manifest_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_manifest(Path(tmp), VALID_MANIFEST)
            manifest = load_manifest(path)

        self.assertEqual(
            manifest,
            PluginManifest(
                id="my-plugin",
                version="1.0.0",
                api_version=1,
                entrypoint_module="plugin",
                entrypoint_function="register",
                capabilities=("runtime",),
            ),
        )

    def test_capabilities_are_deduplicated_preserving_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = dict(VALID_MANIFEST, capabilities=["editor", "runtime", "editor"])
            path = _write_manifest(Path(tmp), data)
            manifest = load_manifest(path)

        self.assertEqual(manifest.capabilities, ("editor", "runtime"))

    def test_multiple_known_capabilities_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = dict(VALID_MANIFEST, capabilities=["runtime", "editor"])
            path = _write_manifest(Path(tmp), data)
            manifest = load_manifest(path)

        self.assertEqual(manifest.capabilities, ("runtime", "editor"))


class PluginManifestInvalidTest(unittest.TestCase):
    def _assert_rejected(self, data: dict) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_manifest(Path(tmp), data)
            with self.assertRaises(PluginManifestError):
                load_manifest(path)

    def test_missing_manifest_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PluginManifestError):
                load_manifest(Path(tmp) / "does-not-exist.json")

    def test_not_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plugin.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(PluginManifestError):
                load_manifest(path)

    def test_non_object_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plugin.json"
            path.write_text("[1, 2, 3]", encoding="utf-8")
            with self.assertRaises(PluginManifestError):
                load_manifest(path)

    def test_unknown_top_level_field_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, marketplace_url="https://example.com"))

    def test_missing_required_field_is_rejected(self) -> None:
        data = dict(VALID_MANIFEST)
        del data["capabilities"]
        self._assert_rejected(data)

    def test_unsupported_schema_version_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, schema_version=2))

    def test_boolean_schema_version_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, schema_version=True))

    def test_unsafe_id_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, id="../escape"))

    def test_reserved_windows_name_id_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, id="CON"))

    def test_empty_version_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, version="   "))

    def test_overly_long_version_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, version="x" * 33))

    def test_non_integer_api_version_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, api_version="1"))

    def test_zero_api_version_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, api_version=0))

    def test_entrypoint_missing_colon_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, entrypoint="plugin.register"))

    def test_entrypoint_with_path_separator_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, entrypoint="sub/plugin:register"))

    def test_entrypoint_with_dotted_module_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, entrypoint="pkg.plugin:register"))

    def test_entrypoint_with_parent_traversal_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, entrypoint="../outside:register"))

    def test_empty_capabilities_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, capabilities=[]))

    def test_unknown_capability_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, capabilities=["theme"]))

    def test_non_list_capabilities_is_rejected(self) -> None:
        self._assert_rejected(dict(VALID_MANIFEST, capabilities="runtime"))


if __name__ == "__main__":
    unittest.main()
