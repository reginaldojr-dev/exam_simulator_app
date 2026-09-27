"""Attempt modes and progress key (ADR 0003)."""

from __future__ import annotations

TRAINING_MODE = "training"
EXAM_MODE = "exam"
ATTEMPT_MODES = (TRAINING_MODE, EXAM_MODE)

# pack_id for old attempts whose pack cannot be identified with certainty.
# Starts with "_", so it never collides with a valid pack id; see domain.identifiers.
LEGACY_PACK_ID = "_legacy"
