"""Fase 9: pure domain tests for the learning track model
(`domain/learning.py`) -- no filesystem, no packs, no registry involved.
"""

from __future__ import annotations

import unittest

from rankeddojo.domain.learning import (
    LearningActivityRef,
    LearningContentError,
    LearningTrack,
    current_level,
    select_next_activity,
    validate_track,
)


def ref(
    *,
    language: str = "c",
    pack_id: str = "pack-a",
    activity_id: str,
    position: int,
    prerequisites: tuple[str, ...] = (),
    topics: tuple[str, ...] = (),
    difficulty: str | None = None,
) -> LearningActivityRef:
    return LearningActivityRef(
        language=language,
        pack_id=pack_id,
        activity_id=activity_id,
        position=position,
        title=activity_id.replace("_", " ").title(),
        topics=topics,
        difficulty=difficulty,
        prerequisites=prerequisites,
    )


class LearningTrackTest(unittest.TestCase):
    def test_activity_ids_preserve_track_order(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(
                ref(activity_id="a", position=1),
                ref(activity_id="b", position=2),
            ),
        )
        self.assertEqual(track.activity_ids, ("a", "b"))

    def test_get_returns_matching_activity(self) -> None:
        track = LearningTrack(language="c", activities=(ref(activity_id="a", position=1),))
        self.assertEqual(track.get("a").activity_id, "a")

    def test_get_returns_none_for_unknown_id(self) -> None:
        track = LearningTrack(language="c", activities=(ref(activity_id="a", position=1),))
        self.assertIsNone(track.get("does-not-exist"))

    def test_empty_track_is_a_valid_state(self) -> None:
        track = LearningTrack(language="c", activities=())
        self.assertEqual(track.activity_ids, ())
        self.assertIsNone(track.get("anything"))


class SameLevelDifferentLanguageTest(unittest.TestCase):
    def test_same_position_means_different_topics_in_different_languages(self) -> None:
        """Explicitly validates the rule from the phase spec: position (v1
        'level') is per language and never implies equivalence between
        languages."""
        c_track = LearningTrack(
            language="c",
            activities=(ref(language="c", activity_id="pointers_1", position=18, topics=("pointers",)),),
        )
        python_track = LearningTrack(
            language="python",
            activities=(
                ref(language="python", activity_id="dict_comprehension", position=18, topics=("dictionaries", "comprehensions")),
            ),
        )

        c_activity = c_track.get("pointers_1")
        python_activity = python_track.get("dict_comprehension")

        self.assertEqual(c_activity.position, python_activity.position)
        self.assertNotEqual(c_activity.topics, python_activity.topics)


class ValidateTrackDuplicateTest(unittest.TestCase):
    def test_duplicate_activity_id_within_a_pack_is_rejected(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(
                ref(pack_id="pack-a", activity_id="dup", position=1),
                ref(pack_id="pack-a", activity_id="dup", position=2),
            ),
        )
        with self.assertRaisesRegex(LearningContentError, "duplicate activity id"):
            validate_track(track)

    def test_same_activity_id_in_different_packs_is_allowed(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(
                ref(pack_id="pack-a", activity_id="intro", position=1),
                ref(pack_id="pack-b", activity_id="intro", position=2),
            ),
        )
        validate_track(track)  # must not raise


class ValidateTrackPrerequisitesTest(unittest.TestCase):
    def test_valid_prerequisite_chain_passes(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(
                ref(activity_id="a", position=1),
                ref(activity_id="b", position=2, prerequisites=("a",)),
            ),
        )
        validate_track(track)  # must not raise

    def test_unknown_prerequisite_is_rejected(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(ref(activity_id="a", position=1, prerequisites=("does-not-exist",)),),
        )
        with self.assertRaisesRegex(LearningContentError, "unknown prerequisite"):
            validate_track(track)

    def test_prerequisite_from_a_different_pack_is_rejected_as_unknown(self) -> None:
        """Prerequisites resolve within the same pack only -- see the module
        docstring in `domain/learning.py`."""
        track = LearningTrack(
            language="c",
            activities=(
                ref(pack_id="pack-a", activity_id="a", position=1),
                ref(pack_id="pack-b", activity_id="b", position=2, prerequisites=("a",)),
            ),
        )
        with self.assertRaisesRegex(LearningContentError, "unknown prerequisite"):
            validate_track(track)

    def test_simple_two_node_cycle_is_rejected(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(
                ref(activity_id="a", position=1, prerequisites=("b",)),
                ref(activity_id="b", position=2, prerequisites=("a",)),
            ),
        )
        with self.assertRaisesRegex(LearningContentError, "cycle"):
            validate_track(track)

    def test_self_referential_prerequisite_is_rejected_as_a_cycle(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(ref(activity_id="a", position=1, prerequisites=("a",)),),
        )
        with self.assertRaisesRegex(LearningContentError, "cycle"):
            validate_track(track)

    def test_longer_cycle_is_rejected(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(
                ref(activity_id="a", position=1, prerequisites=("c",)),
                ref(activity_id="b", position=2, prerequisites=("a",)),
                ref(activity_id="c", position=3, prerequisites=("b",)),
            ),
        )
        with self.assertRaisesRegex(LearningContentError, "cycle"):
            validate_track(track)

    def test_diamond_shaped_prerequisites_are_not_a_cycle(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(
                ref(activity_id="a", position=1),
                ref(activity_id="b", position=2, prerequisites=("a",)),
                ref(activity_id="c", position=3, prerequisites=("a",)),
                ref(activity_id="d", position=4, prerequisites=("b", "c")),
            ),
        )
        validate_track(track)  # must not raise


class SelectNextActivityTest(unittest.TestCase):
    def test_first_activity_with_no_prerequisites_when_nothing_completed(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(ref(activity_id="a", position=1), ref(activity_id="b", position=2)),
        )
        next_activity = select_next_activity(track, completed_activity_ids=frozenset())
        self.assertEqual(next_activity.activity_id, "a")

    def test_skips_completed_activities(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(ref(activity_id="a", position=1), ref(activity_id="b", position=2)),
        )
        next_activity = select_next_activity(track, completed_activity_ids=frozenset({"a"}))
        self.assertEqual(next_activity.activity_id, "b")

    def test_returns_none_when_everything_completed(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(ref(activity_id="a", position=1), ref(activity_id="b", position=2)),
        )
        next_activity = select_next_activity(track, completed_activity_ids=frozenset({"a", "b"}))
        self.assertIsNone(next_activity)

    def test_activity_with_unsatisfied_prerequisite_is_blocked(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(
                ref(activity_id="a", position=1),
                ref(activity_id="b", position=2, prerequisites=("a",)),
            ),
        )
        # "a" not completed yet -> "b" is blocked; nothing else is available.
        next_activity = select_next_activity(track, completed_activity_ids=frozenset())
        self.assertEqual(next_activity.activity_id, "a")

    def test_activity_becomes_available_once_prerequisite_is_completed(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(
                ref(activity_id="a", position=1),
                ref(activity_id="b", position=2, prerequisites=("a",)),
            ),
        )
        next_activity = select_next_activity(track, completed_activity_ids=frozenset({"a"}))
        self.assertEqual(next_activity.activity_id, "b")

    def test_empty_track_returns_none(self) -> None:
        self.assertIsNone(select_next_activity(LearningTrack(language="c"), frozenset()))


class CurrentLevelTest(unittest.TestCase):
    def test_level_one_when_nothing_completed(self) -> None:
        track = LearningTrack(language="c", activities=(ref(activity_id="a", position=1),))
        self.assertEqual(current_level(track, frozenset()), 1)

    def test_level_advances_past_completed_activities(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(ref(activity_id="a", position=1), ref(activity_id="b", position=2)),
        )
        self.assertEqual(current_level(track, frozenset({"a"})), 2)

    def test_level_is_len_plus_one_once_everything_completed(self) -> None:
        track = LearningTrack(
            language="c",
            activities=(ref(activity_id="a", position=1), ref(activity_id="b", position=2)),
        )
        self.assertEqual(current_level(track, frozenset({"a", "b"})), 3)

    def test_empty_track_is_level_one(self) -> None:
        self.assertEqual(current_level(LearningTrack(language="c"), frozenset()), 1)


if __name__ == "__main__":
    unittest.main()
