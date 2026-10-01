"""Subject screen presentation helpers: legacy sidebar extraction fallback,
and generic body-section promotion/demotion.

Two separate jobs live here:

1. LEGACY COMPATIBILITY FALLBACK (`extract_list_section`) -- best-effort
   extraction of a pack's own subject Markdown heading text, for sidebar
   blocks that have no structured metadata to read. This is no longer the
   primary source for those blocks: new/official packs declare them as
   structured, declarative metadata on the exercise definition itself
   (`ExerciseDefinition.usage`/`submission`, see
   `domain.activity_definition.UsageConstraints` and
   `docs/subject-content-contract.md`). `MainWindow._refresh_exercise_frame`
   reads structured metadata first and only calls into this module when the
   corresponding structured field is empty, i.e. for content written before
   the structured contract existed. Its scope is intentionally frozen: do
   not add more heading phrasings or smarter matching here -- the direction
   for new content is the structured contract, not a more capable parser.

2. BODY NORMALIZATION (`strip_sections`, `demote_examples_heading`) -- once
   `MainWindow` has decided WHAT is actually being shown in the sidebar
   (whether from structured metadata or from #1's fallback), these two
   functions let it remove the now-redundant copy from the subject body, and
   tone down the generic "Example(s)" grouping heading. Both operate purely
   on heading text -- same `_HEADING_RE`/`_normalize_heading` machinery as
   #1 -- and never judge or rewrite the content under a heading; the caller
   decides, per exercise, which headings (if any) are safe to touch. This
   keeps the rule general: there is no special-cased "if heading == Expected
   files" branch anywhere -- see `MainWindow._exercise_body_markdown` for
   the one generic, data-driven loop that uses these.

This module is presentation-only, kept isolated from `MainWindow` the same
way trace parsing is (see `application.engine.trace_summary`), and never
guesses or fabricates content.
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
EXPECTED_FILE_HEADINGS = (
    "arquivo esperado",
    "arquivos esperados",
    "expected file",
    "expected files",
)
CONSTRAINTS_HEADINGS = (
    "regras",
    "restrições",
    "restricoes",
    "constraints",
    "rules",
)
EXAMPLES_HEADINGS = (
    "exemplo",
    "exemplos",
    "example",
    "examples",
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


def strip_sections(markdown: str, heading_variants: tuple[str, ...]) -> str:
    """Removes every section (the matching heading line, and everything
    under it until the next heading or end of document) whose heading text
    matches one of `heading_variants`.

    Used to drop a subject.md section from the main body once its content
    has already been promoted to the sidebar -- the caller
    (`MainWindow._exercise_body_markdown`) only passes heading variants it
    has already confirmed are being shown there, structured or legacy; this
    function itself never judges the section's content, only its heading
    text, and content under a non-matching heading is always left untouched.
    """
    kept: list[str] = []
    skipping = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            skipping = _normalize_heading(heading_match.group(1)) in heading_variants
            if skipping:
                continue
        if skipping:
            continue
        kept.append(raw_line)
    result = "\n".join(kept)
    if markdown.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result


def demote_examples_heading(markdown: str) -> str:
    """Rewrites the single generic "Example(s)"/"Exemplo(s)" grouping
    heading (if present) down to a muted h6 (see `SubjectMarkdownView`'s
    dedicated, muted `h6` rule), so it stops visually outweighing the
    exercise's actual instructions.

    Deliberately narrow: it matches only the bare group label
    (`EXAMPLES_HEADINGS`, exact normalized text), never "Example 1"/"Example
    2"-style sub-headings -- those stay at their original level and remain
    fully legible, since per the subject content contract they already
    provide enough structure on their own. Only the first match is touched;
    a subject.md has at most one such grouping heading in practice.
    """
    lines = markdown.splitlines()
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        heading_match = _HEADING_RE.match(line)
        if heading_match and _normalize_heading(heading_match.group(1)) in EXAMPLES_HEADINGS:
            lines[index] = f"###### {heading_match.group(1).strip()}"
            break
    result = "\n".join(lines)
    if markdown.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result
