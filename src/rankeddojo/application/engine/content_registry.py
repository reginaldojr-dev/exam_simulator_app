"""Aggregates learning content from multiple `ContentProvider`s (built-in,
installed packs, and -- in the future -- a remote provider) into a single
`LearningTrack` per language.

This mirrors `RuntimeRegistry`/`EditorRegistry`: it is the one place that
combines providers, but it owns no content-parsing logic of its own --
discovery, validation, and pack/exercise rules stay entirely in the
providers and the systems they wrap (`LocalPackCatalog`, `JsonPackLoader`,
`JsonExerciseDefinitionLoader`). `ContentRegistry` only assembles the final,
deterministic position of each activity within its language's track and
checks the resulting prerequisite graph is valid (see `domain.learning`).

It never executes a grader, opens a workspace, controls UI, computes XP,
decides adaptation, reaches the network, or loads a plugin -- it only reads
values `ContentProvider`s already produced.
"""

from __future__ import annotations

from dataclasses import replace

from rankeddojo.domain.learning import LearningActivityRef, LearningContentError, LearningTrack, validate_track
from rankeddojo.ports.content_provider import ContentProvider


class DuplicateContentProviderError(ValueError):
    """Two providers were registered under the same id. The first one
    registered stays the authority; it is never silently replaced."""


class ContentRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ContentProvider] = {}
        self._order: list[str] = []
        self._provider_errors: dict[str, str] = {}
        self._track_errors: dict[str, str] = {}

    def register_provider(self, provider_id: str, provider: ContentProvider) -> None:
        if provider_id in self._providers:
            raise DuplicateContentProviderError(f"Content provider already registered: {provider_id}.")
        self._providers[provider_id] = provider
        self._order.append(provider_id)

    def provider_ids(self) -> tuple[str, ...]:
        return tuple(self._order)

    def languages(self) -> tuple[str, ...]:
        languages: set[str] = set()
        for provider_id in self._order:
            languages.update(self._providers[provider_id].languages())
        return tuple(sorted(languages))

    def track(self, language: str) -> LearningTrack:
        """A language with no registered provider, or no provider content
        for it, is not an error: it returns a valid, empty track."""
        activities: list[LearningActivityRef] = []
        for provider_id in self._order:
            provider = self._providers[provider_id]
            try:
                activities.extend(provider.activities(language))
            except Exception as error:  # noqa: BLE001 -- one provider's failure must not break the others
                self._provider_errors[f"{provider_id}:{language}"] = f"Content provider failed: {error!r}"

        positioned = tuple(
            replace(ref, position=index) for index, ref in enumerate(activities, start=1)
        )
        track = LearningTrack(language=language, activities=positioned)
        try:
            validate_track(track)
        except LearningContentError as error:
            self._track_errors[language] = str(error)
            return LearningTrack(language=language, activities=())
        self._track_errors.pop(language, None)
        return track

    def activity(self, language: str, activity_id: str) -> LearningActivityRef | None:
        return self.track(language).get(activity_id)

    @property
    def errors(self) -> dict[str, str]:
        combined: dict[str, str] = dict(self._provider_errors)
        combined.update({f"track:{language}": reason for language, reason in self._track_errors.items()})
        for provider_id in self._order:
            for source, reason in self._providers[provider_id].errors.items():
                combined[f"{provider_id}:{source}"] = reason
        return combined
