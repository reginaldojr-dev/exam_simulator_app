from __future__ import annotations

from exam_trainer.adapters.compiler.system_native_compiler import SystemNativeCompiler


class SystemCppCompiler(SystemNativeCompiler):
    def __init__(self, manual_compiler: str | None = None) -> None:
        super().__init__(
            language_name="C++",
            candidates=("c++", "clang++", "g++"),
            flags=("-Wall", "-Wextra", "-Werror", "-std=c++17"),
            manual_compiler=manual_compiler,
            probe_filename="probe.cpp",
            probe_source=(
                "#include <iostream>\n"
                "int main() {\n"
                "    std::cout << \"OK\\n\";\n"
                "    return 0;\n"
                "}\n"
            ),
        )
