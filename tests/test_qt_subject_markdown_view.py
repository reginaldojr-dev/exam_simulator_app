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

    def _rendered_html(self, markdown: str) -> str:
        """HTML produced by the Markdown stage alone (before Qt renders it)."""
        return SubjectMarkdownView._renderer.render(markdown)

    # --------------------------------------------------------------- basics
    def test_multiple_paragraphs_render_as_separate_paragraphs(self) -> None:
        view = self._view("Primeiro paragrafo.\n\nSegundo paragrafo.\n\nTerceiro paragrafo.")

        text = view.toPlainText()

        self.assertIn("Primeiro paragrafo.", text)
        self.assertIn("Segundo paragrafo.", text)
        self.assertIn("Terceiro paragrafo.", text)
        html = self._rendered_html("Primeiro paragrafo.\n\nSegundo paragrafo.")
        self.assertEqual(html.count("<p>"), 2)

    def test_renders_headings_without_literal_markers(self) -> None:
        view = self._view("# Titulo\n\n## Subtitulo\n\n### Detalhe")

        text = view.toPlainText()

        self.assertIn("Titulo", text)
        self.assertIn("Subtitulo", text)
        self.assertIn("Detalhe", text)
        self.assertNotIn("# Titulo", text)
        self.assertNotIn("## Subtitulo", text)
        self.assertNotIn("### Detalhe", text)

    def test_heading_levels_map_to_h1_h2_h3_tags(self) -> None:
        html = self._rendered_html("# Titulo\n\n## Subtitulo\n\n### Detalhe")

        self.assertIn("<h1>Titulo</h1>", html)
        self.assertIn("<h2>Subtitulo</h2>", html)
        self.assertIn("<h3>Detalhe</h3>", html)

    def test_renders_inline_code_without_backticks(self) -> None:
        view = self._view("Use `argc_counter.c` e termine com `\\n`.")

        text = view.toPlainText()

        self.assertIn("argc_counter.c", text)
        self.assertIn("\\n", text)
        self.assertNotIn("`argc_counter.c`", text)

    def test_inline_code_is_wrapped_in_code_tag(self) -> None:
        html = self._rendered_html("Use `reverse_bits.c`.")

        self.assertIn("<code>reverse_bits.c</code>", html)

    def test_renders_lists_as_list_content(self) -> None:
        view = self._view("## Regras\n\n- primeiro\n- segundo\n- `write`")

        text = view.toPlainText()

        self.assertIn("primeiro", text)
        self.assertIn("segundo", text)
        self.assertIn("write", text)
        self.assertNotIn("- primeiro", text)

    def test_unordered_list_renders_as_ul_li(self) -> None:
        html = self._rendered_html("- primeiro\n- segundo")

        self.assertIn("<ul>", html)
        self.assertEqual(html.count("<li>"), 2)

    def test_preserves_utf8_accents(self) -> None:
        view = self._view("# Função\n\nImprima a quantidade de argumentos, em português.")

        text = view.toPlainText()

        self.assertIn("Função", text)
        self.assertIn("português", text)

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

    # ----------------------------------------------------------------- code
    def test_preserves_code_block_content(self) -> None:
        view = self._view("Saida:\n\n```text\n0\n1\n```")

        text = view.toPlainText()

        self.assertIn("Saida:", text)
        self.assertIn("0", text)
        self.assertIn("1", text)
        self.assertNotIn("```", text)

    def test_fenced_code_block_is_a_single_pre_element(self) -> None:
        """Todo o bloco vira UM <pre>, nao uma faixa por linha."""
        markdown = "```text\nlinha 1\nlinha 2\nlinha 3\n```"

        html = self._rendered_html(markdown)

        self.assertEqual(html.count("<pre>"), 1)
        self.assertIn("linha 1", html)
        self.assertIn("linha 2", html)
        self.assertIn("linha 3", html)

    def test_fenced_shell_code_block_preserves_prompt_character(self) -> None:
        """Regressao: '$>' dentro de um code block nao pode virar '$&gt;'."""
        markdown = (
            "```shell\n"
            "$> ./camel_to_snake \"hereIsACamelCaseWord\"\n"
            "here_is_a_camel_case_word\n"
            "```"
        )
        view = self._view(markdown)

        text = view.toPlainText()

        self.assertIn('$> ./camel_to_snake "hereIsACamelCaseWord"', text)
        self.assertIn("here_is_a_camel_case_word", text)
        self.assertNotIn("&gt;", text)
        self.assertNotIn("&amp;", text)

    def test_fenced_code_block_with_angle_brackets_and_ampersand(self) -> None:
        """C real: 'if (a < b && c > d)' deve aparecer literal, nao escapado."""
        markdown = "```c\nif (a < b && c > d) {\n    return 1;\n}\n```"
        view = self._view(markdown)

        text = view.toPlainText()

        self.assertIn("if (a < b && c > d) {", text)
        self.assertNotIn("&lt;", text)
        self.assertNotIn("&gt;", text)
        self.assertNotIn("&amp;", text)

    def test_fenced_code_block_preserves_ascii_art(self) -> None:
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

        self.assertIn("    1 byte", text)
        self.assertIn("_____________", text)
        self.assertIn("0010  0110", text)
        self.assertIn("     ||", text)
        self.assertIn("     \\/", text)

    # -------------------------------------------------------------- security
    def test_raw_html_is_not_executed_and_stays_visible_as_text(self) -> None:
        view = self._view("<script>alert(1)</script>\n\n<b>texto</b>")

        text = view.toPlainText()

        self.assertIn("<script>alert(1)</script>", text)
        self.assertIn("<b>texto</b>", text)

    def test_raw_html_is_escaped_in_generated_markup(self) -> None:
        """A camada Markdown->HTML nunca deve emitir uma tag <script> ativa."""
        html = self._rendered_html("<script>alert(1)</script>")

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_view_is_read_only(self) -> None:
        view = self._view("Texto qualquer.")

        self.assertTrue(view.isReadOnly())

    def test_links_do_not_open_automatically(self) -> None:
        view = self._view("Texto qualquer.")

        self.assertFalse(view.openExternalLinks())
        self.assertFalse(view.openLinks())

    # -------------------------------------------------------------- selecao
    def test_text_can_be_selected(self) -> None:
        from PySide6.QtGui import QTextCursor

        view = self._view("Texto selecionavel para copiar.")

        cursor = view.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        view.setTextCursor(cursor)

        self.assertTrue(view.textCursor().hasSelection())
        self.assertIn("Texto selecionavel para copiar.", view.textCursor().selectedText())

    # -------------------------------------------------------------- estilos
    def test_document_stylesheet_keeps_markdown_reading_spacing(self) -> None:
        view = self._view("Texto.\n\n## Secao\n\n```text\ncodigo\n```")

        stylesheet = view.document().defaultStyleSheet()

        self.assertIn("line-height: 1.72", stylesheet)
        self.assertIn("margin: 12px 0 18px 0", stylesheet)
        self.assertIn("border-bottom: 1px solid #2f5f3b", stylesheet)
        self.assertIn("background-color: #071307", stylesheet)
        self.assertIn("white-space: pre", stylesheet)
        self.assertIn("blockquote", stylesheet)


if __name__ == "__main__":
    unittest.main()
