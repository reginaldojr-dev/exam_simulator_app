"""Fase 6: validates `PluginLoader`, which discovers local plugins, validates
their manifest, checks API-version compatibility and opt-in, and -- only for
plugins that pass every one of those checks -- imports their entrypoint file
and calls its registration function through a `PluginRegistrationContext`.

These tests write real `.py` entrypoint files to a temp directory and rely on
`PluginLoader` to import them; they never import anything from the plugin
package tree of this repository itself, so running this file never executes
any content shipped with the app.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rankeddojo.adapters.editor.editor_registry import EditorPreset, EditorRegistry
from rankeddojo.adapters.plugins.loader import PluginLoader
from rankeddojo.application.engine.runtime_registry import RuntimeRegistry


def _write_plugin(folder: Path, manifest: dict, entrypoint_source: str, module_name: str = "plugin") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (folder / f"{module_name}.py").write_text(entrypoint_source, encoding="utf-8")


def _manifest(**overrides) -> dict:
    data = {
        "schema_version": 1,
        "id": "sample-plugin",
        "version": "1.0.0",
        "api_version": 1,
        "entrypoint": "plugin:register",
        "capabilities": ["editor"],
    }
    data.update(overrides)
    return data


EDITOR_REGISTER_SOURCE = """
from rankeddojo.adapters.editor.editor_registry import EditorPreset


def register(context):
    context.register_editor(EditorPreset(id="Sample Editor", candidates=("sample-editor",)))
"""


class PluginLoaderDiscoveryTest(unittest.TestCase):
    def test_folder_without_plugin_json_is_silently_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            not_a_plugin = plugins_dir / "not-a-plugin"
            not_a_plugin.mkdir(parents=True)
            (not_a_plugin / "readme.txt").write_text("hi", encoding="utf-8")

            loader = PluginLoader()
            loader.load_into(
                plugins_dir=plugins_dir,
                enabled_plugin_ids=(),
                runtimes=RuntimeRegistry(),
                editors=EditorRegistry(),
            )

        self.assertEqual(loader.load_errors, {})

    def test_missing_plugins_dir_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loader = PluginLoader()
            loader.load_into(
                plugins_dir=Path(tmp) / "does-not-exist",
                enabled_plugin_ids=(),
                runtimes=RuntimeRegistry(),
                editors=EditorRegistry(),
            )

        self.assertEqual(loader.load_errors, {})

    def test_zero_plugins_leaves_registries_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtimes = RuntimeRegistry()
            editors = EditorRegistry()
            PluginLoader().load_into(
                plugins_dir=Path(tmp) / "plugins",
                enabled_plugin_ids=(),
                runtimes=runtimes,
                editors=editors,
            )

        self.assertEqual(runtimes.languages(), ())
        self.assertEqual(editors.ids(), ())


class PluginLoaderApiVersionTest(unittest.TestCase):
    def test_incompatible_api_version_is_skipped_and_never_imported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            _write_plugin(
                plugins_dir / "sample-plugin",
                _manifest(api_version=2),
                EDITOR_REGISTER_SOURCE,
            )
            editors = EditorRegistry()
            loader = PluginLoader()

            loader.load_into(
                plugins_dir=plugins_dir,
                enabled_plugin_ids=("sample-plugin",),
                runtimes=RuntimeRegistry(),
                editors=editors,
            )

        self.assertFalse(editors.has("Sample Editor"))
        self.assertIn(str(plugins_dir / "sample-plugin"), loader.load_errors)

    def test_invalid_manifest_is_skipped_without_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            folder = plugins_dir / "broken-plugin"
            folder.mkdir(parents=True)
            (folder / "plugin.json").write_text("{not json", encoding="utf-8")

            loader = PluginLoader()
            loader.load_into(  # must not raise
                plugins_dir=plugins_dir,
                enabled_plugin_ids=("broken-plugin",),
                runtimes=RuntimeRegistry(),
                editors=EditorRegistry(),
            )

        self.assertIn(str(folder), loader.load_errors)


class PluginLoaderOptInTest(unittest.TestCase):
    def test_disabled_plugin_is_discovered_but_never_imported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            _write_plugin(plugins_dir / "sample-plugin", _manifest(), EDITOR_REGISTER_SOURCE)
            editors = EditorRegistry()
            loader = PluginLoader()

            loader.load_into(
                plugins_dir=plugins_dir,
                enabled_plugin_ids=(),  # not enabled
                runtimes=RuntimeRegistry(),
                editors=editors,
            )

        # Not imported/registered, and not reported as an error either --
        # being disabled is a normal, expected state, not a failure.
        self.assertFalse(editors.has("Sample Editor"))
        self.assertEqual(loader.load_errors, {})

    def test_enabled_plugin_is_imported_and_registered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            _write_plugin(plugins_dir / "sample-plugin", _manifest(), EDITOR_REGISTER_SOURCE)
            editors = EditorRegistry()
            loader = PluginLoader()

            loader.load_into(
                plugins_dir=plugins_dir,
                enabled_plugin_ids=("sample-plugin",),
                runtimes=RuntimeRegistry(),
                editors=editors,
            )

        self.assertTrue(editors.has("Sample Editor"))
        self.assertEqual(loader.load_errors, {})

    def test_unrelated_enabled_id_does_not_enable_a_different_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            _write_plugin(plugins_dir / "sample-plugin", _manifest(), EDITOR_REGISTER_SOURCE)
            editors = EditorRegistry()

            PluginLoader().load_into(
                plugins_dir=plugins_dir,
                enabled_plugin_ids=("some-other-plugin",),
                runtimes=RuntimeRegistry(),
                editors=editors,
            )

        self.assertFalse(editors.has("Sample Editor"))


class PluginLoaderIsolationTest(unittest.TestCase):
    def test_import_failure_is_isolated_and_does_not_stop_other_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            _write_plugin(
                plugins_dir / "broken-plugin",
                _manifest(id="broken-plugin"),
                "raise RuntimeError('boom at import time')\n",
            )
            _write_plugin(
                plugins_dir / "healthy-plugin",
                _manifest(id="healthy-plugin"),
                EDITOR_REGISTER_SOURCE,
            )
            editors = EditorRegistry()
            loader = PluginLoader()

            loader.load_into(  # must not raise
                plugins_dir=plugins_dir,
                enabled_plugin_ids=("broken-plugin", "healthy-plugin"),
                runtimes=RuntimeRegistry(),
                editors=editors,
            )

        self.assertTrue(editors.has("Sample Editor"))
        self.assertIn(str(plugins_dir / "broken-plugin"), loader.load_errors)

    def test_registration_failure_is_isolated_and_does_not_stop_other_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            _write_plugin(
                plugins_dir / "broken-plugin",
                _manifest(id="broken-plugin"),
                "def register(context):\n    raise RuntimeError('boom during registration')\n",
            )
            _write_plugin(
                plugins_dir / "healthy-plugin",
                _manifest(id="healthy-plugin"),
                EDITOR_REGISTER_SOURCE,
            )
            editors = EditorRegistry()
            loader = PluginLoader()

            loader.load_into(  # must not raise
                plugins_dir=plugins_dir,
                enabled_plugin_ids=("broken-plugin", "healthy-plugin"),
                runtimes=RuntimeRegistry(),
                editors=editors,
            )

        self.assertTrue(editors.has("Sample Editor"))
        self.assertIn(str(plugins_dir / "broken-plugin"), loader.load_errors)

    def test_missing_entrypoint_function_is_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            _write_plugin(plugins_dir / "sample-plugin", _manifest(), "# no register() defined here\n")
            loader = PluginLoader()

            loader.load_into(  # must not raise
                plugins_dir=plugins_dir,
                enabled_plugin_ids=("sample-plugin",),
                runtimes=RuntimeRegistry(),
                editors=EditorRegistry(),
            )

        self.assertIn(str(plugins_dir / "sample-plugin"), loader.load_errors)

    def test_missing_entrypoint_file_is_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            folder = plugins_dir / "sample-plugin"
            folder.mkdir(parents=True)
            (folder / "plugin.json").write_text(json.dumps(_manifest()), encoding="utf-8")
            # No plugin.py written at all.
            loader = PluginLoader()

            loader.load_into(  # must not raise
                plugins_dir=plugins_dir,
                enabled_plugin_ids=("sample-plugin",),
                runtimes=RuntimeRegistry(),
                editors=EditorRegistry(),
            )

        self.assertIn(str(folder), loader.load_errors)


class PluginLoaderDuplicateTest(unittest.TestCase):
    def test_duplicate_plugin_id_second_folder_is_skipped_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            _write_plugin(plugins_dir / "aaa-first", _manifest(), EDITOR_REGISTER_SOURCE)
            _write_plugin(
                plugins_dir / "zzz-second",
                _manifest(),
                'from rankeddojo.adapters.editor.editor_registry import EditorPreset\n\n\n'
                'def register(context):\n'
                '    context.register_editor(EditorPreset(id="Should Not Register", candidates=()))\n',
            )
            editors = EditorRegistry()
            loader = PluginLoader()

            loader.load_into(
                plugins_dir=plugins_dir,
                enabled_plugin_ids=("sample-plugin",),
                runtimes=RuntimeRegistry(),
                editors=editors,
            )

        self.assertTrue(editors.has("Sample Editor"))
        self.assertFalse(editors.has("Should Not Register"))
        self.assertIn(str(plugins_dir / "zzz-second"), loader.load_errors)

    def test_runtime_registered_by_a_plugin_never_overrides_a_builtin(self) -> None:
        from dataclasses import dataclass

        @dataclass
        class _FakeRuntime:
            language: str
            display_name: str = "Fake"

        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            _write_plugin(
                plugins_dir / "sample-plugin",
                _manifest(capabilities=["runtime"]),
                (
                    "class _PluginRuntime:\n"
                    "    language = 'python'\n"
                    "    display_name = 'Plugin Python'\n"
                    "\n\n"
                    "def register(context):\n"
                    "    context.register_runtime(_PluginRuntime())\n"
                ),
            )
            runtimes = RuntimeRegistry([_FakeRuntime(language="python", display_name="Built-in Python")])
            loader = PluginLoader()

            loader.load_into(
                plugins_dir=plugins_dir,
                enabled_plugin_ids=("sample-plugin",),
                runtimes=runtimes,
                editors=EditorRegistry(),
            )

        self.assertEqual(runtimes.get("python").display_name, "Built-in Python")
        self.assertIn(str(plugins_dir / "sample-plugin"), loader.load_errors)


class PluginLoaderDeterminismTest(unittest.TestCase):
    def test_discovery_order_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins_dir = Path(tmp) / "plugins"
            for name in ("bravo-plugin", "alpha-plugin", "charlie-plugin"):
                _write_plugin(
                    plugins_dir / name,
                    _manifest(id=name),
                    (
                        "from rankeddojo.adapters.editor.editor_registry import EditorPreset\n\n\n"
                        "def register(context):\n"
                        f"    context.register_editor(EditorPreset(id='{name}', candidates=()))\n"
                    ),
                )
            enabled = ("alpha-plugin", "bravo-plugin", "charlie-plugin")

            first = EditorRegistry()
            PluginLoader().load_into(
                plugins_dir=plugins_dir, enabled_plugin_ids=enabled, runtimes=RuntimeRegistry(), editors=first
            )
            second = EditorRegistry()
            PluginLoader().load_into(
                plugins_dir=plugins_dir, enabled_plugin_ids=enabled, runtimes=RuntimeRegistry(), editors=second
            )

        self.assertEqual(first.ids(), second.ids())
        self.assertEqual(set(first.ids()), {"alpha-plugin", "bravo-plugin", "charlie-plugin"})


class PluginLoaderPathSafetyTest(unittest.TestCase):
    def test_entrypoint_outside_the_plugin_folder_via_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside.py"
            outside.write_text(EDITOR_REGISTER_SOURCE, encoding="utf-8")

            plugins_dir = Path(tmp) / "plugins"
            folder = plugins_dir / "sample-plugin"
            folder.mkdir(parents=True)
            (folder / "plugin.json").write_text(json.dumps(_manifest()), encoding="utf-8")
            link = folder / "plugin.py"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlinks are not supported in this environment")

            editors = EditorRegistry()
            loader = PluginLoader()
            loader.load_into(  # must not raise, and must not import the linked-to file
                plugins_dir=plugins_dir,
                enabled_plugin_ids=("sample-plugin",),
                runtimes=RuntimeRegistry(),
                editors=editors,
            )

        self.assertFalse(editors.has("Sample Editor"))
        self.assertIn(str(folder), loader.load_errors)


if __name__ == "__main__":
    unittest.main()
