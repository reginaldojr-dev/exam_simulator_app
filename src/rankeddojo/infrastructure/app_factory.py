from __future__ import annotations

from rankeddojo.adapters.persistence.json_app_config_repository import (
    JsonAppConfigRepository,
)
from rankeddojo.adapters.persistence.sqlite_progress_repository import (
    SQLiteProgressRepository,
)
from rankeddojo.adapters.persistence.sqlite_store import SQLiteStore
from rankeddojo.adapters.compiler.system_c_compiler import SystemCCompiler
from rankeddojo.adapters.compiler.system_cpp_compiler import SystemCppCompiler
from rankeddojo.adapters.editor.editor_registry import EDITOR_REGISTRY
from rankeddojo.adapters.editor.subprocess_editor import SubprocessEditorFactory
from rankeddojo.adapters.grader.generic_grader import GenericGrader
from rankeddojo.adapters.runtime.c_runtime import CRuntime
from rankeddojo.adapters.runtime.cpp_runtime import CppRuntime
from rankeddojo.adapters.runtime.java_runtime import JavaRuntime
from rankeddojo.adapters.runtime.python_runtime import PythonRuntime
from rankeddojo.application.capabilities import capabilities_from_runtime_descriptors
from rankeddojo.application.engine.content_registry import ContentRegistry
from rankeddojo.application.engine.runtime_registry import RuntimeRegistry
from rankeddojo.adapters.exercise_definition.json_loader import JsonExerciseDefinitionLoader
from rankeddojo.adapters.pack.json_pack_loader import JsonPackLoader
from rankeddojo.adapters.pack.local_pack_catalog import LocalPackCatalog
from rankeddojo.adapters.pack.local_pack_importer import LocalPackImporter
from rankeddojo.adapters.learning.pack_content_provider import PackContentProvider
from rankeddojo.adapters.plugins.loader import PluginLoader
from rankeddojo.adapters.workspace.local_exercise_workspace import LocalExerciseWorkspace
from rankeddojo.adapters.workspace.local_workspace import LocalWorkspace
from rankeddojo.application.use_cases.initialize_application import (
    InitializeApplication,
)
from rankeddojo.application.use_cases.get_learning_track import GetLearningTrack
from rankeddojo.application.use_cases.get_next_learning_activity import (
    GetNextLearningActivity,
)
from rankeddojo.application.use_cases.mvp_coordinator import MVPTrainerCoordinator
from rankeddojo.infrastructure.paths import (
    app_config_file_path,
    app_database_file_path,
    bundled_sample_packs_dir,
    managed_packs_dir,
    user_plugins_dir,
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
        # Built-ins are registered first (above); local opt-in plugins are loaded
        # next, directly into the same RuntimeRegistry/EditorRegistry -- there is no
        # separate plugin registry. A plugin never overrides a built-in (see
        # adapters/plugins/context.py). Zero plugins enabled/installed -> identical
        # behavior to before plugins existed.
        PluginLoader().load_into(
            plugins_dir=user_plugins_dir(),
            enabled_plugin_ids=config.load_enabled_plugins(),
            runtimes=runtimes,
            editors=EDITOR_REGISTRY,
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
            content_registry=self.create_content_registry(pack_loader, exercise_loader),
        )

    def create_config_repository(self) -> JsonAppConfigRepository:
        return JsonAppConfigRepository(app_config_file_path())

    def create_content_registry(
        self,
        pack_loader: JsonPackLoader | None = None,
        exercise_loader: JsonExerciseDefinitionLoader | None = None,
    ) -> ContentRegistry:
        """Fase 9/10: one `ContentRegistry` combining built-in learning
        content (bundled example packs that opted in via `pack.json`'s
        `learning_track`) and installed pack content (the user's own
        managed packs, same opt-in). `create_mvp_coordinator` wires this
        into the coordinator the UI already talks to, passing the SAME
        `pack_loader`/`exercise_loader` it built (capability-aware) so
        learning content stays in sync with the main pack catalog's
        language support. Called with no arguments, it falls back to
        plain loaders -- e.g. for a caller that only needs the registry
        on its own."""
        pack_loader = pack_loader or JsonPackLoader()
        exercise_loader = exercise_loader or JsonExerciseDefinitionLoader()
        registry = ContentRegistry()
        registry.register_provider(
            "builtin",
            PackContentProvider(
                LocalPackCatalog(
                    bundled_sample_packs_dir(),
                    pack_loader=pack_loader,
                    exercise_loader=exercise_loader,
                )
            ),
        )
        registry.register_provider(
            "installed",
            PackContentProvider(
                LocalPackCatalog(
                    managed_packs_dir(),
                    pack_loader=pack_loader,
                    exercise_loader=exercise_loader,
                )
            ),
        )
        return registry

    def create_get_learning_track(self) -> GetLearningTrack:
        return GetLearningTrack(
            content_registry=self.create_content_registry(),
            progress_repository=self.create_progress_repository(),
        )

    def create_get_next_learning_activity(self) -> GetNextLearningActivity:
        return GetNextLearningActivity(get_learning_track=self.create_get_learning_track())
