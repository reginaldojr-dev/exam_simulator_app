# Learning content model (v1)

This document describes the foundation added in this phase for continuous,
per-language progression. It intentionally implements a small, deterministic
slice of the eventual system -- see "Deferred to the future" at the end for
what is explicitly not here yet.

## LearningTrack

A `LearningTrack` (`rankeddojo.domain.learning`) is an ordered sequence of
`LearningActivityRef` entries for a single, stable technical `language` id
(for example `"c"`, `"python"`). It is a pure domain concept: no filesystem,
no UI, no dependency on packs or any specific loader.

Each `LearningActivityRef` carries:

- `language`, `pack_id`, `activity_id` -- stable technical identifiers, never
  translated/presentation strings.
- `position` -- the activity's 1-based slot within its language's track,
  assigned by `ContentRegistry` once all providers are combined.
- `title`, `topics` -- presentation/metadata, safe to localize later without
  affecting logic.
- `difficulty` -- optional free-form technical label (e.g. `"intro"`,
  `"easy"`). It is metadata only: nothing in this phase uses it to select or
  gate content. It exists so a future adaptive/selection system has
  something to read.
- `prerequisites` -- optional tuple of other `activity_id`s from the **same
  pack** that must be completed first. Prerequisites are intentionally
  **pack-scoped only** (never cross-pack, never cross-language): this avoids
  ambiguity when multiple packs are concatenated into one language's track,
  and keeps validation a simple, non-solver graph check (duplicate-id
  check, unknown-reference check, and a white/gray/black DFS cycle check --
  see `domain/learning.py::validate_track`). An invalid or cyclic pack is
  simply treated as invalid content: the registry falls back to an empty
  track for that language and records the reason in `ContentRegistry.errors`
  rather than crashing the app.

## What "level" means in v1

"Level" is `LearningActivityRef.position`: the 1-based index of an activity
within *its own language's* track. It is:

- **not** a global score or experience value;
- **not** comparable across languages -- the same position in two languages
  can (and usually will) cover entirely different topics. For example, C
  position 18 might be about pointers while Python position 18 is about
  dictionaries/comprehensions; both are valid, unrelated facts.
- derived, not stored: `current_level()` returns the position of the first
  not-yet-completed activity (or `len(activities) + 1` once everything is
  completed, or `1` for an empty track).

## ContentRegistry

`ContentRegistry` (`rankeddojo.application.engine.content_registry`)
combines one or more `ContentProvider`s into queryable `LearningTrack`s. It:

- registers providers by id (`register_provider`), rejecting a duplicate id
  (`DuplicateContentProviderError`) rather than silently overriding it;
- lists available languages across every provider (`languages()`);
- builds a language's track (`track(language)`) by concatenating each
  provider's activities *in registration order*, then reassigning `position`
  sequentially across the combined result, then validating the result
  (`validate_track`);
- isolates provider failures: if one provider raises while producing
  activities for a language, that failure is recorded under
  `errors["<provider_id>:<language>"]` and the other providers' content is
  still returned -- one bad provider never breaks the whole track;
- never executes a grader, opens a workspace, touches PySide6, calculates
  XP, decides adaptive selection, or reaches the network. It only combines
  what providers already produced.

A registry with no providers, or a language with no content, returns a
valid, predictable, empty `LearningTrack` rather than raising.

## Providers

`ContentProvider` (`rankeddojo.ports.content_provider`) is a small Protocol:
`languages()`, `activities(language)`, and an `errors` property. Two
providers exist in this phase, both in `rankeddojo.adapters.learning`:

- **`PackContentProvider`** -- adapts the existing `LocalPackCatalog` (the
  same class already used for training/exam packs) into a `ContentProvider`.
  It does not reimplement pack discovery or parsing; it only reads packs
  that opted in via `pack.json`'s `learning_track: true` and reshapes their
  exercises into `LearningActivityRef`s, carrying over `topics`,
  `difficulty`, and `prerequisites` from each exercise's definition.
  Instantiating it twice against two different directories
  (`bundled_sample_packs_dir()` and `managed_packs_dir()`) is how built-in
  and installed-pack content are both served through the same provider
  class -- `LocalPackCatalog` already treats "which directory to scan" as
  its only distinguishing input.

A future `RemoteContentProvider` can implement the same `ContentProvider`
Protocol without any change to `ContentRegistry` or the providers above --
but it is not implemented in this phase, and the registry performs no
network access.

## Built-in vs. installed-pack content

There is no separate "built-in content" format. Built-in content is simply
the bundled example packs (`examples/packs/...`) read through the same
`PackContentProvider`/`LocalPackCatalog` machinery as a user's installed
packs, just pointed at the bundled directory instead of the managed one.
`AppFactory.create_content_registry()` wires both:

- provider id `"builtin"` -> bundled sample packs;
- provider id `"installed"` -> the user's managed packs directory.

As a pilot, four bundled example packs (`c-basics`, `cpp-basics`,
`python-basics`, `java-basics`) were opted in (`learning_track: true`), and
their exercises were annotated with a `difficulty` label. `c-basics`
additionally has a small `prerequisites` chain across its five exercises, to
exercise prerequisite-gated progression end to end. This is deliberately a
small pilot, not a content library -- the model is built to grow
indefinitely without further structural changes.

## Pack compatibility

Old packs remain valid with zero changes:

- `pack.json`'s `learning_track` field is optional and defaults to `False`
  when absent -- a pack that has never heard of learning tracks imports
  exactly as it did before this phase and never appears in any
  `ContentRegistry` result.
- `exercise.json`'s `difficulty`/`prerequisites` fields are optional and
  only read starting at `schema_version 3`; older schema versions never
  attempt to read them, and their absence never blocks loading.
- A pack or exercise with no learning metadata can still be used normally
  for training/exam -- it simply never enters a track.

## How progress is derived

No new progress store was introduced. `GetLearningTrack`
(`rankeddojo.application.use_cases.get_learning_track`) reads the existing
`TrainerProgressRepository.progress_by_key()` (already implemented by
`SQLiteProgressRepository`) and treats an activity as completed when its
`(pack_id, activity_id)` key has a `ProgressEntry` whose `status` is
`ActivityProgress.COMPLETED`. `LearningActivityRef.progress_key` exists
specifically to match that key's shape, so no translation layer is needed.
From that derived "completed" set, `GetLearningTrack` computes:

- `current_level` (see above);
- `next_activity` -- the first not-yet-completed activity in track order
  whose prerequisites (if any) are all in the completed set.

## APIs added

- `GetLearningTrack.execute(language) -> LearningTrackView` -- returns the
  track, the derived completed-id set, the current level, and the next
  activity. No Qt dependency; pure application/domain types.
- `GetNextLearningActivity.execute(language) -> LearningActivityRef | None`
  -- thin convenience wrapper over `GetLearningTrack`.

Neither use case is wired into application startup or the UI in this phase
-- nothing currently calls them, so existing startup behavior and the
existing UI are unchanged.

## Deferred to the future

Deliberately out of scope for this phase: XP, achievements, badges, visual
ranks, an adaptive/recommendation engine, mastery scoring, spaced
repetition, placement tests, cloud sync, a remote content provider, a
marketplace, AI-generated exercises, an extension manager, an extensions UI,
and any UI surface consuming this model. The data shapes above (`difficulty`
as metadata, the `ContentProvider` Protocol, provider ids) were chosen so
that a future phase can add these without breaking the contracts introduced
here.
