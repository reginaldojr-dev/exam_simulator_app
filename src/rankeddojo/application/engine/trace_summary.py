"""Builds the "trace resumido" (summarized trace) shown right after a FAIL,
from the same `GradingResult` the grader already produced -- never from a
second execution and never by re-grading anything.

Design note (Fase "exercise-feedback-ui"): `GradingResult.test_results`
already carries structured per-test data (expected/received/stderr/exit
code/timeout), so the test-failure summary below reuses it directly, with
no text parsing at all. The one exception is the compiler command line:
`GradingResult` never keeps the `CompilationResult.command` tuple that
`GenericGrader` had in hand while compiling (only the raw compiler output
survives as `compile_output`), so `_parse_compile_command` recovers it from
the trace's own "Command: ..." line instead. That line is text this
application generates itself (see `TraceBuilder.add_compilation`), never
pack-authored content, so a plain whitespace split is safe and
deterministic -- this is intentionally the smallest parser that gets the
job done, not a general shell-command parser.
"""

from __future__ import annotations

from dataclasses import dataclass

from rankeddojo.domain.grading import GradingOutcome, GradingResult


@dataclass(frozen=True)
class CompilationSummary:
    """A compiler invocation, broken into fields for quick diagnosis."""

    compiler: str = ""
    flags: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    output_path: str = ""
    raw_command: str = ""


@dataclass(frozen=True)
class TestFailureSummary:
    """The first failing test, with only what's useful for a quick look."""

    index: int
    expected: str
    received: str
    stderr: str
    exit_code: int | None
    timed_out: bool


@dataclass(frozen=True)
class TraceSummary:
    """The "trace resumido" for a failed/content-error grading result.

    `stage` is a stable identifier -- "compilation" | "test" | "content_error"
    -- never a translated string; the UI layer decides how to label each one
    in the active locale. Exactly one of `compilation`/`test_failure` is set,
    matching `stage` ("content_error" sets neither -- `message` alone is
    enough there, mirroring how `GenericGrader._content_error` already works).
    """

    stage: str
    message: str = ""
    compilation: CompilationSummary | None = None
    test_failure: TestFailureSummary | None = None


_SOURCE_EXTENSIONS = (".c", ".cpp", ".cc", ".cxx", ".java", ".py")
_COMMAND_PREFIX = "Command: "


def _parse_compile_command(trace_lines: tuple[str, ...]) -> CompilationSummary:
    command_line = ""
    for line in trace_lines:
        if line.startswith(_COMMAND_PREFIX):
            command_line = line[len(_COMMAND_PREFIX) :]
            break
    if not command_line or command_line == "(not executed)":
        return CompilationSummary(raw_command=command_line)

    tokens = command_line.split()
    compiler = tokens[0] if tokens else ""
    flags: list[str] = []
    sources: list[str] = []
    output_path = ""
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "-o" and index + 1 < len(tokens):
            output_path = tokens[index + 1]
            index += 2
            continue
        if token.startswith("-"):
            flags.append(token)
        elif token.lower().endswith(_SOURCE_EXTENSIONS):
            sources.append(token)
        index += 1
    return CompilationSummary(
        compiler=compiler,
        flags=tuple(flags),
        sources=tuple(sources),
        output_path=output_path,
        raw_command=command_line,
    )


def build_trace_summary(result: GradingResult) -> TraceSummary | None:
    """Returns `None` for a passed result -- there is nothing to summarize."""

    if result.outcome is GradingOutcome.PASSED:
        return None
    if result.outcome is GradingOutcome.CONTENT_ERROR:
        return TraceSummary(stage="content_error", message=result.compile_output)
    if not result.test_results:
        # USER_FAILED with no test even attempted: the submission itself
        # failed to compile (see `GenericGrader.grade`).
        return TraceSummary(
            stage="compilation",
            message=result.compile_output,
            compilation=_parse_compile_command(result.trace_data.lines),
        )
    for index, test_result in enumerate(result.test_results, start=1):
        if test_result.passed:
            continue
        return TraceSummary(
            stage="test",
            message=str(index),
            test_failure=TestFailureSummary(
                index=index,
                expected=test_result.test_case.expected,
                received=test_result.stdout,
                stderr=test_result.stderr,
                exit_code=test_result.exit_code,
                timed_out=test_result.timed_out,
            ),
        )
    return None
