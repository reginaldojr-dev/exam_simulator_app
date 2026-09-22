from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from exam_trainer.adapters.ui.qt.main_window import MainWindow
from exam_trainer.adapters.ui.qt.startup_window import StartupWindow
from exam_trainer.infrastructure.app_factory import AppFactory


class DesktopApp:
    def __init__(self) -> None:
        self._qt_app = QApplication(sys.argv)
        self._workspace_service = AppFactory().create_workspace_service()
        self._window: MainWindow | StartupWindow | None = None

    def run(self) -> int:
        startup_state = self._workspace_service.get_startup_state()
        if startup_state.has_workspace and startup_state.workspace_path is not None:
            self._show_main_window(startup_state.workspace_path)
        else:
            self._show_startup_window()

        return self._qt_app.exec()

    def _show_startup_window(self) -> None:
        startup_window = StartupWindow(self._workspace_service)
        startup_window.workspace_configured.connect(self._show_main_window)
        self._window = startup_window
        startup_window.show()

    def _show_main_window(self, workspace_path: Path) -> None:
        main_window = MainWindow(
            workspace_path,
            AppFactory().create_mvp_coordinator(workspace_path),
        )
        self._window = main_window
        main_window.show()


def main() -> int:
    return DesktopApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
