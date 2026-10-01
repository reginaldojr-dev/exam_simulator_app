"""Compatibility: the old C grader is now GenericGrader with a CRuntime."""

from __future__ import annotations

from rankeddojo.adapters.grader.generic_grader import GenericGrader
from rankeddojo.adapters.runtime.c_runtime import CRuntime
from rankeddojo.application.engine.expectations import ExpectationRegistry
from rankeddojo.application.engine.generators import TestCaseGeneratorRegistry
from rankeddojo.application.engine.runtime_registry import RuntimeRegistry
from rankeddojo.ports.compiler_port import CompilerPort


class GenericCGrader(GenericGrader):
    def __init__(
        self,
        compiler: CompilerPort,
        generator_registry: TestCaseGeneratorRegistry | None = None,
        expectation_registry: ExpectationRegistry | None = None,
    ) -> None:
        super().__init__(
            RuntimeRegistry([CRuntime(compiler)]),
            generator_registry=generator_registry,
            expectation_registry=expectation_registry,
        )
