from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from rankeddojo.adapters.ui.qt.components import widgets as ui
from rankeddojo.adapters.ui.qt.i18n import LocaleService, tr
from rankeddojo.adapters.ui.qt.theme import ThemeManager

from rankeddojo.application.use_cases.initialize_application import (
    InitializeApplication,
    WorkspaceError,
)


class StartupWindow(QWidget):
    workspace_configured = Signal(Path)

    def __init__(
        self,
        initialize_application: InitializeApplication,
        theme_manager: ThemeManager | None = None,
        locale_service: LocaleService | None = None,
    ) -> None:
        super().__init__()
        self._initialize_application = initialize_application
        self._locale = locale_service

        self.setWindowTitle(tr("Configurar Workspace"))
        self.setMinimumSize(480, 260)

        self._title = ui.title_label("RankedDojo")
        self._description = ui.label(
            tr("Escolha onde a workspace local do aplicativo deve ser criada."),
            wrap=True,
        )
        self._choose_button = ui.button(self._button_text(tr("Escolher pasta da workspace"), ">"), self._choose_workspace, "start")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        layout.addWidget(self._title)
        layout.addWidget(self._description)
        layout.addStretch()
        layout.addWidget(self._choose_button)

        (theme_manager or ThemeManager()).apply(self)
        if self._locale is not None:
            self._locale.locale_changed.connect(lambda _locale: self._retranslate())

    @staticmethod
    def _button_text(text: str, prefix: str | None = None) -> str:
        body = text.upper()
        return f"{prefix} {body}" if prefix else body

    def _retranslate(self) -> None:
        self.setWindowTitle(tr("Configurar Workspace"))
        self._description.setText(tr("Escolha onde a workspace local do aplicativo deve ser criada."))
        self._choose_button.setText(self._button_text(tr("Escolher pasta da workspace"), ">"))

    def _choose_workspace(self) -> None:
        selected_parent = QFileDialog.getExistingDirectory(
            self,
            tr("Escolher local para a workspace"),
        )
        if not selected_parent:
            return

        workspace_path = Path(selected_parent) / "rankeddojo"
        try:
            workspace = self._initialize_application.configure_workspace(workspace_path)
        except WorkspaceError as error:
            QMessageBox.warning(self, tr("Workspace inválida"), str(error))
            return
        except OSError as error:
            QMessageBox.critical(
                self,
                tr("Erro ao criar workspace"),
                f"{tr('Não foi possível criar a workspace.')}\n\n{error}",
            )
            return

        self.workspace_configured.emit(workspace.path)
        self.close()

