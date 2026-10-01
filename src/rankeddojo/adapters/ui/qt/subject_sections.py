"""LEGACY COMPATIBILITY FALLBACK -- best-effort extraction of "allowed" /
"not allowed" sections from a pack's own subject Markdown heading text.

This is no longer the primary source for that sidebar block. New/official
packs declare `allowed`/`forbidden` as structured, declarative metadata on
the exercise definition itself (`ExerciseDefinition.usage`, see
`domain.activity_definition.UsageConstraints` and
`docs/subject-content-contract.md`) -- the UI reads that first
(`MainWindow._refresh_exercise_frame`) and only calls into this module when
`usage.allowed`/`usage.forbidden` is empty, i.e. for content written before
the structured contract existed.

This module exists purely so those older packs keep working: it is
presentation-only, kept isolated from `MainWindow` the same way trace
parsing is (see `application.engine.trace_summary`), and it never guesses or
fabricates content -- a pack whose subject.md uses none of the known heading
phrasings below simply doesn't get that sidebar block from this path (it
may still get it from structured `usage`). Its scope is intentionally
frozen: do not add more heading phrasings or smarter matching here -- the
direction for new content is the structured contract, not a more capable
parser.

The "expected file" shown in the sidebar does NOT come from here -- it comes
straight from `ExerciseDefinition.submission.filename`, which is real
structured metadata, same as `usage` above.
"""

from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
_LIST_ITEM_RE = re.compile(r"^[-*]\s+(.*)$")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")

ALLOWED_HEADINGS = (
    "permitido",
    "permitidas",
    "allowed",
    "allowed functions",
    "funções permitidas",
    "funcoes permitidas",
)
NOT_ALLOWED_HEADINGS = (
    "não permitido",
    "nao permitido",
    "não permitidas",
    "nao permitidas",
    "not allowed",
    "forbidden",
    "forbidden functions",
    "proibido",
    "proibidas",
)


def _normalize_heading(text: str) -> str:
    return text.strip().strip(":").lower()


def extract_list_section(markdown: str, heading_variants: tuple[str, ...]) -> tuple[str, ...]:
    """Legacy fallback only -- see the module docstring. The bullet items
    right under the first heading whose text matches one of
    `heading_variants` (case-insensitive). Empty tuple when no such heading
    exists, or it isn't followed by a list -- the caller hides the sidebar
    block in that case rather than showing something empty/wrong.
    """
    collecting = False
    items: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            if collecting:
                break  # a new heading closes the section we were reading
            if _normalize_heading(heading_match.group(1)) in heading_variants:
                collecting = True
            continue
        if not collecting:
            continue
        if not line:
            continue
        item_match = _LIST_ITEM_RE.match(line)
        if not item_match:
            break  # non-list content closes the section
        items.append(_INLINE_CODE_RE.sub(r"\1", item_match.group(1)).strip())
    return tuple(items)
