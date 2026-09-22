from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from exam_trainer.adapters.compiler.system_c_compiler import SystemCCompiler
from exam_trainer.adapters.grader.generic_c_grader import GenericCGrader
from exam_trainer.domain.exercise_definition import (
    ExerciseDefinition,
    ExecutionDefinition,
    LimitsDefinition,
    SubmissionDefinition,
    TestDefinition,
)
from exam_trainer.domain.grading import GradingPolicy
from exam_trainer.ports.grader_port import GradingRequest


class GraderIntegrationTest(unittest.TestCase):
    def test_program_output_passes_with_real_compiler_when_available(self) -> None:
        compiler = SystemCCompiler()
        if not compiler.is_available():
            self.skipTest("No C compiler available.")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            exercise_path = root / "exercise"
            workspace.mkdir()
            exercise_path.mkdir()
            (workspace / "echo_args.c").write_text(
                """
                #include <stdio.h>

                int main(int argc, char **argv)
                {
                    for (int i = 1; i < argc; i++)
                    {
                        if (i > 1)
                            printf(" ");
                        printf("%s", argv[i]);
                    }
                    printf("\\n");
                    return 0;
                }
                """,
                encoding="utf-8",
            )
            definition = ExerciseDefinition(
                id="echo_args",
                name="Echo Args",
                subject=Path("subject.md"),
                submission=SubmissionDefinition(filename="echo_args.c"),
                execution=ExecutionDefinition(type="program_output"),
                tests=TestDefinition(
                    generator="random_arguments",
                    expectation="echo_arguments",
                ),
                limits=LimitsDefinition(timeout_seconds=2),
            )

            result = GenericCGrader(compiler).grade(
                GradingRequest(
                    definition=definition,
                    exercise_path=exercise_path,
                    workspace_path=workspace,
                    policy=GradingPolicy.training(),
                    seed=42,
                )
            )

            self.assertTrue(result.passed, result.trace_data.as_text())
            self.assertTrue(result.test_results)
