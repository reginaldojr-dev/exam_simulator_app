"""Fase 6: validates `PluginRegistrationContext`, the narrow registration
surface handed to a plugin's entrypoint function. It owns no state of its
own: every call must forward into the real `RuntimeRegistry`/`EditorRegistry`
passed in, and a plugin may only use the capabilities it declared.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from rankeddojo.adapters.editor.editor_registry import EditorPreset, EditorRegistry
from rankeddojo.adapters.plugins.context import (
    DuplicateCapabilityError,
    PluginCapabilityUnavailableError,
    PluginRegistrationContext,
)
from rankeddojo.application.engine.runtime_registry import RuntimeRegistry


@dataclass
class _FakeRuntime:
    """Minimal stand-in satisfying the `LanguageRuntime` structural fields
    `RuntimeRegistry` actually reads (`.language`)."""

    language: str
    display_name: str = "Fake"


class PluginRegistrationContextRuntimeTest(unittest.TestCase):
    def test_register_runtime_forwards_to_the_real_runtime_registry(self) -> None:
        runtimes = RuntimeRegistry()
        context = PluginRegistrationContext(
            runtimes=runtimes,
            editors=EditorRegistry(),
            declared_capabilities=("runtime",),
            plugin_id="my-plugin",
        )

        context.register_runtime(_FakeRuntime(language="rust"))

        self.assertTrue(runtimes.has("rust"))
        self.assertIs(runtimes.get("rust").__class__, _FakeRuntime)

    def test_register_runtime_never_overrides_an_existing_language(self) -> None:
        runtimes = RuntimeRegistry([_FakeRuntime(language="python")])
        context = PluginRegistrationContext(
            runtimes=runtimes,
            editors=EditorRegistry(),
            declared_capabilities=("runtime",),
            plugin_id="my-plugin",
        )
        original = runtimes.get("python")

        with self.assertRaises(DuplicateCapabilityError):
            context.register_runtime(_FakeRuntime(language="python"))

        self.assertIs(runtimes.get("python"), original)

    def test_register_runtime_requires_the_declared_capability(self) -> None:
        context = PluginRegistrationContext(
            runtimes=RuntimeRegistry(),
            editors=EditorRegistry(),
            declared_capabilities=("editor",),
            plugin_id="my-plugin",
        )

        with self.assertRaises(PluginCapabilityUnavailableError):
            context.register_runtime(_FakeRuntime(language="rust"))


class PluginRegistrationContextEditorTest(unittest.TestCase):
    def test_register_editor_forwards_to_the_real_editor_registry(self) -> None:
        editors = EditorRegistry()
        context = PluginRegistrationContext(
            runtimes=RuntimeRegistry(),
            editors=editors,
            declared_capabilities=("editor",),
            plugin_id="my-plugin",
        )

        context.register_editor(EditorPreset(id="My Editor", candidates=("my-editor",)))

        self.assertTrue(editors.has("My Editor"))

    def test_register_editor_never_overrides_an_existing_id(self) -> None:
        editors = EditorRegistry([EditorPreset(id="VS Code", candidates=("code",))])
        context = PluginRegistrationContext(
            runtimes=RuntimeRegistry(),
            editors=editors,
            declared_capabilities=("editor",),
            plugin_id="my-plugin",
        )
        original = editors.get("VS Code")

        with self.assertRaises(DuplicateCapabilityError):
            context.register_editor(EditorPreset(id="VS Code", candidates=("fake",)))

        self.assertIs(editors.get("VS Code"), original)

    def test_register_editor_requires_the_declared_capability(self) -> None:
        context = PluginRegistrationContext(
            runtimes=RuntimeRegistry(),
            editors=EditorRegistry(),
            declared_capabilities=("runtime",),
            plugin_id="my-plugin",
        )

        with self.assertRaises(PluginCapabilityUnavailableError):
            context.register_editor(EditorPreset(id="My Editor", candidates=("my-editor",)))


if __name__ == "__main__":
    unittest.main()
