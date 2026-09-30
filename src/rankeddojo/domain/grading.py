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


class GradingOutcome(str, Enum):
    """What a grading run actually determined, independent of any UI text.

    - `PASSED`: the submission satisfied the exercise.
    - `USER_FAILED`: the submission itself is wrong (didn't compile, crashed,
      timed out, or its output diverged) -- a normal, expected outcome of
      grading someone's code.
    - `CONTENT_ERROR`: grading could not reach a trustworthy verdict on the
      submission because the exercise's own content/reference is broken
      (reference failed to compile/prepare, crashed, timed out, or the
      execution plan/harness declaration itself is invalid). This is never
      the user's fault and must never be treated like `USER_FAILED` by any
      consumer (history, exam progression, scoring).

    `RUNTIME_UNAVAILABLE` is deliberately not a member here: today the UI
    always runs `preflight_runtime`/`preflight_exam` before a submission can
    reach the grader (see `main_window._runtime_checked`), so a missing
    compiler/interpreter is resolved before `GenericGrader.grade()` is ever
    called. Modeling it here would be speculative scope for this phase.
    """

    PASSED = "passed"
    USER_FAILED = "user_failed"
    CONTENT_ERROR = "content_error"


@dataclass(frozen=True)
class GradingResult:
    """`outcome` is the single source of truth for what happened.

    `passed` is kept as a derived, read-only property (not a stored field)
    so the two can never disagree -- there is no way to construct a
    `GradingResult` with `passed=True` and `outcome=USER_FAILED` at the same
    time, because `passed` is not something callers set anymore.
    """

    outcome: GradingOutcome
    compile_output: str = ""
    test_results: tuple[TestResult, ...] = ()
    stderr: str = ""
    seed: int | None = None
    trace_data: TraceData = field(default_factory=TraceData)

    @property
    def passed(self) -> bool:
        return self.outcome is GradingOutcome.PASSED


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
