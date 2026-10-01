"""Contract a source of learning content implements to participate in the
`ContentRegistry` (see `application/engine/content_registry.py`).

A provider only reports what it already knows about -- it does not execute
a grader, open a workspace, touch the UI, or reach the network. See
`adapters/learning/pack_content_provider.py` for the current implementation
(built-in and installed packs); a future remote provider would implement
this same, narrow contract.
"""

from __future__ import annotations

from typing import Protocol

from rankeddojo.domain.learning import LearningActivityRef


class ContentProvider(Protocol):
    def languages(self) -> tuple[str, ...]:
        """Technical language ids this provider currently has content for."""
        raise NotImplementedError

    def activities(self, language: str) -> tuple[LearningActivityRef, ...]:
        """This provider's activities for `language`, in this provider's own
        deterministic order. `position` on each ref is provisional -- the
        registry assembling multiple providers reassigns the final,
        track-wide position."""
        raise NotImplementedError

    @property
    def errors(self) -> dict[str, str]:
        """Discovery/load errors this provider recorded while producing the
        above (source -> reason), mirroring the `load_errors` pattern
        `UserThemeLoader`/`PluginLoader`/`LocalPackCatalog` already use."""
        raise NotImplementedError
