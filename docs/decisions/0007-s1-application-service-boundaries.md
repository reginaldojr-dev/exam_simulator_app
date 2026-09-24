# ADR 0007 — S1: application só depende de ports; domain sem I/O

- Status: Aceita (roadmap de fechamento da V1, sessão S1)

## Contexto

`tests/test_architecture.py` registrava 5 violações conhecidas atribuídas à S1 (mais 1 para a S2, que continua aberta):

1. `domain/workspace.py` importava `pathlib.Path` e chamava `expanduser()` (I/O concreto dentro do domain).
2. `application/use_cases/mvp_coordinator.py` importava adapters concretos diretamente: `adapters.editor.subprocess_editor` (no topo do módulo, para reconstruir o editor em `save_editor_command`) e `adapters.runtime.c_runtime.CRuntime` (import interno, usado como atalho quando só `compiler` era passado ao construtor).
3. O mesmo coordinator usava `shutil.rmtree` (fim da prova) e `Path.rename`/`mkdir` (migração do layout antigo de workspace de treino) diretamente, em vez de delegar a um adapter.
4. `ports/progress_repository.py` importava `ProgressEntry` de `application.mvp_models` — um port dependendo da application, invertendo a regra "ports só dependem de domain".
5. A UI (`adapters/ui/qt/main_window.py` e `startup_window.py`) importava `adapters.editor`, `domain.pack_definition` e `domain.workspace` diretamente, em vez de passar só pela application.

## Decisão

1. **`Workspace` (domain) vira uma regra pura**: `path` é tipado como `PurePath`, sem chamar `Path`/`expanduser()`. Expandir `~` é responsabilidade de quem chama `Workspace.from_path` (agora em `InitializeApplication`, na application) — o valor concreto (`pathlib.Path`) continua chegando até os adapters porque `from_path` não força a normalização para `PurePath` quando já recebe um `Path` (duck typing: `Path` é subclasse de `PurePath`).
2. **`ProgressEntry` migra para `domain/progress.py`**. `application/mvp_models.py` reexporta o nome para não quebrar quem já importava de lá (`mvp_coordinator.py`, `adapters/persistence/sqlite_progress_repository.py`). `ports/progress_repository.py` passa a importar de `domain.progress`.
3. **Novo port `EditorFactory`** (`ports/editor_port.py`), com `display_name`, `validate`, `create` e `resolve_known`. `EditorLaunchError` também migra para lá (era definida em `adapters/editor/subprocess_editor.py`). O adapter ganha `SubprocessEditorFactory`, que implementa o port reaproveitando as funções que já existiam. O coordinator passa a receber `editor_factory: EditorFactory` no construtor e nunca mais importa `adapters.editor` diretamente.
4. **`ExerciseWorkspacePort` ganha `move_directory` e `remove_directory`**, implementados em `LocalExerciseWorkspace`. O coordinator delega a eles a migração do layout antigo de treino e a limpeza da pasta da sessão de prova ao final; `import shutil` sai da application inteira. As checagens de elegibilidade (`.exists()`, `.is_file()`, comparação de paths) continuam na application — não são I/O que muda estado, só leitura/decisão, e a regra de arquitetura (`test_application_does_not_touch_the_filesystem`) só proíbe `shutil`/`os`.
5. **`MVPTrainerCoordinator` para de aceitar `compiler` e monta o runtime sozinho.** O parâmetro `compiler: ConfigurableCompilerPort | None` só existia para o atalho `RuntimeRegistry([CRuntime(compiler, manager=compiler)])`; como não era guardado em `self`, virava código morto se o atalho saísse. `runtimes: RuntimeRegistry` passa a ser obrigatório — quem monta o coordinator (composition root ou teste) monta o registry explicitamente. `app_factory.py` já montava `runtimes` do jeito certo; só os testes que dependiam do atalho (`test_mvp_coordinator`, `test_progress_by_pack`, `test_exam_rules`, `test_qt_main_window`) precisaram passar a montar `RuntimeRegistry([CRuntime(...)])` na mão — mesma cobertura, sem o atalho.
6. **UI**: `main_window.py` importa `DEFAULT_LANGUAGE` de `application.mvp_models` (que reexporta de `domain.pack_definition`) em vez de importar o domain direto; a resolução de editores conhecidos ("VS Code" etc.) passa a ser `coordinator.resolve_known_editor(label)`, que delega ao `EditorFactory`. `startup_window.py` importa `WorkspaceError` de `application.use_cases.initialize_application` (que reexporta de `domain.workspace`).

## Consequências

- `tests/test_architecture.py`: as 5 entradas de `KNOWN_VIOLATIONS` atribuídas à S1 saem do dicionário e os `@expected_until` correspondentes são removidos; os 5 testes agora passam de verdade. Só `test_language_checks_only_in_language_aware_modules` (S2) continua `expectedFailure`.
- Testes adaptados (mesma cobertura, API nova): `test_mvp_coordinator.py`, `test_progress_by_pack.py`, `test_exam_rules.py`, `test_python_runtime.py`, `test_runtime_layer.py`, `test_qt_main_window.py` — todos passavam `compiler=` (ou nada) para o coordinator; passam a montar `RuntimeRegistry` e `editor_factory=SubprocessEditorFactory()` explicitamente.
- Nenhum teste foi apagado ou teve cobertura reduzida — só a forma de construir o coordinator nos testes mudou.
- `GenericGrader` continua em `adapters/grader/` (fora do alvo `application/grading/`) — essa mudança de módulo fica para a S1/S2 seguinte, junto da extração dos services (`TrainingService`, `ExamService` etc., Obj. 9/10), que não fazia parte do escopo verificado nesta rodada (o board de violações registrado cobria só os 5 itens acima).
- Suíte completa (mirror na nuvem, sem os packs privados nem PyInstaller): antes e depois da mudança, exatamente o mesmo conjunto de 14 falhas pré-existentes (rank02-practice tautológico — Objetivo 13.2 ainda não feito — e `test_build_script.py`, que depende de um build real). Nenhuma regressão.
