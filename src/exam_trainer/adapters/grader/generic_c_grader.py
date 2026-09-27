"""Compatibility: the old C grader is now GenericGrader with a CRuntime."""

from __future__ import annotations

from exam_trainer.adapters.grader.generic_grader import GenericGrader
from exam_trainer.adapters.runtime.c_runtime import CRuntime
from exam_trainer.application.engine.expectations import ExpectationRegistry
from exam_trainer.application.engine.generators import TestCaseGeneratorRegistry
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry
from exam_trainer.ports.compiler_port import CompilerPort


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
