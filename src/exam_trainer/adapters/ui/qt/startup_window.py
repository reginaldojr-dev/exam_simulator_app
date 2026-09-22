from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from exam_trainer.application.use_cases.initialize_application import (
    InitializeApplication,
)
from exam_trainer.domain.workspace import WorkspaceError


class StartupWindow(QWidget):
    workspace_configured = Signal(Path)

    def __init__(self, initialize_application: InitializeApplication) -> None:
        super().__init__()
        self._initialize_application = initialize_application

        self.setWindowTitle("Configurar Workspace")
        self.setMinimumSize(480, 260)

        title = QLabel("42 Exam Trainer")
        title.setObjectName("title")

        description = QLabel(
            "Escolha onde a workspace local do aplicativo deve ser criada."
        )
        description.setWordWrap(True)

        choose_button = QPushButton("Escolher pasta da workspace")
        choose_button.setMinimumHeight(42)
        choose_button.clicked.connect(self._choose_workspace)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch()
        layout.addWidget(choose_button)

        self.setStyleSheet(
            """
            QLabel#title {
                font-size: 22px;
                font-weight: 700;
            }
            QPushButton {
                font-size: 15px;
                padding: 8px 12px;
            }
            """
        )

    def _choose_workspace(self) -> None:
        selected_parent = QFileDialog.getExistingDirectory(
            self,
            "Escolher local para a workspace",
        )
        if not selected_parent:
            return

        workspace_path = Path(selected_parent) / "42-exam-trainer"
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
