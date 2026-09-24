from __future__ import annotations

from exam_trainer.adapters.persistence.json_app_config_repository import (
    JsonAppConfigRepository,
)
from exam_trainer.adapters.persistence.sqlite_progress_repository import (
    SQLiteProgressRepository,
)
from exam_trainer.adapters.persistence.sqlite_store import SQLiteStore
from exam_trainer.adapters.compiler.system_c_compiler import SystemCCompiler
from exam_trainer.adapters.compiler.system_cpp_compiler import SystemCppCompiler
from exam_trainer.adapters.editor.subprocess_editor import SubprocessEditorFactory
from exam_trainer.adapters.grader.generic_grader import GenericGrader
from exam_trainer.adapters.runtime.c_runtime import CRuntime
from exam_trainer.adapters.runtime.cpp_runtime import CppRuntime
from exam_trainer.adapters.runtime.java_runtime import JavaRuntime
from exam_trainer.adapters.runtime.python_runtime import PythonRuntime
from exam_trainer.application.capabilities import capabilities_from_runtime_descriptors
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry
from exam_trainer.adapters.exercise_definition.json_loader import JsonExerciseDefinitionLoader
from exam_trainer.adapters.pack.json_pack_loader import JsonPackLoader
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
        cpp_compiler = SystemCppCompiler(manual_compiler=config.load_runtime_path("cpp"))
        runtimes = RuntimeRegistry(
            [
                CRuntime(compiler, manager=compiler),
                CppRuntime(cpp_compiler, manager=cpp_compiler),
                PythonRuntime(manual_python=config.load_runtime_path("python")),
                JavaRuntime(manual_javac=config.load_runtime_path("java")),
            ]
        )
        capabilities = capabilities_from_runtime_descriptors(runtimes.descriptors())
        pack_loader = JsonPackLoader(supported_languages=frozenset(capabilities.languages))
        exercise_loader = JsonExerciseDefinitionLoader(capabilities=capabilities)
        editor_command = config.load_editor_command()
        editor_factory = SubprocessEditorFactory()
        return MVPTrainerCoordinator(
            pack_catalog=LocalPackCatalog(
                managed_packs_dir(),
                bundled_packs_dir=bundled_sample_packs_dir(),
                pack_loader=pack_loader,
                exercise_loader=exercise_loader,
            ),
            progress_repository=self.create_progress_repository(),
            workspace=LocalExerciseWorkspace(),
            grader=GenericGrader(runtimes),
            editor=editor_factory.create(editor_command),
            pack_importer=LocalPackImporter(
                managed_packs_dir(),
                pack_loader=pack_loader,
                exercise_loader=exercise_loader,
            ),
            config_repository=config,
            workspace_port=workspace,
            workspace_root=workspace_root,
            runtimes=runtimes,
            editor_factory=editor_factory,
        )

    def create_config_repository(self) -> JsonAppConfigRepository:
        return JsonAppConfigRepository(app_config_file_path())
