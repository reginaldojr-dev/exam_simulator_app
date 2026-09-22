from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout

from exam_trainer.adapters.ui.qt.components import widgets as ui
from exam_trainer.adapters.ui.qt.components.cursor import CursorController
from exam_trainer.adapters.ui.qt.theme import THEMES, ThemeManager, build_stylesheet, get_theme
from exam_trainer.adapters.ui.qt.theme.tokens import ThemeTokens

RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _rules(qss: str) -> list[tuple[str, str]]:
    return [(selector.strip(), body) for selector, body in RULE.findall(qss)]


class ThemeTokensTest(unittest.TestCase):
    def test_every_theme_defines_every_color_token(self) -> None:
        color_fields = [name for name, field in ThemeTokens.__dataclass_fields__.items() if field.type == "str" and name not in ("key", "name", "font_body", "font_title", "cursor_char")]
        for theme in THEMES.values():
            for name in color_fields:
                value = getattr(theme, name)
                self.assertRegex(value, r"^#[0-9a-fA-F]{6}$", f"{theme.key}.{name}")

    def test_accent_is_never_a_large_background(self) -> None:
        for theme in THEMES.values():
            for selector, body in _rules(build_stylesheet(theme)):
                if "QPushButton" in selector or "QHeaderView" in selector or "::item" in selector or "QFrame" in selector:
                    self.assertNotIn(f"background: {theme.accent.lower()}", body.lower(), f"{theme.key}: {selector}")
                    self.assertNotIn(f"background-color: {theme.accent.lower()}", body.lower(), f"{theme.key}: {selector}")

    def test_terminal_is_default_and_unknown_key_falls_back(self) -> None:
        self.assertEqual(get_theme(None).key, "terminal")
        self.assertEqual(get_theme("does-not-exist").key, "terminal")

    def test_terminal_keeps_spec_palette(self) -> None:
        terminal = THEMES["terminal"]
        self.assertEqual(terminal.background, "#0a0e0a")
        self.assertEqual(terminal.accent, "#39ff14")
        self.assertEqual(terminal.text_secondary, "#4a6b4a")
        self.assertEqual(terminal.success, "#50fa7b")
        self.assertEqual(terminal.fail, "#ff5555")
        self.assertEqual(terminal.warning, "#f1fa8c")
        self.assertEqual(terminal.hover_background, "#102010")


class ThemePersistenceTest(unittest.TestCase):
    def test_config_repository_round_trips_theme(self) -> None:
        import tempfile

        from exam_trainer.adapters.persistence.json_app_config_repository import JsonAppConfigRepository

        with tempfile.TemporaryDirectory() as temp_dir:
            repository = JsonAppConfigRepository(Path(temp_dir) / "config.json")
            self.assertIsNone(repository.load_theme())
            repository.save_theme("amber")
            self.assertEqual(JsonAppConfigRepository(Path(temp_dir) / "config.json").load_theme(), "amber")


class ThemeManagerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_set_theme_restyles_registered_widgets_and_emits(self) -> None:
        manager = ThemeManager("terminal")
        widget = QWidget()
        manager.apply(widget)
        received: list[str] = []
        manager.theme_changed.connect(lambda tokens: received.append(tokens.key))

        manager.set_theme("minimal")

        self.assertEqual(received, ["minimal"])
        self.assertIn(THEMES["minimal"].background, widget.styleSheet())
        self.assertEqual(manager.color("fail").name(), THEMES["minimal"].fail)


class CursorControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _page(self) -> tuple[QWidget, QLabel, list]:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel()
        layout.addWidget(title)
        buttons = [ui.button(f"> ITEM {index}", None, "menu") for index in range(3)]
        for button in buttons:
            layout.addWidget(button)
        return page, title, buttons

    def test_uses_a_single_timer(self) -> None:
        holder = QWidget()
        controller = CursorController(holder)
        timers = {id(timer) for timer in holder.findChildren(QTimer)}
        self.assertEqual(len(timers), 1)
        self.assertIs(controller.timer.parent(), controller)

    def test_only_one_item_blinks_besides_the_title(self) -> None:
        page, title, buttons = self._page()
        controller = CursorController(page)
        controller.configure(enabled=True, animations=False, cursor_char="_")
        controller.register_title(title, "TREINO")
        for button in buttons:
            controller.track(button)
        controller.set_idle_target(page, buttons[2])
        page.show()
        controller.enter_page(page)

        controller._focus = buttons[0]
        controller._on = True
        controller._render()

        lit = [button for button in buttons if button.text().endswith("_")]
        self.assertEqual(lit, [buttons[0]])
        self.assertEqual(title.text(), "TREINO _")

        controller._focus = None
        controller._render()
        lit = [button for button in buttons if button.text().endswith("_")]
        self.assertEqual(lit, [buttons[2]])

    def test_disabled_cursor_shows_static_texts(self) -> None:
        page, title, buttons = self._page()
        controller = CursorController(page)
        controller.configure(enabled=False, animations=False, cursor_char="_")
        controller.register_title(title, "HISTÓRICO")
        controller.set_idle_target(page, buttons[0])
        page.show()
        controller.enter_page(page)

        self.assertEqual(title.text(), "HISTÓRICO")
        self.assertEqual(buttons[0].text(), "> ITEM 0")


class OptionButtonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_check_and_radio_markers(self) -> None:
        check = ui.OptionButton("level0", kind="check", checked=True)
        radio = ui.OptionButton("Todos", kind="radio")
        self.assertEqual(check.text(), "[x] level0")
        self.assertEqual(radio.text(), "( ) Todos")
        check.setChecked(False)
        radio.setChecked(True)
        self.assertEqual(check.text(), "[ ] level0")
        self.assertEqual(radio.text(), "(•) Todos")
        self.assertEqual(check.value, "level0")


if __name__ == "__main__":
    unittest.main()
