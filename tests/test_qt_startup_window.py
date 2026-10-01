from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from rankeddojo.adapters.ui.qt.startup_window import StartupWindow
from rankeddojo.domain.workspace import Workspace


class StubInitializeApplication:
    def __init__(self) -> None:
        self.configured: Path | None = None

    def configure_workspace(self, selected_directory: Path | str) -> Workspace:
        self.configured = Path(selected_directory)
        self.configured.mkdir(parents=True, exist_ok=True)
        return Workspace.from_path(self.configured)


class StartupWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_closes_after_workspace_is_configured(self) -> None:
        service = StubInitializeApplication()
        window = StartupWindow(service)
        captured: list[Path] = []
        window.workspace_configured.connect(captured.append)
        window.show()
        self.assertTrue(window.isVisible())

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch(
            "rankeddojo.adapters.ui.qt.startup_window.QFileDialog.getExistingDirectory",
            return_value=temp_dir,
        ):
            window._choose_workspace()
            self._app.processEvents()

        self.assertEqual(captured, [Path(temp_dir) / "rankeddojo"])
        self.assertFalse(window.isVisible())

    def test_public_brand_changed_but_default_workspace_folder_stays_legacy(self) -> None:
        service = StubInitializeApplication()
        window = StartupWindow(service)

        self.assertEqual(window._title.text(), "RankedDojo")

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch(
            "rankeddojo.adapters.ui.qt.startup_window.QFileDialog.getExistingDirectory",
            return_value=temp_dir,
        ):
            window._choose_workspace()

        self.assertEqual(service.configured, Path(temp_dir) / "rankeddojo")

    def test_cancel_keeps_startup_window_open(self) -> None:
        service = StubInitializeApplication()
        window = StartupWindow(service)
        window.show()

        with mock.patch(
            "rankeddojo.adapters.ui.qt.startup_window.QFileDialog.getExistingDirectory",
            return_value="",
        ):
            window._choose_workspace()
            self._app.processEvents()

        self.assertTrue(window.isVisible())


if __name__ == "__main__":
    unittest.main()
