"""Best-effort extraction of a couple of informational sections ("allowed" /
"not allowed" functions) from a pack's own subject Markdown, so the exercise
sidebar can surface them as short tags instead of leaving them buried inside
the long-form subject text.

This is presentation only, kept isolated from `MainWindow` the same way
trace parsing is (see `application.engine.trace_summary`): a pack's
subject.md is still the single source of truth, no pack schema or contract
field is introduced, and nothing here is required for correctness. A pack
whose subject.md uses none of the known heading phrasings below simply
doesn't get that sidebar block -- the caller hides it when the result is
empty; this module never guesses or fabricates content.

The "expected file" shown in the sidebar does NOT come from here -- it comes
straight from `ExerciseDefinition.submission.filename`, which is real
structured metadata. Parsing is only needed for "allowed"/"not allowed",
which have no structured field.
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
    """The bullet items right under the first heading whose text matches one
    of `heading_variants` (case-insensitive). Empty tuple when no such
    heading exists, or it isn't followed by a list -- the caller hides the
    sidebar block in that case rather than showing something empty/wrong.
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
