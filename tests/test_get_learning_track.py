"""Fase 9: validates the `GetLearningTrack`/`GetNextLearningActivity`
application use cases -- composing `ContentRegistry` with progress already
recorded in `TrainerProgressRepository`. No Qt, no filesystem.
"""

from __future__ import annotations

import unittest

from rankeddojo.application.engine.content_registry import ContentRegistry
from rankeddojo.application.use_cases.get_learning_track import GetLearningTrack
from rankeddojo.application.use_cases.get_next_learning_activity import GetNextLearningActivity
from rankeddojo.domain.learning import LearningActivityRef
from rankeddojo.domain.progress import ProgressEntry


def ref(*, pack_id: str, activity_id: str, position: int, prerequisites: tuple[str, ...] = ()) -> LearningActivityRef:
    return LearningActivityRef(
        language="c",
        pack_id=pack_id,
        activity_id=activity_id,
        position=position,
        title=activity_id,
        prerequisites=prerequisites,
    )


def completed_entry(exercise_id: str, pack_id: str) -> ProgressEntry:
    return ProgressEntry(
        exercise_id=exercise_id,
        status="completed",
        attempts_count=1,
        last_attempt_at="2026-01-01T00:00:00",
        best_passed=True,
        best_score=1.0,
        last_mode="training",
        pack_id=pack_id,
    )


def attempted_entry(exercise_id: str, pack_id: str) -> ProgressEntry:
    return ProgressEntry(
        exercise_id=exercise_id,
        status="attempted",
        attempts_count=1,
        last_attempt_at="2026-01-01T00:00:00",
        best_passed=False,
        best_score=0.0,
        last_mode="training",
        pack_id=pack_id,
    )


class FakeContentProvider:
    def __init__(self, activities: tuple[LearningActivityRef, ...]) -> None:
        self._activities = activities

    def languages(self) -> tuple[str, ...]:
        return ("c",) if self._activities else ()

    def activities(self, language: str) -> tuple[LearningActivityRef, ...]:
        return self._activities if language == "c" else ()

    @property
    def errors(self) -> dict[str, str]:
        return {}


class FakeProgressRepository:
    """Only implements what `GetLearningTrack` actually calls."""

    def __init__(self, entries: dict[tuple[str, str], ProgressEntry]) -> None:
        self._entries = entries

    def progress_by_key(self) -> dict[tuple[str, str], ProgressEntry]:
        return dict(self._entries)


def make_registry(activities: tuple[LearningActivityRef, ...]) -> ContentRegistry:
    registry = ContentRegistry()
    registry.register_provider("builtin", FakeContentProvider(activities))
    return registry


class GetLearningTrackTest(unittest.TestCase):
    def test_nothing_completed_yields_first_activity_as_next_and_level_one(self) -> None:
        registry = make_registry((ref(pack_id="p", activity_id="a", position=1), ref(pack_id="p", activity_id="b", position=2)))
        use_case = GetLearningTrack(registry, FakeProgressRepository({}))

        view = use_case.execute("c")

        self.assertEqual(view.completed_activity_ids, frozenset())
        self.assertEqual(view.current_level, 1)
        self.assertEqual(view.next_activity.activity_id, "a")

    def test_completed_progress_entry_is_derived_into_completed_ids(self) -> None:
        registry = make_registry((ref(pack_id="p", activity_id="a", position=1), ref(pack_id="p", activity_id="b", position=2)))
        progress = FakeProgressRepository({("p", "a"): completed_entry("a", "p")})
        use_case = GetLearningTrack(registry, progress)

        view = use_case.execute("c")

        self.assertEqual(view.completed_activity_ids, frozenset({"a"}))
        self.assertEqual(view.current_level, 2)
        self.assertEqual(view.next_activity.activity_id, "b")

    def test_attempted_but_not_completed_entry_does_not_count_as_completed(self) -> None:
        registry = make_registry((ref(pack_id="p", activity_id="a", position=1),))
        progress = FakeProgressRepository({("p", "a"): attempted_entry("a", "p")})
        use_case = GetLearningTrack(registry, progress)

        view = use_case.execute("c")

        self.assertEqual(view.completed_activity_ids, frozenset())
        self.assertEqual(view.next_activity.activity_id, "a")

    def test_prerequisite_blocks_next_activity_until_satisfied(self) -> None:
        registry = make_registry(
            (
                ref(pack_id="p", activity_id="a", position=1),
                ref(pack_id="p", activity_id="b", position=2, prerequisites=("a",)),
            )
        )
        use_case = GetLearningTrack(registry, FakeProgressRepository({}))

        view = use_case.execute("c")

        # "a" is not completed -> "b" stays blocked; "a" is next.
        self.assertEqual(view.next_activity.activity_id, "a")

        progress_with_a_done = FakeProgressRepository({("p", "a"): completed_entry("a", "p")})
        view_after = GetLearningTrack(registry, progress_with_a_done).execute("c")
        self.assertEqual(view_after.next_activity.activity_id, "b")

    def test_language_with_no_content_returns_a_predictable_empty_view(self) -> None:
        registry = ContentRegistry()
        use_case = GetLearningTrack(registry, FakeProgressRepository({}))

        view = use_case.execute("c")

        self.assertEqual(view.track.activities, ())
        self.assertEqual(view.completed_activity_ids, frozenset())
        self.assertIsNone(view.next_activity)
        self.assertEqual(view.current_level, 1)

    def test_progress_from_an_unrelated_pack_is_ignored(self) -> None:
        registry = make_registry((ref(pack_id="p", activity_id="a", position=1),))
        progress = FakeProgressRepository({("other-pack", "a"): completed_entry("a", "other-pack")})
        use_case = GetLearningTrack(registry, progress)

        view = use_case.execute("c")

        self.assertEqual(view.completed_activity_ids, frozenset())


class GetNextLearningActivityTest(unittest.TestCase):
    def test_returns_the_same_next_activity_as_get_learning_track(self) -> None:
        registry = make_registry((ref(pack_id="p", activity_id="a", position=1),))
        get_track = GetLearningTrack(registry, FakeProgressRepository({}))
        use_case = GetNextLearningActivity(get_track)

        self.assertEqual(use_case.execute("c").activity_id, "a")

    def test_returns_none_when_track_is_empty(self) -> None:
        get_track = GetLearningTrack(ContentRegistry(), FakeProgressRepository({}))
        use_case = GetNextLearningActivity(get_track)

        self.assertIsNone(use_case.execute("c"))


if __name__ == "__main__":
    unittest.main()
