"""Learning track model: progression through one language's activities.

A `LearningTrack` is built once content has already been discovered
elsewhere (see `ports/content_provider.py` and
`application/engine/content_registry.py`); nothing here touches the
filesystem, a pack, or a registry -- it only operates on the
`LearningActivityRef` values it is given. This keeps the model pure and
testable independent of how content was found.

Progression is per language: `position` (the v1 meaning of "level"; see
`current_level`) in one language's track has no relationship to the same
`position` in another language's track. The same number can sit on a
completely different concept in each language -- that is expected, not a
bug to reconcile.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LearningActivityRef:
    """One activity's place within a language's learning track.

    `pack_id`/`activity_id` together are the same identity progress is
    already tracked under (see `domain.progress.ProgressEntry.identity`);
    nothing new is introduced for identity, and `progress_key` below matches
    `TrainerProgressRepository.progress_by_key()`'s key shape exactly so a
    track can be joined against existing progress without translation.

    `prerequisites` only ever names other `activity_id`s from the *same*
    pack -- there is no cross-pack or cross-language dependency resolution
    in v1 (see `validate_track`).
    """

    language: str
    pack_id: str
    activity_id: str
    position: int
    title: str
    topics: tuple[str, ...] = ()
    difficulty: str | None = None
    prerequisites: tuple[str, ...] = ()

    @property
    def progress_key(self) -> tuple[str, str]:
        return (self.pack_id, self.activity_id)


@dataclass(frozen=True)
class LearningTrack:
    """A language's activities, ordered by `position` (1-based, assigned by
    `ContentRegistry` once all providers' content for that language has been
    combined -- see `ContentRegistry.track`)."""

    language: str
    activities: tuple[LearningActivityRef, ...] = ()

    @property
    def activity_ids(self) -> tuple[str, ...]:
        return tuple(ref.activity_id for ref in self.activities)

    def get(self, activity_id: str) -> LearningActivityRef | None:
        for ref in self.activities:
            if ref.activity_id == activity_id:
                return ref
        return None


class LearningContentError(ValueError):
    """The assembled track has invalid content: a duplicate activity id
    inside one pack, an unknown prerequisite, or a prerequisite cycle.
    Raised only while validating (`validate_track`); callers are expected to
    record it and fall back to an empty track rather than let it crash the
    app (see `ContentRegistry.track`) -- the same "never crash on bad
    content" discipline packs, themes and plugins already follow."""


def validate_track(track: LearningTrack) -> None:
    """Checks the track's internal consistency.

    Both checks are scoped to a single `pack_id` at a time, never across the
    whole track: a duplicate `activity_id` inside one pack is invalid
    content authored wrong, and a prerequisite can only reference a sibling
    exercise in the same pack (see `LearningActivityRef`), so there is
    nothing to resolve across packs or languages -- no dependency solver,
    just simple existence and a plain cycle check per pack.
    """
    by_pack: dict[str, dict[str, LearningActivityRef]] = {}
    for ref in track.activities:
        pack_activities = by_pack.setdefault(ref.pack_id, {})
        if ref.activity_id in pack_activities:
            raise LearningContentError(
                f"Pack '{ref.pack_id}' has duplicate activity id: {ref.activity_id}."
            )
        pack_activities[ref.activity_id] = ref

    for pack_id, activities in by_pack.items():
        _validate_prerequisites(pack_id, activities)


def _validate_prerequisites(pack_id: str, activities: dict[str, LearningActivityRef]) -> None:
    for ref in activities.values():
        unknown = [prereq for prereq in ref.prerequisites if prereq not in activities]
        if unknown:
            raise LearningContentError(
                f"Pack '{pack_id}' activity '{ref.activity_id}' has unknown prerequisite(s): "
                f"{', '.join(unknown)}."
            )

    white, gray, black = 0, 1, 2
    color = {activity_id: white for activity_id in activities}

    def visit(activity_id: str, path: tuple[str, ...]) -> None:
        color[activity_id] = gray
        for prereq in activities[activity_id].prerequisites:
            if color[prereq] == gray:
                chain = " -> ".join((*path, prereq))
                raise LearningContentError(f"Pack '{pack_id}' has a prerequisite cycle: {chain}.")
            if color[prereq] == white:
                visit(prereq, (*path, prereq))
        color[activity_id] = black

    for activity_id in activities:
        if color[activity_id] == white:
            visit(activity_id, (activity_id,))


def select_next_activity(
    track: LearningTrack, completed_activity_ids: frozenset[str]
) -> LearningActivityRef | None:
    """The first not-yet-completed activity, in track order, whose
    prerequisites (if any) are all completed. No adaptive logic: a plain
    linear scan plus a simple prerequisite check -- when an activity has no
    prerequisites, track order alone decides (`set(()) <= anything` is
    always true)."""
    for ref in track.activities:
        if ref.activity_id in completed_activity_ids:
            continue
        if set(ref.prerequisites) <= completed_activity_ids:
            return ref
    return None


def current_level(track: LearningTrack, completed_activity_ids: frozenset[str]) -> int:
    """The learner's position (1-based) within THIS language's track: the
    `position` of the first not-yet-completed activity, or
    `len(activities) + 1` once every activity is completed. An empty track
    is level 1. This is a position, never a score, never XP, and never
    comparable across languages -- see the module docstring."""
    for ref in track.activities:
        if ref.activity_id not in completed_activity_ids:
            return ref.position
    return len(track.activities) + 1 if track.activities else 1
