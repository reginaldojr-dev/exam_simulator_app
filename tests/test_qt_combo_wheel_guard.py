from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QComboBox, QWidget

from exam_trainer.adapters.ui.qt.components.combo_wheel_guard import (
    ComboBoxWheelGuard,
    install_combo_box_wheel_guard,
)


def _wheel_event() -> QWheelEvent:
    return QWheelEvent(
        QPointF(0, 0),
        QPointF(0, 0),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


class _RecordingWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.received_types: list[QEvent.Type] = []

    def event(self, event: QEvent) -> bool:  # noqa: N802 - Qt API
        self.received_types.append(event.type())
        return super().event(event)


class ComboBoxWheelGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_unfocused_combo_box_wheel_is_swallowed(self) -> None:
        guard = ComboBoxWheelGuard()
        parent = _RecordingWidget()
        combo = QComboBox(parent)

        handled = guard.eventFilter(combo, _wheel_event())

        self.assertTrue(handled)

    def test_unfocused_combo_box_wheel_is_forwarded_to_parent(self) -> None:
        # Swallowing the event on the combo must not block page/area
        # scrolling: the same wheel event is forwarded to the parent widget.
        guard = ComboBoxWheelGuard()
        parent = _RecordingWidget()
        combo = QComboBox(parent)

        guard.eventFilter(combo, _wheel_event())

        self.assertIn(QEvent.Type.Wheel, parent.received_types)

    def test_focused_combo_box_wheel_is_not_intercepted(self) -> None:
        # A combo box that already has keyboard focus keeps Qt's normal
        # wheel behavior -- the filter must not touch it.
        guard = ComboBoxWheelGuard()
        parent = _RecordingWidget()
        combo = QComboBox(parent)
        combo.hasFocus = lambda: True  # type: ignore[method-assign]
        # QComboBox(parent) itself sends parent a QEvent.ChildAdded before
        # the guard is ever involved; clear that out so the assertion below
        # only reflects events caused by the guard's own eventFilter call.
        parent.received_types.clear()

        handled = guard.eventFilter(combo, _wheel_event())

        self.assertFalse(handled)
        self.assertEqual(parent.received_types, [])

    def test_non_combo_box_widget_is_ignored(self) -> None:
        guard = ComboBoxWheelGuard()
        widget = QWidget()

        handled = guard.eventFilter(widget, _wheel_event())

        self.assertFalse(handled)

    def test_non_wheel_event_is_ignored(self) -> None:
        guard = ComboBoxWheelGuard()
        parent = _RecordingWidget()
        combo = QComboBox(parent)

        handled = guard.eventFilter(combo, QEvent(QEvent.Type.EnabledChange))

        self.assertFalse(handled)

    def test_install_creates_a_guard_installed_on_the_application(self) -> None:
        guard = install_combo_box_wheel_guard(self._app)
        self.assertIsInstance(guard, ComboBoxWheelGuard)
        self.assertIs(guard.parent(), self._app)


if __name__ == "__main__":
    unittest.main()
