from __future__ import annotations

from exam_trainer.adapters.persistence.json_app_config_repository import (
    JsonAppConfigRepository,
)
from exam_trainer.adapters.persistence.sqlite_progress_repository import (
    SQLiteProgressRepository,
)
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.adapters.compiler.system_c_compiler import SystemCCompiler
from exam_trainer.adapters.editor.subprocess_editor import (
    SubprocessEditor,
    editor_display_name,
)
from exam_trainer.adapters.grader.generic_c_grader import GenericCGrader
from exam_trainer.adapters.pack.local_pack_catalog import LocalPackCatalog
from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter
from exam_trainer.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from exam_trainer.adapters.workspace.local_workspace import LocalWorkspace
from exam_trainer.application.use_cases.initialize_application import (
    InitializeApplication,
)
from exam_trainer.application.use_cases.mvp_coordinator import MVPTrainerCoordinator
from exam_trainer.infrastructure.paths import (
    app_config_file_path,
    app_database_file_path,
    bundled_sample_packs_dir,
    managed_packs_dir,
)


class AppFactory:
    def create_initialize_application(self) -> InitializeApplication:
        return InitializeApplication(
            config_repository=JsonAppConfigRepository(app_config_file_path()),
            workspace_port=LocalWorkspace(),
        )

    def create_workspace_service(self) -> InitializeApplication:
        return self.create_initialize_application()

    def create_progress_repository(self) -> SQLiteProgressRepository:
        return SQLiteProgressRepository(SQLiteStore(app_database_file_path()))

    def create_mvp_coordinator(self, workspace_root) -> MVPTrainerCoordinator:
        config = JsonAppConfigRepository(app_config_file_path())
        workspace = LocalWorkspace()
        compiler = SystemCCompiler(manual_compiler=config.load_compiler_path())
        editor_command = config.load_editor_command()
        return MVPTrainerCoordinator(
            pack_catalog=LocalPackCatalog(
                managed_packs_dir(),
                bundled_packs_dir=bundled_sample_packs_dir(),
            ),
            progress_repository=self.create_progress_repository(),
            workspace=LocalExerciseWorkspace(),
            grader=GenericCGrader(compiler),
            editor=SubprocessEditor(editor_command, editor_display_name(editor_command)),
            pack_importer=LocalPackImporter(managed_packs_dir()),
            compiler=compiler,
            config_repository=config,
            workspace_port=workspace,
            workspace_root=workspace_root,
        )

    def create_config_repository(self) -> JsonAppConfigRepository:
        return JsonAppConfigRepository(app_config_file_path())
