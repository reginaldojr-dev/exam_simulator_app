from __future__ import annotations

import unittest
from pathlib import PurePosixPath

from exam_trainer.adapters.exercise_definition.json_loader import ExerciseDefinitionError, JsonExerciseDefinitionLoader
from exam_trainer.application.engine.expectations import default_expectation_registry
from exam_trainer.application.engine.generators import default_generator_registry
from exam_trainer.application.engine.test_case_service import TestCaseService
from exam_trainer.domain.exercise_definition import (
    ExerciseDefinition,
    ExecutionDefinition,
    LimitsDefinition,
    SubmissionDefinition,
    TestCaseDefinition,
    TestDefinition,
)
from exam_trainer.domain.test_contract import ArgumentContract, ArgumentKind, TestContract


def definition(contract: TestContract | None, generator: str = "random_arguments") -> ExerciseDefinition:
    return ExerciseDefinition(
        id="contract",
        name="Contract",
        subject=PurePosixPath("subject.md"),
        submission=SubmissionDefinition("contract.c"),
        execution=ExecutionDefinition(type="program_output"),
        tests=TestDefinition(generator=generator, expectation="echo_arguments", contract=contract),
        limits=LimitsDefinition(timeout_seconds=2),
    )


class DeclarativeTestContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TestCaseService(default_generator_registry(), default_expectation_registry())

    def cases(self, contract: TestContract, generator: str = "random_arguments"):
        return self.service.build_cases(definition(contract, generator), seed=42)

    def test_last_word_and_first_word_contract_generate_exactly_one_string_arg(self) -> None:
        contract = TestContract(args=(ArgumentContract(ArgumentKind.STRING),))

        for case in self.cases(contract):
            self.assertEqual(len(case.args), 1)
            self.assertIsInstance(case.args[0], str)
            self.assertNotEqual(case.args[0], "")

    def test_wdmatch_contract_generates_exactly_two_strings(self) -> None:
        contract = TestContract(args=(ArgumentContract(ArgumentKind.STRING), ArgumentContract(ArgumentKind.STRING)))

        for case in self.cases(contract):
            self.assertEqual(len(case.args), 2)
            self.assertTrue(all(isinstance(arg, str) and arg for arg in case.args))

    def test_do_op_contract_generates_integer_operator_integer(self) -> None:
        contract = TestContract(
            args=(
                ArgumentContract(ArgumentKind.INTEGER, min_value=-20, max_value=20),
                ArgumentContract(ArgumentKind.CHOICE, values=("+", "-", "*", "/", "%")),
                ArgumentContract(ArgumentKind.INTEGER, min_value=1, max_value=20),
            )
        )

        for case in self.cases(contract):
            self.assertEqual(len(case.args), 3)
            int(case.args[0])
            self.assertIn(case.args[1], ("+", "-", "*", "/", "%"))
            int(case.args[2])

    def test_max_contract_generates_length_prefixed_integer_sequence(self) -> None:
        contract = TestContract(
            args=(
                ArgumentContract(
                    ArgumentKind.INTEGER_SEQUENCE,
                    min_value=-50,
                    max_value=50,
                    min_items=1,
                    max_items=5,
                    include_length_arg=True,
                ),
            )
        )

        for case in self.cases(contract, generator="random_int_array"):
            self.assertGreaterEqual(len(case.args), 2)
            count = int(case.args[0])
            values = case.args[1:]
            self.assertEqual(count, len(values))
            self.assertTrue(1 <= len(values) <= 5)
            for value in values:
                int(value)

    def test_ft_atoi_contract_never_generates_zero_args(self) -> None:
        contract = TestContract(args=(ArgumentContract(ArgumentKind.INTEGER),))

        for case in self.cases(contract):
            self.assertEqual(len(case.args), 1)
            int(case.args[0])

    def test_fizzbuzz_contract_generates_no_args(self) -> None:
        contract = TestContract(args=())

        for case in self.cases(contract):
            self.assertEqual(case.args, ())

    def test_same_contract_and_seed_are_deterministic(self) -> None:
        contract = TestContract(
            args=(
                ArgumentContract(ArgumentKind.INTEGER, min_value=-5, max_value=5),
                ArgumentContract(ArgumentKind.CHOICE, values=("a", "b")),
            )
        )

        first = self.service.build_cases(definition(contract), seed=99)
        second = self.service.build_cases(definition(contract), seed=99)
        other = self.service.build_cases(definition(contract), seed=100)

        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_generator_incompatible_with_contract_fails_loudly(self) -> None:
        contract = TestContract(args=(ArgumentContract(ArgumentKind.INTEGER), ArgumentContract(ArgumentKind.INTEGER)))

        with self.assertRaisesRegex(ValueError, "random_integer"):
            self.cases(contract, generator="random_integer")

    def test_fixed_cases_are_validated_against_contract(self) -> None:
        fixed = ExerciseDefinition(
            id="fixed",
            name="Fixed",
            subject=PurePosixPath("subject.md"),
            submission=SubmissionDefinition("fixed.c"),
            execution=ExecutionDefinition(type="program_output"),
            tests=TestDefinition(
                generator="fixed_cases",
                expectation="literal",
                cases=(TestCaseDefinition(args=(), expected=""),),
                contract=TestContract(args=(ArgumentContract(ArgumentKind.INTEGER),)),
            ),
            limits=LimitsDefinition(timeout_seconds=2),
        )

        with self.assertRaisesRegex(ValueError, "fewer args"):
            self.service.build_cases(fixed, seed=1)


class DeclarativeTestContractLoaderTest(unittest.TestCase):
    def v3_data(self) -> dict[str, object]:
        return {
            "schema_version": 3,
            "id": "do_op",
            "type": "exercise",
            "name": "do_op",
            "subject": "subject.md",
            "programming_language": "c",
            "content_language": "pt-BR",
            "submission": {"filename": "do_op.c"},
            "validation": {
                "strategy": "program_output",
                "tests": {
                    "generator": "random_arguments",
                    "expectation": "reference_output",
                    "contract": {
                        "args": [
                            {"kind": "integer", "min": -20, "max": 20},
                            {"kind": "choice", "values": ["+", "-", "*", "/", "%"]},
                            {"kind": "integer", "min": 1, "max": 20},
                        ]
                    },
                },
                "reference": {"source": "reference.c"},
            },
        }

    def test_loader_reads_tests_contract(self) -> None:
        definition = JsonExerciseDefinitionLoader().load_data(self.v3_data())

        self.assertIsNotNone(definition.tests.contract)
        assert definition.tests.contract is not None
        self.assertEqual(definition.tests.contract.args[1].kind, ArgumentKind.CHOICE)
        self.assertEqual(definition.tests.contract.args[1].values, ("+", "-", "*", "/", "%"))

    def test_loader_rejects_choice_without_values(self) -> None:
        data = self.v3_data()
        data["validation"]["tests"]["contract"]["args"][1] = {"kind": "choice"}

        with self.assertRaisesRegex(ExerciseDefinitionError, "values"):
            JsonExerciseDefinitionLoader().load_data(data)

    def test_loader_rejects_invalid_bounds(self) -> None:
        data = self.v3_data()
        data["validation"]["tests"]["contract"]["args"][0] = {"kind": "integer", "min": 10, "max": 1}

        with self.assertRaisesRegex(ExerciseDefinitionError, "min"):
            JsonExerciseDefinitionLoader().load_data(data)

    def test_loader_rejects_unknown_kind(self) -> None:
        data = self.v3_data()
        data["validation"]["tests"]["contract"]["args"][0] = {"kind": "regex"}

        with self.assertRaisesRegex(ExerciseDefinitionError, "argument kind"):
            JsonExerciseDefinitionLoader().load_data(data)


if __name__ == "__main__":
    unittest.main()
