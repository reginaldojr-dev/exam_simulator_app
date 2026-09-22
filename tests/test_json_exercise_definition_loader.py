from __future__ import annotations

import tempfile
import unittest
from pathlib import PurePath, Path

from exam_trainer.adapters.exercise_definition.json_loader import (
    DEFAULT_TIMEOUT_SECONDS,
    ExerciseDefinitionError,
    JsonExerciseDefinitionLoader,
)
from exam_trainer.domain.exercise_definition import ExerciseDefinition


def valid_definition_data() -> dict[str, object]:
    return {
        "id": "echo_args",
        "name": "Echo Args",
        "subject": "subject.md",
        "submission": {
            "filename": "echo_args.c",
        },
        "execution": {
            "type": "program_output",
        },
        "tests": {
            "generator": "random_string",
            "expectation": "echo_arguments",
        },
        "limits": {
            "timeout_seconds": 2,
        },
    }


class JsonExerciseDefinitionLoaderTest(unittest.TestCase):
    def test_loads_valid_definition(self) -> None:
        loader = JsonExerciseDefinitionLoader()

        definition = loader.load_data(valid_definition_data())

        self.assertIsInstance(definition, ExerciseDefinition)
        self.assertEqual(definition.id, "echo_args")
        self.assertEqual(definition.name, "Echo Args")
        self.assertEqual(definition.subject, PurePath("subject.md"))
        self.assertEqual(definition.submission.filename, "echo_args.c")
        self.assertEqual(definition.execution.type, "program_output")
        self.assertEqual(definition.tests.generator, "random_string")
        self.assertEqual(definition.tests.expectation, "echo_arguments")
        self.assertEqual(definition.limits.timeout_seconds, 2)

    def test_rejects_missing_required_field(self) -> None:
        data = valid_definition_data()
        del data["subject"]

        with self.assertRaisesRegex(ExerciseDefinitionError, "Missing required field"):
            JsonExerciseDefinitionLoader().load_data(data)

    def test_rejects_unknown_execution_type(self) -> None:
        data = valid_definition_data()
        data["execution"] = {"type": "shell_command"}

        with self.assertRaisesRegex(ExerciseDefinitionError, "Unknown execution type"):
            JsonExerciseDefinitionLoader().load_data(data)

    def test_rejects_unknown_generator(self) -> None:
        data = valid_definition_data()
        data["tests"] = {
            "generator": "unknown_generator",
            "expectation": "echo_arguments",
        }

        with self.assertRaisesRegex(ExerciseDefinitionError, "Unknown test generator"):
            JsonExerciseDefinitionLoader().load_data(data)

    def test_rejects_unknown_expectation(self) -> None:
        data = valid_definition_data()
        data["tests"] = {
            "generator": "random_string",
            "expectation": "unknown_expectation",
        }

        with self.assertRaisesRegex(ExerciseDefinitionError, "Unknown test expectation"):
            JsonExerciseDefinitionLoader().load_data(data)

    def test_rejects_negative_timeout(self) -> None:
        data = valid_definition_data()
        data["limits"] = {"timeout_seconds": -1}

        with self.assertRaisesRegex(ExerciseDefinitionError, "greater than zero"):
            JsonExerciseDefinitionLoader().load_data(data)

    def test_uses_default_timeout_when_omitted(self) -> None:
        data = valid_definition_data()
        del data["limits"]

        definition = JsonExerciseDefinitionLoader().load_data(data)

        self.assertEqual(definition.limits.timeout_seconds, DEFAULT_TIMEOUT_SECONDS)

    def test_rejects_empty_filename(self) -> None:
        data = valid_definition_data()
        data["submission"] = {"filename": ""}

        with self.assertRaisesRegex(ExerciseDefinitionError, "filename cannot be empty"):
            JsonExerciseDefinitionLoader().load_data(data)

    def test_rejects_filename_with_path_parts(self) -> None:
        data = valid_definition_data()
        data["submission"] = {"filename": "src/echo_args.c"}

        with self.assertRaisesRegex(ExerciseDefinitionError, "simple filename"):
            JsonExerciseDefinitionLoader().load_data(data)

    def test_rejects_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            exercise_json = Path(temp_dir) / "exercise.json"
            exercise_json.write_text("{ invalid json", encoding="utf-8")

            with self.assertRaisesRegex(ExerciseDefinitionError, "Invalid JSON"):
                JsonExerciseDefinitionLoader().load(exercise_json)

    def test_loads_from_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            exercise_json = Path(temp_dir) / "exercise.json"
            exercise_json.write_text(
                """
                {
                  "id": "echo_args",
                  "name": "Echo Args",
                  "subject": "subject.md",
                  "submission": {"filename": "echo_args.c"},
                  "execution": {"type": "program_output"},
                  "tests": {
                    "generator": "random_string",
                    "expectation": "echo_arguments"
                  }
                }
                """,
                encoding="utf-8",
            )

            definition = JsonExerciseDefinitionLoader().load(exercise_json)

            self.assertEqual(definition.id, "echo_args")
            self.assertEqual(definition.limits.timeout_seconds, DEFAULT_TIMEOUT_SECONDS)

    def test_function_with_main_requires_fixture(self) -> None:
        data = valid_definition_data()
        data["execution"] = {"type": "function_with_main"}

        with self.assertRaisesRegex(ExerciseDefinitionError, "fixture is required"):
            JsonExerciseDefinitionLoader().load_data(data)

    def test_function_with_main_accepts_fixture(self) -> None:
        data = valid_definition_data()
        data["execution"] = {
            "type": "function_with_main",
            "fixture": "main.c",
        }

        definition = JsonExerciseDefinitionLoader().load_data(data)

        self.assertEqual(definition.execution.fixture, PurePath("main.c"))

    def test_reference_compare_requires_reference(self) -> None:
        data = valid_definition_data()
        data["execution"] = {"type": "reference_compare"}

        with self.assertRaisesRegex(ExerciseDefinitionError, "reference is required"):
            JsonExerciseDefinitionLoader().load_data(data)

    def test_loads_reference_compare_with_fixed_cases_and_support_files(self) -> None:
        data = valid_definition_data()
        data["execution"] = {
            "type": "reference_compare",
            "fixture": "fixtures/main.c",
            "reference": "fixtures/reference.c",
        }
        data["tests"] = {
            "generator": "fixed_cases",
            "expectation": "reference_output",
            "cases": [
                {"args": ["alpha", "beta"], "stdin": "", "expected": "alpha beta\n"}
            ],
        }
        data["support_files"] = ["ft_list.h"]

        definition = JsonExerciseDefinitionLoader().load_data(data)

        self.assertEqual(definition.execution.type, "reference_compare")
        self.assertEqual(definition.execution.fixture, PurePath("fixtures/main.c"))
        self.assertEqual(definition.execution.reference, PurePath("fixtures/reference.c"))
        self.assertEqual(definition.tests.cases[0].args, ("alpha", "beta"))
        self.assertEqual(definition.tests.cases[0].expected, "alpha beta\n")
        self.assertEqual(definition.support_files, (PurePath("ft_list.h"),))

    def test_fixed_cases_require_declared_cases(self) -> None:
        data = valid_definition_data()
        data["tests"] = {
            "generator": "fixed_cases",
            "expectation": "literal",
        }

        with self.assertRaisesRegex(ExerciseDefinitionError, "tests.cases is required"):
            JsonExerciseDefinitionLoader().load_data(data)
