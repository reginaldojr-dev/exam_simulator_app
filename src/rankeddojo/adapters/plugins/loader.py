"""Discovers local plugins under the user's plugins folder and, for those
explicitly enabled and API-compatible, imports and registers them. See
`resources/plugin-api-v1.md` for the full contract.

Discovery never executes code: every plugin folder is only ever read as far
as `load_manifest()` (plain JSON) and the API-version/enabled checks *before*
its entrypoint file is ever imported as Python. A folder that merely exists,
is not enabled, has an invalid manifest, or declares an unsupported
`api_version` is skipped without its `.py` file ever being touched.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from rankeddojo.adapters.editor.editor_registry import EditorRegistry
from rankeddojo.adapters.pack.pack_security import PackSecurityError, ensure_inside
from rankeddojo.adapters.plugins.api import PluginApiVersionError, check_api_version_supported
from rankeddojo.adapters.plugins.context import PluginRegistrationContext
from rankeddojo.adapters.plugins.manifest import (
    PLUGIN_MANIFEST_FILENAME,
    PluginManifest,
    PluginManifestError,
    load_manifest,
)
from rankeddojo.application.engine.runtime_registry import RuntimeRegistry


class PluginLoader:
    """Loads enabled, API-compatible plugins from a plugins folder into the
    app's existing registries.

    - Deterministic: plugin folders are visited in sorted order.
    - Disabled by default: a plugin's Python code is only ever imported if
      its manifest `id` is present in `enabled_plugin_ids`. A disabled
      plugin's `plugin.json` may still be read (metadata only), but its
      entrypoint module is never imported.
    - A failure anywhere for one plugin (missing/invalid manifest,
      incompatible `api_version`, duplicate id, import error, registration
      error) is recorded in `load_errors` and never stops another plugin
      from loading, and never crashes the app (no bare `except: pass`: every
      failure is recorded with a reason).
    """

    def __init__(self) -> None:
        self._load_errors: dict[str, str] = {}

    @property
    def load_errors(self) -> dict[str, str]:
        """Plugin folders that failed to load (folder path -> reason), from
        the most recent `load_into` call."""
        return dict(self._load_errors)

    def load_into(
        self,
        *,
        plugins_dir: Path,
        enabled_plugin_ids: tuple[str, ...],
        runtimes: RuntimeRegistry,
        editors: EditorRegistry,
    ) -> None:
        self._load_errors = {}
        enabled = frozenset(enabled_plugin_ids)
        seen_ids: dict[str, Path] = {}
        for root in self._plugin_roots(plugins_dir):
            self._load_one(root, enabled=enabled, seen_ids=seen_ids, runtimes=runtimes, editors=editors)

    def _load_one(
        self,
        root: Path,
        *,
        enabled: frozenset[str],
        seen_ids: dict[str, Path],
        runtimes: RuntimeRegistry,
        editors: EditorRegistry,
    ) -> None:
        manifest_path = root / PLUGIN_MANIFEST_FILENAME
        if not manifest_path.is_file():
            # Not a plugin folder (no plugin.json inside): silently skipped,
            # the same way UserThemeLoader/LocalPackCatalog skip a folder
            # with no definition file. A folder's mere existence never runs
            # anything.
            return

        try:
            manifest = load_manifest(manifest_path)
        except PluginManifestError as error:
            self._load_errors[str(root)] = f"Invalid plugin.json: {error}"
            return

        if manifest.id in seen_ids:
            self._load_errors[str(root)] = (
                f"Plugin id '{manifest.id}' was already loaded from '{seen_ids[manifest.id]}'; "
                "a later folder with the same id is skipped, never silently overriding it."
            )
            return
        seen_ids[manifest.id] = root

        try:
            check_api_version_supported(manifest.api_version)
        except PluginApiVersionError as error:
            self._load_errors[str(root)] = str(error)
            return

        if manifest.id not in enabled:
            # Discovered and validated, but not opted in: never imported.
            return

        self._import_and_register(root, manifest, runtimes=runtimes, editors=editors)

    def _import_and_register(
        self,
        root: Path,
        manifest: PluginManifest,
        *,
        runtimes: RuntimeRegistry,
        editors: EditorRegistry,
    ) -> None:
        try:
            entrypoint_path = ensure_inside(root, root / f"{manifest.entrypoint_module}.py")
        except PackSecurityError as error:
            self._load_errors[str(root)] = f"Unsafe entrypoint path: {error}"
            return
        if not entrypoint_path.is_file():
            self._load_errors[str(root)] = (
                f"Entrypoint module '{manifest.entrypoint_module}.py' not found in plugin folder."
            )
            return

        try:
            module = self._import_module(manifest.id, entrypoint_path)
        except Exception as error:  # noqa: BLE001 -- a broken plugin must never crash startup
            self._load_errors[str(root)] = f"Failed to import plugin: {error!r}"
            return

        register_function = getattr(module, manifest.entrypoint_function, None)
        if not callable(register_function):
            self._load_errors[str(root)] = (
                f"Entrypoint function '{manifest.entrypoint_function}' not found or not "
                f"callable in '{manifest.entrypoint_module}.py'."
            )
            return

        context = PluginRegistrationContext(
            runtimes=runtimes,
            editors=editors,
            declared_capabilities=manifest.capabilities,
            plugin_id=manifest.id,
        )
        try:
            register_function(context)
        except Exception as error:  # noqa: BLE001 -- isolate one plugin's failure from the rest
            self._load_errors[str(root)] = f"Plugin registration failed: {error!r}"
            return

    @staticmethod
    def _import_module(plugin_id: str, entrypoint_path: Path) -> ModuleType:
        module_name = f"rankeddojo_plugin_{plugin_id}"
        spec = importlib.util.spec_from_file_location(module_name, entrypoint_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create an import spec for {entrypoint_path}.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _plugin_roots(plugins_dir: Path) -> list[Path]:
        if not plugins_dir.is_dir():
            return []
        return [
            child
            for child in sorted(plugins_dir.iterdir())
            if child.is_dir() and not child.is_symlink()
        ]
