from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from exam_trainer.adapters.compiler.system_cpp_compiler import SystemCppCompiler
from exam_trainer.adapters.runtime.cpp_runtime import CppRuntime
from exam_trainer.adapters.runtime.java_runtime import JavaRuntime
from exam_trainer.ports.runtime_port import LanguageRuntime, ProgramSpec


class CppRuntimeAvailabilityTest(unittest.TestCase):
    def test_cpp_runtime_reports_availability_without_crashing(self) -> None:
        runtime = CppRuntime(SystemCppCompiler())

        self.assertIsInstance(runtime, LanguageRuntime)
        self.assertEqual(runtime.descriptor.language, "cpp")
        self.assertIn("program_output", runtime.descriptor.execution_types)
        self.assertIsInstance(runtime.check_available(), bool)


class JavaRuntimeTest(unittest.TestCase):
    def test_java_runtime_reports_jdk_availability_without_crashing(self) -> None:
        runtime = JavaRuntime()

        self.assertIsInstance(runtime, LanguageRuntime)
        self.assertEqual(runtime.descriptor.language, "java")
        self.assertIn("program_output", runtime.descriptor.execution_types)
        self.assertIsInstance(runtime.check_available(), bool)

    @unittest.skipUnless(JavaRuntime().check_available(), "no Java/JDK")
    def test_compiles_and_runs_main_class_without_shell(self) -> None:
        runtime = JavaRuntime()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Main.java"
            source.write_text(
                "public class Main {\n"
                "  public static void main(String[] args) {\n"
                "    for (String arg : args) System.out.print(arg + \"|\");\n"
                "  }\n"
                "}\n",
                encoding="utf-8",
            )
            program = runtime.prepare(ProgramSpec(main_source=source, entry="Main"), root / "build", "main")

            self.assertTrue(program.success, program.build.output)
            outcome = runtime.run(program, ("a b", "$(echo x)", ";ls"), "", 3)
            self.assertEqual(outcome.stdout, "a b|$(echo x)|;ls|")
            self.assertEqual(outcome.exit_code, 0)

    @unittest.skipUnless(JavaRuntime().check_available(), "no Java/JDK")
    def test_java_compile_error_is_preparation_failure(self) -> None:
        runtime = JavaRuntime()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Main.java"
            source.write_text("public class Main { nope }\n", encoding="utf-8")
            program = runtime.prepare(ProgramSpec(main_source=source, entry="Main"), root / "build", "main")

            self.assertFalse(program.success)
            self.assertIn("error", program.build.output.lower())


if __name__ == "__main__":
    unittest.main()
