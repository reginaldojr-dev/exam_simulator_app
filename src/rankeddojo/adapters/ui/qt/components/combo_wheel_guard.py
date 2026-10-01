"""Global protection against accidental QComboBox changes from mouse wheel scrolling.

Qt's QComboBox reacts to the wheel whenever the cursor hovers over it, regardless
of keyboard focus -- so scrolling a settings page can silently change a value
(e.g. the interface language) the user never meant to touch. Installing this
filter once on the QApplication fixes it everywhere, without editing every
QComboBox instantiation or duplicating logic per screen.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QComboBox, QWidget


class ComboBoxWheelGuard(QObject):
    """Event filter: ignores wheel events over an unfocused QComboBox.

    Install on the QApplication instance so it applies to every QComboBox in
    the app. A combo box that already has keyboard focus keeps Qt's normal
    wheel behavior. An unfocused one never changes value from a wheel event;
    the event is forwarded to its parent widget instead, so page/area
    scrolling keeps working.
    """

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel and isinstance(watched, QComboBox) and not watched.hasFocus():
            parent = watched.parentWidget()
            if isinstance(parent, QWidget):
                QApplication.sendEvent(parent, event)
            return True
        return super().eventFilter(watched, event)


def install_combo_box_wheel_guard(app: QApplication) -> ComboBoxWheelGuard:
    """Create and install the guard on `app`. Keep the returned object alive
    for the app's lifetime (it is parented to `app`, so Qt already does this).
    """

    guard = ComboBoxWheelGuard(app)
    app.installEventFilter(guard)
    return guard
