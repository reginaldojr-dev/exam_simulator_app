from __future__ import annotations

from exam_trainer.adapters.persistence.json_app_config_repository import (
    JsonAppConfigRepository,
)
from exam_trainer.adapters.persistence.sqlite_progress_repository import (
    SQLiteProgressRepository,
)
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.adapters.compiler.system_c_compiler import SystemCCompiler
from exam_trainer.adapters.editor.subprocess_editor import SubprocessEditorFactory
from exam_trainer.adapters.grader.generic_grader import GenericGrader
from exam_trainer.adapters.runtime.c_runtime import CRuntime
from exam_trainer.adapters.runtime.python_runtime import PythonRuntime
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry
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
        runtimes = RuntimeRegistry(
            [
                CRuntime(compiler, manager=compiler),
                PythonRuntime(manual_python=config.load_runtime_path("python")),
            ]
        )
        editor_command = config.load_editor_command()
        editor_factory = SubprocessEditorFactory()
        return MVPTrainerCoordinator(
            pack_catalog=LocalPackCatalog(
                managed_packs_dir(),
                bundled_packs_dir=bundled_sample_packs_dir(),
            ),
            progress_repository=self.create_progress_repository(),
            workspace=LocalExerciseWorkspace(),
            grader=GenericGrader(runtimes),
            editor=editor_factory.create(editor_command),
            pack_importer=LocalPackImporter(managed_packs_dir()),
            config_repository=config,
            workspace_port=workspace,
            workspace_root=workspace_root,
            runtimes=runtimes,
            editor_factory=editor_factory,
        )

    def create_config_repository(self) -> JsonAppConfigRepository:
        return JsonAppConfigRepository(app_config_file_path())
