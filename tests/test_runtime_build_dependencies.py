from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path, PurePath
from types import SimpleNamespace
from unittest import mock

from rankeddojo.adapters.compiler.system_c_compiler import SystemCCompiler
from rankeddojo.adapters.compiler.system_cpp_compiler import SystemCppCompiler
from rankeddojo.adapters.grader.generic_grader import GenericGrader
from rankeddojo.adapters.runtime.c_runtime import CRuntime
from rankeddojo.adapters.runtime.cpp_runtime import CppRuntime
from rankeddojo.application.engine.execution import FunctionCallStrategy, ProgramOutputStrategy, reference_spec, support_include_dirs
from rankeddojo.application.engine.runtime_registry import RuntimeRegistry
from rankeddojo.domain.exercise_definition import (
    FUNCTION_CALL,
    PROGRAM_OUTPUT,
    ExecutionDefinition,
    ExerciseDefinition,
    LimitsDefinition,
    ReferenceDefinition,
    SubmissionDefinition,
    TestCaseDefinition,
    TestDefinition,
)
from rankeddojo.domain.grading import GradingPolicy
from rankeddojo.ports.compiler_port import CompilationResult
from rankeddojo.ports.grader_port import GradingRequest
from rankeddojo.ports.runtime_port import ProgramSpec


def _definition(**overrides: object) -> ExerciseDefinition:
    values: dict[str, object] = {
        "id": "with_support",
        "name": "With Support",
        "subject": PurePath("subject.md"),
        "submission": SubmissionDefinition(filename="answer.c"),
        "execution": ExecutionDefinition(type=PROGRAM_OUTPUT),
        "tests": TestDefinition(
            generator="fixed_cases",
            expectation="reference_output",
            cases=(TestCaseDefinition(args=(), expected=None),),
        ),
        "limits": LimitsDefinition(timeout_seconds=2),
        "support_files": (PurePath("support/custom_list.h"),),
        "reference": ReferenceDefinition(source=PurePath("solution/solution.c")),
        "language": "c",
    }
    values.update(overrides)
    return ExerciseDefinition(**values)  # type: ignore[arg-type]


class RecordingCompiler:
    def __init__(self) -> None:
        self.calls: list[tuple[list[Path], Path, tuple[Path, ...]]] = []

    def is_available(self) -> bool:
        return True

    def compile(
        self,
        source_files: list[Path],
        output_path: Path,
        *,
        include_dirs: tuple[Path, ...] = (),
    ) -> CompilationResult:
        self.calls.append((source_files, output_path, include_dirs))
        return CompilationResult(success=True, command=("fake",), executable_path=output_path)


class RuntimeBuildDependenciesTest(unittest.TestCase):
    def test_program_spec_defaults_include_dirs_to_empty_tuple(self) -> None:
        spec = ProgramSpec(main_source=Path("main.c"))

        self.assertEqual(spec.include_dirs, ())

    def test_program_spec_preserves_include_dirs(self) -> None:
        include_dir = Path("support")
        spec = ProgramSpec(main_source=Path("main.c"), include_dirs=(include_dir,))

        self.assertEqual(spec.include_dirs, (include_dir,))

    def test_c_compiler_adds_include_dirs_as_separate_arguments(self) -> None:
        compiler = SystemCCompiler(flags=("-Wall",))
        include_a = Path("C:/Users/Test User/Pack Files/support")
        include_b = Path("C:/pack/shared")
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch.object(compiler, "find_compiler", return_value="gcc"), mock.patch.object(
            subprocess, "run", return_value=completed
        ) as run:
            result = compiler.compile([Path("main.c")], Path("app.exe"), include_dirs=(include_a, include_b))

        self.assertTrue(result.success)
        command = run.call_args.args[0]
        self.assertEqual(
            command,
            ["gcc", "-Wall", "-I", str(include_a), "-I", str(include_b), "main.c", "-o", "app.exe"],
        )
        self.assertIn(str(include_a), result.command)

    def test_c_compiler_without_include_dirs_preserves_previous_command_shape(self) -> None:
        compiler = SystemCCompiler(flags=("-Wall",))
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch.object(compiler, "find_compiler", return_value="gcc"), mock.patch.object(
            subprocess, "run", return_value=completed
        ) as run:
            compiler.compile([Path("main.c")], Path("app.exe"))

        self.assertEqual(run.call_args.args[0], ["gcc", "-Wall", "main.c", "-o", "app.exe"])

    def test_cpp_compiler_adds_include_dirs_as_separate_arguments(self) -> None:
        compiler = SystemCppCompiler()
        include_dir = Path("C:/Users/Test User/Pack Files/support")
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch.object(compiler, "find_compiler", return_value="g++"), mock.patch.object(
            subprocess, "run", return_value=completed
        ) as run:
            result = compiler.compile([Path("main.cpp")], Path("app.exe"), include_dirs=(include_dir,))

        self.assertTrue(result.success)
        command = run.call_args.args[0]
        self.assertIn("-I", command)
        self.assertIn(str(include_dir), command)
        self.assertEqual(command[command.index("-I") + 1], str(include_dir))

    def test_cpp_compiler_without_include_dirs_preserves_previous_command_shape(self) -> None:
        compiler = SystemCppCompiler()
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch.object(compiler, "find_compiler", return_value="g++"), mock.patch.object(
            subprocess, "run", return_value=completed
        ) as run:
            compiler.compile([Path("main.cpp")], Path("app.exe"))

        command = run.call_args.args[0]
        self.assertNotIn("-I", command)
        self.assertEqual(command[-3:], ["main.cpp", "-o", "app.exe"])

    def test_support_files_derive_deduplicated_include_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            exercise = Path(temp_dir) / "pack" / "level" / "with_support"
            (exercise / "support").mkdir(parents=True)
            (exercise / "shared").mkdir()
            (exercise / "support" / "a.h").write_text("", encoding="utf-8")
            (exercise / "support" / "b.h").write_text("", encoding="utf-8")
            (exercise / "shared" / "c.h").write_text("", encoding="utf-8")
            definition = _definition(
                support_files=(
                    PurePath("support/a.h"),
                    PurePath("support/b.h"),
                    PurePath("shared/c.h"),
                )
            )

            include_dirs = support_include_dirs(definition, exercise)

        self.assertEqual(include_dirs, (exercise / "support", exercise / "shared"))

    def test_submission_and_reference_specs_receive_same_support_include_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            exercise = root / "pack" / "level" / "with_support"
            workspace = root / "workspace"
            (exercise / "support").mkdir(parents=True)
            (exercise / "solution").mkdir()
            workspace.mkdir()
            (exercise / "support" / "custom_list.h").write_text("", encoding="utf-8")
            (exercise / "solution" / "solution.c").write_text("", encoding="utf-8")
            (workspace / "answer.c").write_text("", encoding="utf-8")
            definition = _definition()

            submission = ProgramOutputStrategy().submission(definition, exercise, workspace / "answer.c")
            reference = reference_spec(definition, exercise)

        self.assertEqual(submission.include_dirs, (exercise / "support",))
        self.assertEqual(reference.include_dirs, submission.include_dirs)
        self.assertNotIn(workspace, submission.include_dirs)

    def test_harness_solution_and_submission_scenarios_get_support_include_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            exercise = root / "exercise"
            workspace = root / "workspace"
            for directory in ("support", "harness", "solution"):
                (exercise / directory).mkdir(parents=True, exist_ok=True)
            workspace.mkdir()
            (exercise / "support" / "custom_list.h").write_text("", encoding="utf-8")
            (exercise / "harness" / "main.c").write_text("", encoding="utf-8")
            (exercise / "solution" / "solution.c").write_text("", encoding="utf-8")
            (workspace / "answer.c").write_text("", encoding="utf-8")
            definition = _definition(
                execution=ExecutionDefinition(type=FUNCTION_CALL, fixture=PurePath("harness/main.c")),
                reference=ReferenceDefinition(source=PurePath("solution/solution.c"), harness=PurePath("harness/main.c")),
            )

            submission = FunctionCallStrategy().submission(definition, exercise, workspace / "answer.c")
            reference = reference_spec(definition, exercise)

        self.assertEqual(submission.include_dirs, (exercise / "support",))
        self.assertEqual(reference.include_dirs, (exercise / "support",))
        self.assertEqual(reference.include_dirs, submission.include_dirs)

    def test_c_runtime_passes_program_spec_include_dirs_to_compiler(self) -> None:
        compiler = RecordingCompiler()
        runtime = CRuntime(compiler)
        include_dir = Path("support")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "main.c"
            source.write_text("int main(void){return 0;}", encoding="utf-8")
            runtime.prepare(ProgramSpec(main_source=source, include_dirs=(include_dir,)), root / "build", "app")

        self.assertEqual(compiler.calls[0][2], (include_dir,))

    def test_cpp_runtime_passes_program_spec_include_dirs_to_compiler(self) -> None:
        compiler = RecordingCompiler()
        runtime = CppRuntime(compiler)
        include_dir = Path("support")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "main.cpp"
            source.write_text("int main(){return 0;}", encoding="utf-8")
            runtime.prepare(ProgramSpec(main_source=source, include_dirs=(include_dir,)), root / "build", "app")

        self.assertEqual(compiler.calls[0][2], (include_dir,))


@unittest.skipUnless(SystemCCompiler().is_available(), "no compatible C compiler")
class RuntimeBuildDependenciesIntegrationTest(unittest.TestCase):
    def test_header_in_support_is_visible_to_harness_reference_and_submission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            exercise = root / "exercise"
            workspace = root / "workspace"
            for directory in ("support", "harness", "solution"):
                (exercise / directory).mkdir(parents=True)
            workspace.mkdir()
            (exercise / "support" / "custom_list.h").write_text(
                "typedef struct s_node { int value; struct s_node *next; } t_node;\n",
                encoding="utf-8",
            )
            (exercise / "harness" / "main.c").write_text(
                '#include <stdio.h>\n'
                '#include "custom_list.h"\n'
                "int list_total(t_node *node);\n"
                "int main(void) {\n"
                "  t_node b = {3, 0};\n"
                "  t_node a = {2, &b};\n"
                '  printf("%d\\n", list_total(&a));\n'
                "  return 0;\n"
                "}\n",
                encoding="utf-8",
            )
            (exercise / "solution" / "solution.c").write_text(
                '#include "custom_list.h"\n'
                "int list_total(t_node *node) {\n"
                "  int total = 0;\n"
                "  while (node) { total += node->value; node = node->next; }\n"
                "  return total;\n"
                "}\n",
                encoding="utf-8",
            )
            (workspace / "answer.c").write_text(
                '#include "custom_list.h"\n'
                "int list_total(t_node *node) {\n"
                "  return node->value + node->next->value;\n"
                "}\n",
                encoding="utf-8",
            )
            definition = _definition(
                execution=ExecutionDefinition(type=FUNCTION_CALL, fixture=PurePath("harness/main.c")),
                reference=ReferenceDefinition(source=PurePath("solution/solution.c"), harness=PurePath("harness/main.c")),
            )

            grader = GenericGrader(RuntimeRegistry([CRuntime(SystemCCompiler())]))
            result = grader.grade(
                GradingRequest(
                    definition=definition,
                    exercise_path=exercise,
                    workspace_path=workspace,
                    policy=GradingPolicy.training(),
                    seed=1,
                )
            )

        self.assertTrue(result.passed, result.trace_data.as_text())


if __name__ == "__main__":
    unittest.main()
