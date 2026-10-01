"""Adapts the existing pack system (`LocalPackCatalog`) into a
`ContentProvider` for the learning track model. It does not reimplement
pack discovery, parsing, or validation -- it only reads the
`PackDefinition`/`ExerciseRef` values `LocalPackCatalog` already produces
and re-shapes the ones that opted in into `LearningActivityRef`.

The same class backs both the built-in and installed-pack providers: which
one it is depends only on which directory the `LocalPackCatalog` it wraps
was built against (see `infrastructure/app_factory.py`). Nothing here
distinguishes "built-in" from "installed" beyond that.
"""

from __future__ import annotations

from rankeddojo.adapters.pack.local_pack_catalog import LocalPackCatalog
from rankeddojo.domain.learning import LearningActivityRef
from rankeddojo.domain.pack_definition import PackDefinition


class PackContentProvider:
    """`ContentProvider` backed by a `LocalPackCatalog`.

    Only packs that declare `"learning_track": true` in `pack.json`
    (schema_version 2+) participate here. A pack without that field
    continues to exist for training/exam exactly as before -- it is simply
    invisible to this provider, never rejected or altered.
    """

    def __init__(self, catalog: LocalPackCatalog) -> None:
        self._catalog = catalog

    @property
    def errors(self) -> dict[str, str]:
        """Delegates to the underlying catalog's own load errors -- this
        provider never swallows or reinterprets them."""
        return self._catalog.load_errors

    def languages(self) -> tuple[str, ...]:
        languages = {pack.language for pack in self._catalog.list_packs() if pack.learning_track}
        return tuple(sorted(languages))

    def activities(self, language: str) -> tuple[LearningActivityRef, ...]:
        refs: list[LearningActivityRef] = []
        for pack in self._catalog.list_packs():
            if not pack.learning_track or pack.language != language:
                continue
            refs.extend(self._activities_for_pack(pack))
        return tuple(refs)

    def _activities_for_pack(self, pack: PackDefinition) -> list[LearningActivityRef]:
        refs: list[LearningActivityRef] = []
        for index, exercise_ref in enumerate(self._catalog.list_exercises(pack.id)):
            definition = exercise_ref.definition
            refs.append(
                LearningActivityRef(
                    language=pack.language,
                    pack_id=pack.id,
                    activity_id=definition.id,
                    # Provisional: this pack's own order. ContentRegistry
                    # reassigns the final, track-wide position once every
                    # provider's activities for the language are combined.
                    position=index,
                    title=definition.name,
                    topics=definition.topics,
                    difficulty=definition.difficulty,
                    prerequisites=definition.prerequisites,
                )
            )
        return refs
