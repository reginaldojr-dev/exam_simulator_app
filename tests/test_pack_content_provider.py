"""Fase 9: validates `PackContentProvider`, which adapts `LocalPackCatalog`
into a `ContentProvider`. It reuses pack discovery/parsing entirely -- these
tests write real `pack.json`/`exercise.json` files to a temp directory and
let the real `LocalPackCatalog`/`JsonPackLoader`/`JsonExerciseDefinitionLoader`
do the reading, exactly like the app would.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rankeddojo.adapters.learning.pack_content_provider import PackContentProvider
from rankeddojo.adapters.pack.local_pack_catalog import LocalPackCatalog


def _write_pack(root: Path, pack_id: str, *, language: str = "c", learning_track: bool | None = True, exercises: list[dict] | None = None) -> None:
    pack_dir = root / pack_id
    pack_data = {
        "schema_version": 3,
        "id": pack_id,
        "name": pack_id.title(),
        "version": "1.0.0",
        "language": language,
        "levels": [{"id": "level0", "path": "level0"}],
    }
    if learning_track is not None:
        pack_data["learning_track"] = learning_track
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.json").write_text(json.dumps(pack_data), encoding="utf-8")

    exercises = exercises or [{"id": "ex1"}]
    for exercise in exercises:
        exercise_id = exercise["id"]
        exercise_dir = pack_dir / "level0" / exercise_id
        exercise_dir.mkdir(parents=True)
        exercise_data = {
            "schema_version": 3,
            "id": exercise_id,
            "type": "exercise",
            "name": exercise_id.title(),
            "subject": "subject.md",
            "programming_language": language,
            "submission": {"filename": f"{exercise_id}.txt"},
            "validation": {
                "strategy": "program_output",
                "tests": {"generator": "fixed_cases", "expectation": "literal", "cases": [{"args": [], "expected": "ok\n"}]},
            },
        }
        exercise_data.update({k: v for k, v in exercise.items() if k != "id"})
        (exercise_dir / "subject.md").write_text("Subject.\n", encoding="utf-8")
        (exercise_dir / "exercise.json").write_text(json.dumps(exercise_data), encoding="utf-8")


class PackContentProviderOptInTest(unittest.TestCase):
    def test_pack_without_learning_track_field_does_not_participate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            managed = Path(tmp) / "managed"
            _write_pack(managed, "old-pack", learning_track=None)  # field entirely absent
            provider = PackContentProvider(LocalPackCatalog(managed))

            self.assertEqual(provider.languages(), ())
            self.assertEqual(provider.activities("c"), ())

    def test_pack_with_learning_track_false_does_not_participate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            managed = Path(tmp) / "managed"
            _write_pack(managed, "off-pack", learning_track=False)
            provider = PackContentProvider(LocalPackCatalog(managed))

            self.assertEqual(provider.languages(), ())

    def test_pack_with_learning_track_true_participates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            managed = Path(tmp) / "managed"
            _write_pack(managed, "on-pack", learning_track=True)
            provider = PackContentProvider(LocalPackCatalog(managed))

            self.assertEqual(provider.languages(), ("c",))
            activities = provider.activities("c")
            self.assertEqual(len(activities), 1)
            self.assertEqual(activities[0].pack_id, "on-pack")
            self.assertEqual(activities[0].activity_id, "ex1")


class PackContentProviderMetadataTest(unittest.TestCase):
    def test_activity_carries_topics_difficulty_and_prerequisites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            managed = Path(tmp) / "managed"
            _write_pack(
                managed,
                "meta-pack",
                exercises=[
                    {"id": "a", "topics": ["basics"], "difficulty": "intro"},
                    {"id": "b", "topics": ["loops"], "difficulty": "easy", "prerequisites": ["a"]},
                ],
            )
            provider = PackContentProvider(LocalPackCatalog(managed))

            activities = {activity.activity_id: activity for activity in provider.activities("c")}

            self.assertEqual(activities["a"].topics, ("basics",))
            self.assertEqual(activities["a"].difficulty, "intro")
            self.assertEqual(activities["a"].prerequisites, ())
            self.assertEqual(activities["b"].prerequisites, ("a",))

    def test_activity_without_learning_metadata_still_participates(self) -> None:
        """Absence of difficulty/prerequisites/topics never blocks a pack
        that opted in with `learning_track: true` -- that metadata is
        entirely optional per activity."""
        with tempfile.TemporaryDirectory() as tmp:
            managed = Path(tmp) / "managed"
            _write_pack(managed, "bare-pack", exercises=[{"id": "ex1"}])
            provider = PackContentProvider(LocalPackCatalog(managed))

            activities = provider.activities("c")

            self.assertEqual(len(activities), 1)
            self.assertIsNone(activities[0].difficulty)
            self.assertEqual(activities[0].prerequisites, ())


class PackContentProviderLanguagesTest(unittest.TestCase):
    def test_different_packs_of_different_languages_report_their_own_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            managed = Path(tmp) / "managed"
            _write_pack(managed, "c-pack", language="c")
            _write_pack(managed, "python-pack", language="python")
            provider = PackContentProvider(LocalPackCatalog(managed))

            self.assertEqual(provider.languages(), ("c", "python"))
            self.assertEqual(len(provider.activities("c")), 1)
            self.assertEqual(len(provider.activities("python")), 1)
            self.assertEqual(provider.activities("java"), ())


class PackContentProviderErrorsTest(unittest.TestCase):
    def test_errors_delegate_to_the_underlying_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            managed = Path(tmp) / "managed"
            broken = managed / "broken-pack"
            broken.mkdir(parents=True)
            (broken / "pack.json").write_text("{not json", encoding="utf-8")
            catalog = LocalPackCatalog(managed)
            provider = PackContentProvider(catalog)

            provider.activities("c")  # triggers a scan

            self.assertEqual(provider.errors, catalog.load_errors)
            self.assertTrue(provider.errors)


if __name__ == "__main__":
    unittest.main()
