"""Plugin API version: the only version this build of RankedDojo understands.

A plugin declares the API version it was written against in its manifest
(`plugin.json`, field `api_version`). A plugin whose declared version does not
match exactly is rejected with a clear error and is never imported -- see
`loader.py`. This intentionally has no semver ranges or compatibility matrix:
v1 supports only `api_version == 1`. A future API version can widen this
check without touching the manifest/loader contract shape.
"""

from __future__ import annotations

PLUGIN_API_VERSION = 1


class PluginApiVersionError(ValueError):
    """A plugin declares an `api_version` this build does not support."""


def check_api_version_supported(declared_api_version: int) -> None:
    """Raise `PluginApiVersionError` unless `declared_api_version` is supported.

    Called only after the manifest itself has already been validated as
    well-formed (see `manifest.load_manifest`); this only judges
    compatibility, not shape.
    """
    if declared_api_version != PLUGIN_API_VERSION:
        raise PluginApiVersionError(
            f"Plugin API v{declared_api_version} is not supported by this build "
            f"(this build supports Plugin API v{PLUGIN_API_VERSION})."
        )
