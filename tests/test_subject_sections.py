"""Pure-logic coverage for `subject_sections.py`'s body-normalization helpers
(`strip_sections`, `demote_examples_heading`) and the pre-existing legacy
sidebar fallback (`extract_list_section`).

These three functions never read UI locale, never import Qt, and judge only
heading text -- never section content. `MainWindow` is the one piece that
decides, per exercise and per field of the structured `UsageConstraints`
contract, which heading variants are safe to pass in; see
`test_qt_main_window.py` for that integration-level coverage.
"""

from __future__ import annotations

import unittest

from rankeddojo.adapters.ui.qt.subject_sections import (
    ALLOWED_HEADINGS,
    EXAMPLES_HEADINGS,
    NOT_ALLOWED_HEADINGS,
    demote_examples_heading,
    extract_list_section,
    strip_sections,
)


class StripSectionsTest(unittest.TestCase):
    def test_removes_matching_section_and_its_content(self) -> None:
        markdown = (
            "Enunciado.\n"
            "\n"
            "## Permitido\n"
            "- `write`\n"
            "\n"
            "## Comportamento esperado\n"
            "- Faça X.\n"
        )
        result = strip_sections(markdown, ALLOWED_HEADINGS)
        self.assertNotIn("Permitido", result)
        self.assertNotIn("write", result)
        self.assertIn("Comportamento esperado", result)
        self.assertIn("Faça X.", result)

    def test_preserves_other_sections_in_original_order(self) -> None:
        markdown = "## Permitido\n- a\n\n## Não permitido\n- b\n\n## Exemplos\n- c\n"
        result = strip_sections(markdown, ALLOWED_HEADINGS)
        not_allowed_index = result.index("Não permitido")
        examples_index = result.index("Exemplos")
        self.assertNotIn("Permitido\n", result.split("Não permitido")[0])
        self.assertLess(not_allowed_index, examples_index)

    def test_is_noop_when_heading_absent(self) -> None:
        markdown = "Enunciado.\n\n## Comportamento esperado\n- Faça X.\n"
        self.assertEqual(strip_sections(markdown, ALLOWED_HEADINGS), markdown)

    def test_matches_heading_variant_case_insensitively_with_trailing_colon(self) -> None:
        markdown = "## PERMITIDO:\n- `write`\n\n## Exemplos\n- ok\n"
        result = strip_sections(markdown, ALLOWED_HEADINGS)
        self.assertNotIn("PERMITIDO", result)
        self.assertIn("Exemplos", result)

    def test_preserves_trailing_newline_presence(self) -> None:
        markdown = "## Comportamento esperado\n- Faça X.\n"
        result = strip_sections(markdown, ALLOWED_HEADINGS)
        self.assertTrue(result.endswith("\n"))

    def test_preserves_missing_trailing_newline(self) -> None:
        markdown = "## Comportamento esperado\n- Faça X."
        result = strip_sections(markdown, ALLOWED_HEADINGS)
        self.assertFalse(result.endswith("\n"))

    def test_never_touches_content_under_a_non_matching_heading(self) -> None:
        # Guard against a parser that judges content instead of heading
        # text: a bullet that happens to read "Permitido" under an
        # unrelated heading must survive untouched.
        markdown = "## Observações\n- Uso de `Permitido` como identificador é só um exemplo.\n"
        result = strip_sections(markdown, ALLOWED_HEADINGS)
        self.assertEqual(result, markdown)

    def test_removing_multiple_heading_groups_in_one_pass(self) -> None:
        markdown = "## Permitido\n- a\n\n## Não permitido\n- b\n\n## Exemplos\n- c\n"
        result = strip_sections(strip_sections(markdown, ALLOWED_HEADINGS), NOT_ALLOWED_HEADINGS)
        self.assertNotIn("Permitido", result)
        self.assertNotIn("permitido", result)
        self.assertIn("Exemplos", result)


class DemoteExamplesHeadingTest(unittest.TestCase):
    def test_rewrites_generic_heading_to_h6(self) -> None:
        markdown = "## Exemplos\n\nEntrada: `1`\n"
        result = demote_examples_heading(markdown)
        lines = result.splitlines()
        self.assertIn("###### Exemplos", lines)
        self.assertNotIn("## Exemplos", lines)

    def test_leaves_numbered_example_subheadings_untouched(self) -> None:
        markdown = "## Exemplos\n\n### Example 1\n\nfoo\n\n### Example 2\n\nbar\n"
        result = demote_examples_heading(markdown)
        lines = result.splitlines()
        self.assertIn("###### Exemplos", lines)
        self.assertIn("### Example 1", lines)
        self.assertIn("### Example 2", lines)

    def test_is_noop_without_a_generic_examples_heading(self) -> None:
        markdown = "### Example 1\n\nfoo\n"
        self.assertEqual(demote_examples_heading(markdown), markdown)

    def test_only_the_first_generic_heading_is_touched(self) -> None:
        # A subject.md has at most one grouping heading in practice; this
        # just documents that the function does not keep rewriting past
        # the first match.
        markdown = "## Exemplos\n\nfoo\n\n## Exemplos\n\nbar\n"
        result = demote_examples_heading(markdown)
        lines = result.splitlines()
        self.assertEqual(lines.count("###### Exemplos"), 1)
        self.assertEqual(lines.count("## Exemplos"), 1)

    def test_preserves_heading_text_exactly(self) -> None:
        markdown = "## Examples\n\nfoo\n"
        result = demote_examples_heading(markdown)
        self.assertIn("###### Examples", result.splitlines())

    def test_all_examples_headings_variants_are_recognized(self) -> None:
        for variant in EXAMPLES_HEADINGS:
            markdown = f"## {variant}\n\nfoo\n"
            result = demote_examples_heading(markdown)
            self.assertTrue(result.startswith("######"), variant)


class ExtractListSectionTest(unittest.TestCase):
    def test_returns_items_under_matching_heading(self) -> None:
        markdown = "## Permitido\n- `write`\n- `read`\n"
        self.assertEqual(extract_list_section(markdown, ALLOWED_HEADINGS), ("write", "read"))

    def test_empty_without_a_matching_heading(self) -> None:
        markdown = "## Comportamento esperado\n- Faça X.\n"
        self.assertEqual(extract_list_section(markdown, ALLOWED_HEADINGS), ())

    def test_stops_at_non_list_content(self) -> None:
        markdown = "## Permitido\n- `write`\n\nTexto solto.\n- `read`\n"
        self.assertEqual(extract_list_section(markdown, ALLOWED_HEADINGS), ("write",))

    def test_empty_when_heading_has_no_list_beneath_it(self) -> None:
        markdown = "## Permitido\n\nTexto solto, sem lista.\n"
        self.assertEqual(extract_list_section(markdown, ALLOWED_HEADINGS), ())


if __name__ == "__main__":
    unittest.main()
