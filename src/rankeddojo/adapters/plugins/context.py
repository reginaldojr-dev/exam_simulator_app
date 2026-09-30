"""Registration surface handed to a plugin's entrypoint function.

`PluginRegistrationContext` is deliberately NOT a mega plugin registry: it
owns no state of its own. Every call forwards to the one existing registry
that is already the authority for that capability (`RuntimeRegistry` for
"runtime", `EditorRegistry` for "editor"), so those registries stay
independent of each other exactly as they were before plugins existed.

A plugin only gets to use the capabilities it declared in `plugin.json`
(`manifest.capabilities`): declaring `capabilities: ["editor"]` and then
calling `register_runtime` is rejected, not silently allowed.
"""

from __future__ import annotations

from rankeddojo.adapters.editor.editor_registry import (
    DuplicateEditorError,
    EditorPreset,
    EditorRegistry,
)
from rankeddojo.application.engine.runtime_registry import RuntimeRegistry
from rankeddojo.ports.runtime_port import LanguageRuntime


class DuplicateCapabilityError(ValueError):
    """A plugin tried to register a runtime/editor id that already exists
    (built-in, or registered earlier by another plugin). Plugins never
    silently override an existing registration."""


class PluginCapabilityUnavailableError(ValueError):
    """A plugin tried to use a capability it did not declare in `plugin.json`."""


class PluginRegistrationContext:
    """Narrow, per-plugin-load view onto the app's existing registries."""

    def __init__(
        self,
        *,
        runtimes: RuntimeRegistry,
        editors: EditorRegistry,
        declared_capabilities: tuple[str, ...],
        plugin_id: str,
    ) -> None:
        self._runtimes = runtimes
        self._editors = editors
        self._declared_capabilities = frozenset(declared_capabilities)
        self._plugin_id = plugin_id

    def register_runtime(self, runtime: LanguageRuntime) -> None:
        """Register a `LanguageRuntime` into the app's `RuntimeRegistry`.

        `RuntimeRegistry.register` itself has no duplicate check (it is used
        internally to let the app reconfigure a language's runtime), so the
        duplicate check for plugin-registered runtimes lives here instead:
        a plugin can never silently replace a built-in or another plugin's
        runtime for the same language.
        """
        self._require_declared("runtime")
        if self._runtimes.has(runtime.language):
            raise DuplicateCapabilityError(
                f"Plugin '{self._plugin_id}' tried to register a runtime for language "
                f"'{runtime.language}', which is already registered (built-in or another "
                "plugin); plugins never override an existing runtime."
            )
        self._runtimes.register(runtime)

    def register_editor(self, preset: EditorPreset) -> None:
        """Register an `EditorPreset` into the app's `EditorRegistry`.

        `EditorRegistry.register` already raises `DuplicateEditorError` on a
        duplicate id; this only re-raises it as `DuplicateCapabilityError` so
        callers of `PluginRegistrationContext` see one consistent exception
        type regardless of which capability they used.
        """
        self._require_declared("editor")
        try:
            self._editors.register(preset)
        except DuplicateEditorError as error:
            raise DuplicateCapabilityError(
                f"Plugin '{self._plugin_id}' tried to register editor preset "
                f"'{preset.id}': {error}"
            ) from error

    def _require_declared(self, capability: str) -> None:
        if capability not in self._declared_capabilities:
            raise PluginCapabilityUnavailableError(
                f"Plugin '{self._plugin_id}' did not declare capability '{capability}' "
                "in plugin.json; it cannot use it."
            )
