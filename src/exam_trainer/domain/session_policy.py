from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from exam_trainer.domain.grading import GradingPolicy

TRAINING_POLICY_ID = "training"
EXAM_POLICY_ID = "exam"


class SessionPolicy(Protocol):
    id: str
    can_switch_activity: bool
    advances_on_pass: bool
    stays_on_fail: bool
    has_deadline: bool
    workspace_scope_kind: str

    def grading_policy(self) -> GradingPolicy:
        raise NotImplementedError


@dataclass(frozen=True)
class TrainingPolicy:
    id: str = TRAINING_POLICY_ID
    can_switch_activity: bool = True
    advances_on_pass: bool = False
    stays_on_fail: bool = False
    has_deadline: bool = False
    workspace_scope_kind: str = TRAINING_POLICY_ID

    def grading_policy(self) -> GradingPolicy:
        return GradingPolicy.training()


@dataclass(frozen=True)
class ExamPolicy:
    id: str = EXAM_POLICY_ID
    can_switch_activity: bool = False
    advances_on_pass: bool = True
    stays_on_fail: bool = True
    has_deadline: bool = True
    workspace_scope_kind: str = "exams"

    def grading_policy(self) -> GradingPolicy:
        return GradingPolicy.exam()


class SessionPolicyRegistry:
    def __init__(self, policies: tuple[SessionPolicy, ...] | None = None) -> None:
        registered = policies or (TrainingPolicy(), ExamPolicy())
        self._policies = {policy.id: policy for policy in registered}

    def get(self, policy_id: str) -> SessionPolicy:
        try:
            return self._policies[policy_id]
        except KeyError as error:
            raise ValueError(f"Unknown session policy: {policy_id!r}") from error

    def register(self, policy: SessionPolicy) -> None:
        self._policies[policy.id] = policy

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._policies))
