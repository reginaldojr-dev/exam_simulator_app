"""Modos de tentativa e chave de progresso (ADR 0003)."""

from __future__ import annotations

TRAINING_MODE = "training"
EXAM_MODE = "exam"
ATTEMPT_MODES = (TRAINING_MODE, EXAM_MODE)

# pack_id das tentativas antigas cujo pack não dá para descobrir com certeza.
# Começa com "_", então nunca colide com um id de pack válido (ver domain.identifiers).
LEGACY_PACK_ID = "_legacy"
