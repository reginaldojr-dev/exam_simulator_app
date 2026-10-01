"""Fase 9: schema-level validation for the two new optional contract
fields -- `pack.json`'s `learning_track` and `exercise.json`'s `difficulty`/
`prerequisites`. Complements `test_pack_content_provider.py` (which exercises
these through the real catalog) by testing the loaders directly.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rankeddojo.adapters.exercise_definition.json_loader import (
    ExerciseDefinitionError,
    JsonExerciseDefinitionLoader,
)
from rankeddojo.adapters.pack.json_pack_loader import JsonPackLoader, PackDefinitionError


def v3_pack(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": 3,
        "id": "pack",
        "name": "Pack",
        "version": "1.0.0",
        "language": "c",
        "levels": [{"id": "level0", "path": "level0"}],
    }
    data.update(overrides)
    return data


def v3_exercise(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": 3,
        "id": "ex",
        "type": "exercise",
        "name": "Ex",
        "subject": "subject.md",
        "programming_language": "c",
        "submission": {"filename": "ex.c"},
        "validation": {
            "strategy": "program_output",
            "tests": {
                "generator": "fixed_cases",
                "expectation": "literal",
                "cases": [{"args": [], "expected": "ok\n"}],
            },
        },
    }
    data.update(overrides)
    return data


def _write_pack_json(pack_data: dict[str, object]) -> Path:
    """Writes only `pack.json` (plus the minimal level dir it references) to
    a fresh temp directory and returns the pack.json path, so the real,
    public `JsonPackLoader.load(path)` can be exercised end to end."""
    tmp_dir = Path(tempfile.mkdtemp())
    level_dir = tmp_dir / "level0"
    level_dir.mkdir(parents=True)
    pack_path = tmp_dir / "pack.json"
    pack_path.write_text(json.dumps(pack_data), encoding="utf-8")
    return pack_path


class PackLearningTrackFieldTest(unittest.TestCase):
    def test_absent_learning_track_defaults_to_false(self) -> None:
        data = v3_pack()
        data.pop("learning_track", None)
        pack_path = _write_pack_json(data)

        pack = JsonPackLoader().load(pack_path)

        self.assertFalse(pack.learning_track)

    def test_true_is_accepted(self) -> None:
        pack_path = _write_pack_json(v3_pack(learning_track=True))

        pack = JsonPackLoader().load(pack_path)

        self.assertTrue(pack.learning_track)

    def test_false_is_accepted(self) -> None:
        pack_path = _write_pack_json(v3_pack(learning_track=False))

        pack = JsonPackLoader().load(pack_path)

        self.assertFalse(pack.learning_track)

    def test_non_boolean_learning_track_is_rejected(self) -> None:
        pack_path = _write_pack_json(v3_pack(learning_track="yes"))

        with self.assertRaisesRegex(PackDefinitionError, "learning_track"):
            JsonPackLoader().load(pack_path)


class ExerciseDifficultyFieldTest(unittest.TestCase):
    def test_absent_difficulty_is_none(self) -> None:
        definition = JsonExerciseDefinitionLoader().load_data(v3_exercise())
        self.assertIsNone(definition.difficulty)

    def test_valid_difficulty_is_kept(self) -> None:
        definition = JsonExerciseDefinitionLoader().load_data(v3_exercise(difficulty="intro"))
        self.assertEqual(definition.difficulty, "intro")

    def test_empty_difficulty_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExerciseDefinitionError, "difficulty"):
            JsonExerciseDefinitionLoader().load_data(v3_exercise(difficulty="   "))

    def test_overly_long_difficulty_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExerciseDefinitionError, "difficulty"):
            JsonExerciseDefinitionLoader().load_data(v3_exercise(difficulty="x" * 41))

    def test_non_string_difficulty_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExerciseDefinitionError, "difficulty"):
            JsonExerciseDefinitionLoader().load_data(v3_exercise(difficulty=5))


class ExercisePrerequisitesFieldTest(unittest.TestCase):
    def test_absent_prerequisites_is_empty_tuple(self) -> None:
        definition = JsonExerciseDefinitionLoader().load_data(v3_exercise())
        self.assertEqual(definition.prerequisites, ())

    def test_valid_prerequisites_are_kept_in_order_and_deduplicated(self) -> None:
        definition = JsonExerciseDefinitionLoader().load_data(
            v3_exercise(prerequisites=["a", "b", "a"])
        )
        self.assertEqual(definition.prerequisites, ("a", "b"))

    def test_non_list_prerequisites_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExerciseDefinitionError, "prerequisites"):
            JsonExerciseDefinitionLoader().load_data(v3_exercise(prerequisites="a"))

    def test_non_string_entry_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExerciseDefinitionError, "prerequisites"):
            JsonExerciseDefinitionLoader().load_data(v3_exercise(prerequisites=[1]))

    def test_unsafe_identifier_entry_is_rejected(self) -> None:
        with self.assertRaises(ExerciseDefinitionError):
            JsonExerciseDefinitionLoader().load_data(v3_exercise(prerequisites=["../escape"]))

    def test_self_reference_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExerciseDefinitionError, "own id"):
            JsonExerciseDefinitionLoader().load_data(v3_exercise(id="self", prerequisites=["self"]))

    def test_too_many_prerequisites_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExerciseDefinitionError, "prerequisites"):
            JsonExerciseDefinitionLoader().load_data(
                v3_exercise(prerequisites=[f"p{i}" for i in range(21)])
            )


class LegacySchemaCompatibilityTest(unittest.TestCase):
    def test_v1_and_v2_exercises_never_read_difficulty_or_prerequisites(self) -> None:
        """v1/v2 packs remain exactly as valid as before this phase -- the
        two new fields are only recognized starting at schema_version 3."""
        v1_data = {
            "id": "legacy",
            "name": "Legacy",
            "subject": "subject.md",
            "submission": {"filename": "legacy.c"},
            "execution": {"type": "program_output"},
            "tests": {"generator": "random_arguments", "expectation": "echo_arguments"},
        }
        definition = JsonExerciseDefinitionLoader().load_data(v1_data)
        self.assertIsNone(definition.difficulty)
        self.assertEqual(definition.prerequisites, ())

    def test_v1_and_v2_packs_never_read_learning_track(self) -> None:
        """A v1 pack (no schema_version key at all, the oldest contract)
        keeps `learning_track` at its dataclass default -- absence of the
        key never breaks loading."""
        v1_pack_data = {
            "id": "legacy-pack",
            "name": "Legacy Pack",
            "version": "1.0.0",
            "levels": [{"id": "level0", "path": "level0"}],
        }
        pack_path = _write_pack_json(v1_pack_data)

        pack = JsonPackLoader().load(pack_path)

        self.assertFalse(pack.learning_track)


if __name__ == "__main__":
    unittest.main()
