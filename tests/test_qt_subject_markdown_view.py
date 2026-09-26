from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from exam_trainer.adapters.ui.qt.components.widgets import SubjectMarkdownView


class SubjectMarkdownViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _view(self, markdown: str) -> SubjectMarkdownView:
        view = SubjectMarkdownView()
        view.set_subject_markdown(markdown)
        return view

    def test_renders_headings_without_literal_markers(self) -> None:
        view = self._view("# Titulo\n\n## Subtitulo")

        text = view.toPlainText()

        self.assertIn("Titulo", text)
        self.assertIn("Subtitulo", text)
        self.assertNotIn("# Titulo", text)
        self.assertNotIn("## Subtitulo", text)

    def test_renders_inline_code_without_backticks(self) -> None:
        view = self._view("Use `argc_counter.c` e termine com `\\n`.")

        text = view.toPlainText()

        self.assertIn("argc_counter.c", text)
        self.assertIn("\\n", text)
        self.assertNotIn("`argc_counter.c`", text)

    def test_preserves_code_block_content(self) -> None:
        view = self._view("Saida:\n\n```text\n0\n1\n```")

        text = view.toPlainText()

        self.assertIn("Saida:", text)
        self.assertIn("0", text)
        self.assertIn("1", text)
        self.assertNotIn("```", text)

    def test_renders_lists_as_list_content(self) -> None:
        view = self._view("- primeiro\n- segundo")

        text = view.toPlainText()

        self.assertIn("primeiro", text)
        self.assertIn("segundo", text)
        self.assertNotIn("- primeiro", text)

    def test_preserves_utf8_accents(self) -> None:
        view = self._view("# Função\n\nImprima a quantidade de argumentos.")

        self.assertIn("Função", view.toPlainText())
        self.assertIn("quantidade", view.toPlainText())

    def test_malformed_markdown_does_not_crash(self) -> None:
        view = self._view("# Titulo\n\n`codigo sem fechar\n\n- item")

        self.assertIn("Titulo", view.toPlainText())
        self.assertIn("codigo sem fechar", view.toPlainText())

    def test_empty_subject_has_friendly_message(self) -> None:
        view = self._view(" \n\t")

        self.assertIn("Subject vazio.", view.toPlainText())

    def test_plain_text_still_appears_normally(self) -> None:
        view = self._view("Texto simples em pt-BR.\nSegunda linha.")

        text = view.toPlainText()

        self.assertIn("Texto simples em pt-BR.", text)
        self.assertIn("Segunda linha.", text)

    def test_raw_html_is_escaped_before_markdown_rendering(self) -> None:
        view = self._view("<script>alert(1)</script>\n\n<b>texto</b>")

        text = view.toPlainText()

        self.assertIn("<script>alert(1)</script>", text)
        self.assertIn("<b>texto</b>", text)

    def test_document_stylesheet_keeps_markdown_reading_spacing(self) -> None:
        view = self._view("Texto.\n\n## Secao\n\n```text\ncodigo\n```")

        stylesheet = view.document().defaultStyleSheet()

        self.assertIn("line-height: 1.58", stylesheet)
        self.assertIn("margin: 9px 0 13px 0", stylesheet)
        self.assertIn("background-color: #071307", stylesheet)
        self.assertIn("white-space: pre", stylesheet)
        self.assertIn("blockquote", stylesheet)

    def test_paragraphs_and_headings_receive_real_block_spacing(self) -> None:
        view = self._view("# Titulo\n\nDescricao.\n\n## Expected files\n\n`main.c`\n\n### Example")
        blocks = self._blocks_by_text(view)

        self.assertGreaterEqual(blocks["Titulo"].blockFormat().bottomMargin(), 14)
        self.assertGreaterEqual(blocks["Descricao."].blockFormat().bottomMargin(), 10)
        self.assertGreaterEqual(blocks["Expected files"].blockFormat().topMargin(), 20)
        self.assertGreaterEqual(blocks["Example"].blockFormat().topMargin(), 16)

    def test_inline_code_has_monospace_and_background(self) -> None:
        view = self._view("Use `reverse_bits.c` e `write`.")

        fragments = self._fragments_containing(view, "reverse_bits.c")

        self.assertTrue(fragments)
        self.assertTrue(any(fragment.charFormat().background().style() != Qt.BrushStyle.NoBrush for fragment in fragments))
        self.assertTrue(any("mono" in " ".join(fragment.charFormat().fontFamilies()).lower() for fragment in fragments))

    def test_fenced_code_block_preserves_ascii_art_and_gets_block_background(self) -> None:
        markdown = """Write a function.

```text
    1 byte
_____________
0010  0110
     ||
     \\/
0110  0100
```
"""
        view = self._view(markdown)
        text = view.toPlainText()
        blocks = self._blocks_by_text(view)

        self.assertIn("    1 byte", text)
        self.assertIn("0010  0110", text)
        self.assertIn("     ||", text)
        self.assertIn("     \\/", text)
        code_block = blocks["0010  0110"]
        self.assertTrue(code_block.blockFormat().nonBreakableLines())
        self.assertNotEqual(code_block.blockFormat().background().style(), Qt.BrushStyle.NoBrush)
        self.assertGreaterEqual(code_block.blockFormat().leftMargin(), 8)

    def test_lists_have_indentation_and_spacing(self) -> None:
        view = self._view("## Regras\n\n- primeiro\n- segundo")
        blocks = self._blocks_by_text(view)

        self.assertIsNotNone(blocks["primeiro"].textList())
        self.assertGreaterEqual(blocks["primeiro"].blockFormat().leftMargin(), 10)
        self.assertGreaterEqual(blocks["primeiro"].blockFormat().bottomMargin(), 6)

    def test_subject_without_headings_still_receives_paragraph_spacing(self) -> None:
        view = self._view("Primeiro paragrafo.\n\nSegundo paragrafo.")
        blocks = self._blocks_by_text(view)

        self.assertGreaterEqual(blocks["Primeiro paragrafo."].blockFormat().bottomMargin(), 10)
        self.assertGreaterEqual(blocks["Segundo paragrafo."].blockFormat().topMargin(), 6)

    @staticmethod
    def _blocks_by_text(view: SubjectMarkdownView):
        blocks = {}
        block = view.document().begin()
        while block.isValid():
            blocks[block.text()] = block
            block = block.next()
        return blocks

    @staticmethod
    def _fragments_containing(view: SubjectMarkdownView, needle: str):
        matches = []
        block = view.document().begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and needle in fragment.text():
                    matches.append(fragment)
                iterator += 1
            block = block.next()
        return matches


if __name__ == "__main__":
    unittest.main()
