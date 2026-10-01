"""Domain-level guarantees for GradingOutcome / GradingResult.passed.

These tests exist purely at the domain level (no grader, no coordinator): they
prove that `passed` is a strict, structurally-guaranteed function of
`outcome`, and that there is no way to construct a `GradingResult` with an
`outcome`/`passed` pair that disagrees with each other.
"""

from __future__ import annotations

import unittest

from rankeddojo.domain.grading import GradingOutcome, GradingResult, TraceData


class GradingOutcomePassedConsistencyTest(unittest.TestCase):
    def test_passed_outcome_implies_passed_true(self) -> None:
        result = GradingResult(outcome=GradingOutcome.PASSED)
        self.assertTrue(result.passed)

    def test_user_failed_outcome_implies_passed_false(self) -> None:
        result = GradingResult(outcome=GradingOutcome.USER_FAILED)
        self.assertFalse(result.passed)

    def test_content_error_outcome_implies_passed_false(self) -> None:
        result = GradingResult(outcome=GradingOutcome.CONTENT_ERROR)
        self.assertFalse(result.passed)

    def test_passed_is_not_a_constructor_argument(self) -> None:
        # `passed` is a derived, read-only property -- there is no stored
        # field for it, so it is structurally impossible to pass a `passed=`
        # value that disagrees with `outcome` (or at all).
        with self.assertRaises(TypeError):
            GradingResult(outcome=GradingOutcome.PASSED, passed=False)  # type: ignore[call-arg]

    def test_passed_property_cannot_be_reassigned(self) -> None:
        result = GradingResult(outcome=GradingOutcome.USER_FAILED)
        with self.assertRaises(AttributeError):
            result.passed = True  # type: ignore[misc]

    def test_outcome_is_frozen(self) -> None:
        result = GradingResult(outcome=GradingOutcome.PASSED)
        with self.assertRaises(AttributeError):
            result.outcome = GradingOutcome.CONTENT_ERROR  # type: ignore[misc]

    def test_exactly_three_outcome_members(self) -> None:
        # RUNTIME_UNAVAILABLE is deliberately excluded (see GradingOutcome's
        # own docstring) -- this test pins that decision so it doesn't drift
        # silently.
        self.assertEqual(
            {member.value for member in GradingOutcome},
            {"passed", "user_failed", "content_error"},
        )

    def test_trace_data_defaults_to_empty(self) -> None:
        result = GradingResult(outcome=GradingOutcome.PASSED)
        self.assertEqual(result.trace_data, TraceData())


if __name__ == "__main__":
    unittest.main()
