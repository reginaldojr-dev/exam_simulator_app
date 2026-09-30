# Plugin API v1

This document describes RankedDojo's local plugin system: what a plugin is,
how it differs from a pack or a theme, the manifest format, and how loading
works. It does not describe a marketplace, a sandbox, or any isolation
guarantee -- none of those exist in this version.

## Packs, themes, and plugins

RankedDojo has three kinds of user-added content, and they are not the same
thing:

- A **pack** (`pack.json` plus exercise content) is declarative study
  content. It is never executable.
- A **theme** (`theme.json`) is a declarative set of visual tokens,
  whitelist-validated. It is never executable.
- A **plugin** (`plugin.json` plus a Python entrypoint) is the only kind of
  user-added content that is executable. It is trusted, opt-in code.

Nothing in the pack or theme loading code imports or knows about plugins,
and nothing in the plugin code imports or knows about pack/theme loading.

## Trusted code, no sandbox

**A plugin is trusted code. It runs with the same permissions as the rest of
the app and as the user who runs it.** RankedDojo does not sandbox, isolate,
or restrict what a plugin's Python code can do once it is imported. Only
install and enable plugins you trust, the same way you would trust any other
Python code you choose to run.

## Folder structure

Each plugin is one subfolder of the plugins directory:

```text
%APPDATA%\rankeddojo\plugins\<plugin-id>\
    plugin.json
    <entrypoint-module>.py
```

(On Linux/macOS the plugins directory is under the platform's usual config
location for `rankeddojo`, not `%APPDATA%`.) A folder with no `plugin.json`
inside it is not a plugin folder and is silently skipped -- a folder's mere
existence never causes anything to run.

## The manifest (`plugin.json`)

All fields are required in v1; unknown fields are rejected outright.

```json
{
  "schema_version": 1,
  "id": "my-plugin",
  "version": "1.0.0",
  "api_version": 1,
  "entrypoint": "plugin:register",
  "capabilities": ["runtime"]
}
```

- `schema_version` -- manifest shape version. Only `1` is supported.
- `id` -- a safe identifier (`[A-Za-z0-9][A-Za-z0-9_-]{0,63}`, no reserved
  Windows names). This is the id used in `enabled_plugins` to opt the plugin
  in.
- `version` -- a free-form, non-empty string describing the plugin's own
  version (not the API version). Not interpreted as semver.
- `api_version` -- the Plugin API version this plugin was written against.
  Must equal this build's supported version exactly (see below); there are
  no ranges.
- `entrypoint` -- `"module:function"`, both plain Python identifiers. Names a
  single `.py` file directly inside the plugin's own folder (no dots, no
  path separators, no sub-packages) and the function inside it that receives
  the registration context.
- `capabilities` -- a non-empty list drawn from the capabilities this build
  actually supports (see below). A plugin can only use the capabilities it
  declares here.

## API version

This build understands exactly one Plugin API version. A plugin whose
`api_version` does not match is rejected before its code is ever imported --
this check happens using only the manifest, never by importing the plugin.

## Opt-in

Plugins are **disabled by default**. A plugin's folder being present and its
manifest being valid is not enough for it to run: its `id` must also appear
in the app's `enabled_plugins` configuration. Enabling a plugin is a manual,
explicit action; there is no UI for it yet in this version.

## Lifecycle

For each folder under the plugins directory, in sorted (deterministic)
order:

1. **Discover**: is there a `plugin.json` in this folder? If not, skip.
2. **Validate manifest**: parse and validate `plugin.json` against the
   whitelist above. If invalid, skip and record why.
3. **Check API compatibility**: does `api_version` match this build? If not,
   skip and record why. Still no Python file has been read.
4. **Check enabled**: is this plugin's `id` in `enabled_plugins`? If not,
   stop here -- the plugin was discovered and validated but never imported.
5. **Import**: only now is the entrypoint `.py` file imported, with its path
   re-checked to stay inside the plugin's own folder.
6. **Register**: the entrypoint function is called with a
   `PluginRegistrationContext` scoped to the capabilities this plugin
   declared.

A failure at any step is recorded for that plugin only; it never stops
another plugin from loading and never crashes the app.

## Supported capabilities (this version)

Only capabilities with a real, existing, mutable registry in RankedDojo are
supported:

- `runtime` -- register a `LanguageRuntime` into the app's runtime registry
  (the same registry built-in C/C++/Python/Java runtimes use).
- `editor` -- register an `EditorPreset` into the app's editor registry (the
  same registry the built-in VS Code/Zed/Cursor presets use).

There is no single "plugin registry": each capability is registered directly
into the one existing registry that is already the authority for it. A
plugin never overrides a built-in or another plugin's registration for the
same id -- attempting to do so is rejected.

## Minimal example

```python
# plugin.json
# {
#   "schema_version": 1,
#   "id": "example-editor",
#   "version": "0.1.0",
#   "api_version": 1,
#   "entrypoint": "plugin:register",
#   "capabilities": ["editor"]
# }

# plugin.py
from rankeddojo.adapters.editor.editor_registry import EditorPreset


def register(context):
    context.register_editor(
        EditorPreset(id="My Editor", candidates=("my-editor",))
    )
```

## Out of scope (this version)

No marketplace or remote/auto-update download. No digital signing. No
sandbox or per-capability permission system. No settings UI to manage
plugins. No plugin capability for themes, packs, learning/leveling, content
registries, or remote data providers. No `ExtensionManager`-style umbrella
component.
