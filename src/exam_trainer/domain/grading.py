from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class TestCase:
    args: tuple[str, ...] = ()
    stdin: str = ""
    expected: str = ""
    seed: int | None = None


@dataclass(frozen=True)
class TestResult:
    test_case: TestCase
    passed: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class TraceData:
    lines: tuple[str, ...] = ()

    def as_text(self) -> str:
        return "\n".join(self.lines)


@dataclass(frozen=True)
class GradingResult:
    passed: bool
    compile_output: str = ""
    test_results: tuple[TestResult, ...] = ()
    stderr: str = ""
    seed: int | None = None
    trace_data: TraceData = field(default_factory=TraceData)


class GradingMode(str, Enum):
    TRAINING = "training"
    EXAM = "exam"


@dataclass(frozen=True)
class GradingPolicy:
    mode: GradingMode
    fail_fast: bool

    @classmethod
    def training(cls) -> "GradingPolicy":
        return cls(mode=GradingMode.TRAINING, fail_fast=False)

    @classmethod
    def exam(cls) -> "GradingPolicy":
        return cls(mode=GradingMode.EXAM, fail_fast=True)
