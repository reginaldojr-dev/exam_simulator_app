"""Fase 9: validates `ContentRegistry`, which combines one or more
`ContentProvider`s into a single `LearningTrack` per language.

Uses small fake providers (not `PackContentProvider`) so these tests stay
about aggregation behavior only -- provider-specific behavior (reading
`LocalPackCatalog`) is covered in `test_pack_content_provider.py`.
"""

from __future__ import annotations

import unittest

from rankeddojo.application.engine.content_registry import (
    ContentRegistry,
    DuplicateContentProviderError,
)
from rankeddojo.domain.learning import LearningActivityRef


class FakeContentProvider:
    def __init__(
        self,
        by_language: dict[str, tuple[LearningActivityRef, ...]],
        errors: dict[str, str] | None = None,
        raise_for_language: str | None = None,
    ) -> None:
        self._by_language = by_language
        self._errors = errors or {}
        self._raise_for_language = raise_for_language

    def languages(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_language))

    def activities(self, language: str) -> tuple[LearningActivityRef, ...]:
        if language == self._raise_for_language:
            raise RuntimeError("boom")
        return self._by_language.get(language, ())

    @property
    def errors(self) -> dict[str, str]:
        return dict(self._errors)


def ref(*, language: str, pack_id: str, activity_id: str) -> LearningActivityRef:
    return LearningActivityRef(
        language=language,
        pack_id=pack_id,
        activity_id=activity_id,
        position=0,  # placeholder; the registry reassigns it
        title=activity_id,
    )


class ContentRegistryEmptyStateTest(unittest.TestCase):
    def test_no_providers_returns_empty_but_valid_state(self) -> None:
        registry = ContentRegistry()

        self.assertEqual(registry.languages(), ())
        track = registry.track("c")
        self.assertEqual(track.activities, ())
        self.assertEqual(registry.errors, {})

    def test_language_with_no_content_returns_empty_track(self) -> None:
        registry = ContentRegistry()
        registry.register_provider("builtin", FakeContentProvider({"c": (ref(language="c", pack_id="p", activity_id="a"),)}))

        track = registry.track("python")

        self.assertEqual(track.activities, ())


class ContentRegistryRegistrationTest(unittest.TestCase):
    def test_duplicate_provider_id_is_rejected(self) -> None:
        registry = ContentRegistry()
        registry.register_provider("builtin", FakeContentProvider({}))

        with self.assertRaises(DuplicateContentProviderError):
            registry.register_provider("builtin", FakeContentProvider({}))

    def test_duplicate_provider_id_does_not_replace_the_first(self) -> None:
        registry = ContentRegistry()
        first = FakeContentProvider({"c": (ref(language="c", pack_id="p", activity_id="a"),)})
        second = FakeContentProvider({"c": (ref(language="c", pack_id="p", activity_id="b"),)})
        registry.register_provider("builtin", first)
        with self.assertRaises(DuplicateContentProviderError):
            registry.register_provider("builtin", second)

        self.assertEqual(registry.track("c").activity_ids, ("a",))

    def test_provider_ids_preserve_registration_order(self) -> None:
        registry = ContentRegistry()
        registry.register_provider("builtin", FakeContentProvider({}))
        registry.register_provider("installed", FakeContentProvider({}))

        self.assertEqual(registry.provider_ids(), ("builtin", "installed"))


class ContentRegistryAggregationTest(unittest.TestCase):
    def test_languages_is_the_union_of_every_provider_sorted(self) -> None:
        registry = ContentRegistry()
        registry.register_provider("builtin", FakeContentProvider({"python": (), "c": ()}))
        registry.register_provider("installed", FakeContentProvider({"java": ()}))

        self.assertEqual(registry.languages(), ("c", "java", "python"))

    def test_track_combines_activities_from_every_provider_in_registration_order(self) -> None:
        registry = ContentRegistry()
        registry.register_provider("builtin", FakeContentProvider({"c": (ref(language="c", pack_id="builtin-pack", activity_id="a"),)}))
        registry.register_provider("installed", FakeContentProvider({"c": (ref(language="c", pack_id="installed-pack", activity_id="b"),)}))

        track = registry.track("c")

        self.assertEqual(track.activity_ids, ("a", "b"))
        self.assertEqual([ref.pack_id for ref in track.activities], ["builtin-pack", "installed-pack"])

    def test_positions_are_reassigned_sequentially_across_providers(self) -> None:
        registry = ContentRegistry()
        registry.register_provider("builtin", FakeContentProvider({"c": (ref(language="c", pack_id="p1", activity_id="a"),)}))
        registry.register_provider("installed", FakeContentProvider({"c": (ref(language="c", pack_id="p2", activity_id="b"),)}))

        track = registry.track("c")

        self.assertEqual([activity.position for activity in track.activities], [1, 2])

    def test_result_is_deterministic_across_repeated_calls(self) -> None:
        registry = ContentRegistry()
        registry.register_provider("builtin", FakeContentProvider({"c": (ref(language="c", pack_id="p1", activity_id="a"), ref(language="c", pack_id="p1", activity_id="b"))}))

        first = registry.track("c")
        second = registry.track("c")

        self.assertEqual(first.activity_ids, second.activity_ids)
        self.assertEqual([a.position for a in first.activities], [a.position for a in second.activities])


class ContentRegistryErrorIsolationTest(unittest.TestCase):
    def test_one_providers_failure_does_not_break_another_providers_content(self) -> None:
        registry = ContentRegistry()
        registry.register_provider("builtin", FakeContentProvider({}, raise_for_language="c"))
        registry.register_provider("installed", FakeContentProvider({"c": (ref(language="c", pack_id="p", activity_id="a"),)}))

        track = registry.track("c")  # must not raise

        self.assertEqual(track.activity_ids, ("a",))
        self.assertIn("builtin:c", registry.errors)

    def test_invalid_track_content_is_recorded_and_falls_back_to_empty_track(self) -> None:
        registry = ContentRegistry()
        cyclic = LearningActivityRef(
            language="c", pack_id="p", activity_id="a", position=0, title="A", prerequisites=("a",)
        )
        registry.register_provider("builtin", FakeContentProvider({"c": (cyclic,)}))

        track = registry.track("c")  # must not raise

        self.assertEqual(track.activities, ())
        self.assertIn("track:c", registry.errors)

    def test_provider_errors_are_namespaced_by_provider_id(self) -> None:
        registry = ContentRegistry()
        registry.register_provider("builtin", FakeContentProvider({}, errors={"some/path": "bad manifest"}))

        self.assertEqual(registry.errors, {"builtin:some/path": "bad manifest"})


if __name__ == "__main__":
    unittest.main()
