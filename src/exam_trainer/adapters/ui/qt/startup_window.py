from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from exam_trainer.adapters.ui.qt.components import widgets as ui
from exam_trainer.adapters.ui.qt.theme import ThemeManager

from exam_trainer.application.use_cases.initialize_application import (
    InitializeApplication,
    WorkspaceError,
)


class StartupWindow(QWidget):
    workspace_configured = Signal(Path)

    def __init__(
        self,
        initialize_application: InitializeApplication,
        theme_manager: ThemeManager | None = None,
    ) -> None:
        super().__init__()
        self._initialize_application = initialize_application

        self.setWindowTitle("Configurar Workspace")
        self.setMinimumSize(480, 260)

        title = ui.title_label("EXAM TRAINER")
        description = ui.label(
            "Escolha onde a workspace local do aplicativo deve ser criada.",
            wrap=True,
        )
        choose_button = ui.button("> ESCOLHER PASTA DA WORKSPACE", self._choose_workspace, "start")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch()
        layout.addWidget(choose_button)

        (theme_manager or ThemeManager()).apply(self)

    def _choose_workspace(self) -> None:
        selected_parent = QFileDialog.getExistingDirectory(
            self,
            "Escolher local para a workspace",
        )
        if not selected_parent:
            return

        workspace_path = Path(selected_parent) / "exam-trainer"
        try:
            workspace = self._initialize_application.configure_workspace(workspace_path)
        except WorkspaceError as error:
            QMessageBox.warning(self, "Workspace inválida", str(error))
            return
        except OSError as error:
            QMessageBox.critical(
                self,
                "Erro ao criar workspace",
                f"Não foi possível criar a workspace.\n\n{error}",
            )
            return

        self.workspace_configured.emit(workspace.path)
        self.close()

