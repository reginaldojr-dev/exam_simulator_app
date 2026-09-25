from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

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


if __name__ == "__main__":
    unittest.main()
