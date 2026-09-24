# Estado do projeto — fechamento da V1

Fotografia do projeto ao longo do "Roadmap de fechamento da V1" (sessões S0–S6).

- **Tabela de status:** preenchida e revisada a cada sessão; fechada na S6.
- **Status possíveis:** IMPLEMENTADO · PARCIAL · FUTURO · PENDÊNCIA EXTERNA.

## Status

| Área | Status | Observação |
| --- | --- | --- |
| Desktop | — | |
| Treino | — | |
| Prova | — | |
| Histórico | — | |
| Packs (infra) | — | |
| C | — | |
| C++ | — | |
| Python | — | |
| Runtime plugins | — | |
| Toolchains | — | |
| Estratégias de execução | — | |
| Themes | — | |
| Pack validation | — | |
| SQLite/migrations | — | |
| Eventos de progresso | — | |
| Build | — | |
| CI | — | |
| Security | — | |
| Documentation | — | |
| Site readiness | — | |
| Mobile readiness | — | |
| Sync readiness | — | |
| Packs de conteúdo (practice, python, originais locais) | — | responsabilidade do prompt "Geração de packs" |

## Antes (medido na S0)

Base medida: branch `v1/close` = `v1/packs` (0a7b28c) + série do roadmap anterior (11 commits).

### Estrutura

```text
src/exam_trainer/
  domain/                     modelos e regras puras (exercise/pack definitions, grading, identifiers, attempt modes, workspace)
  application/
    engine/                   execution strategies, expectations, generators, runtime_registry, test_case_service, trace
    use_cases/                MVPTrainerCoordinator (god object) + casos de uso antigos
    capabilities.py, mvp_models.py
  ports/                      compiler, config, editor, grader, pack, progress, runtime, workspace
  adapters/
    compiler/ editor/ exercise_definition/ filesystem/ grader/ pack/ persistence/ runtime/ workspace/
    ui/qt/ (main_window, startup_window, components/, theme/)
    contract_fields.py
  infrastructure/             app_factory (composition root), paths
  resources/                  pack-contract.md
```

### Medidas

| Medida | Valor |
| --- | --- |
| Arquivos de teste / testes | 24 / 189 (2 skips do pack privado) |
| `MVPTrainerCoordinator` | 649 linhas, 48 métodos públicos |
| Métodos do coordinator usados pela UI | 37 distintos |
| `main_window.py` | 1418 linhas (todas as telas num arquivo) |
| Acessos a dict/strings mágicas na UI | 23 (ex.: `row["status"] == "concluído"`, `mode == "exam"`) |

### Violações de fronteira (viraram testes `expectedFailure` em `tests/test_architecture.py`)

| Regra | Onde | Sessão que resolve | Status |
| --- | --- | --- | --- |
| domain só com `PurePath` | `domain/workspace.py` importava `pathlib.Path` e chamava `expanduser()` | S1 | ✅ resolvida na S1 |
| application não importa adapters | `mvp_coordinator.py` importava `adapters.editor.subprocess_editor` e, dentro de uma função, `adapters.runtime.c_runtime` | S1 | ✅ resolvida na S1 |
| application não mexe em arquivos | `mvp_coordinator.py` usava `shutil.rmtree` (fim da prova) e `Path.rename`/`mkdir` (migração da workspace de treino) | S1 | ✅ resolvida na S1 |
| ports só dependem de domain | `ports/progress_repository.py` importava `application.mvp_models.ProgressEntry` | S1 | ✅ resolvida na S1 |
| UI só importa application | `main_window.py` importava `adapters.editor` e `domain.pack_definition`; `startup_window.py` importava `domain.workspace` | S1 | ✅ resolvida na S1 |
| sem `language ==` fora dos módulos de linguagem | `main_window.py` (card de Configurações compara com `DEFAULT_LANGUAGE`) | S2 | pendente |

**Já respeitadas** (testes verdes desde a S0):

- domain só importa stdlib pura;
- só a UI e o `main.py` importam PySide6;
- o GenericGrader não conhece runtime nem compilador concreto;
- nada importa cliente HTTP ou framework web.

### Outros achados

- **`language == "c"` na config:** `adapters/persistence/json_app_config_repository.py` mapeia `compiler_path` (legado). Está na lista de exceções até a migração de configuração da S2.
- **Grader:** o `GenericGrader` mora em `adapters/grader/`; a árvore-alvo o coloca em `application/grading/` (S1/S2). Não foi movido na S1 — não fazia parte das 5 violações registradas em `KNOWN_VIOLATIONS`; fica para a extração dos services (Obj. 9/10) numa sessão seguinte.
- **Teste tautológico:** `tests/test_pack_contract_v2.py::PracticePackGradingRegressionTest` corrige o `rank02-practice` usando as referências dele mesmo. Como as 55 referências são o mesmo echo, o teste não prova nada sobre o caminho C. Continua falhando (esperado): será substituído na sessão que reescrever o pack (Objetivo 13.2, "Geração de packs").
- **Finais de linha:** o repositório guarda blobs com LF (`core.autocrlf` no Windows). O espelho da série anterior tinha CRLF no `.spec` e no `rank02-practice`; a S0 refez a série sobre blobs LF (ADR 0006).

## Diário

### S0 — Verificação, linha de base e testes de arquitetura

- **Série anterior:** não tinha sido aplicada no computador (não existia `roadmap/execution`).
- **Estado encontrado:**
  - HEAD em `v1/packs` (0a7b28c), criada a partir de `visual-redesign` com dois commits: `chore(git): ignore private pack folders` e `ui: título da Home como EXAM TRAINER`. A branch já estava no remoto;
  - pastas privadas `rank02..06-original`, `_private_backup` e `_private_notes` presentes e ignoradas pelo Git.
- **Base de `v1/close`:** `v1/packs` (0a7b28c). A entrega da S0 inclui a série anterior refeita sobre essa base, mais os commits da S0 (ADR 0006).
- **Testes:** 189 → 201 (+12 de arquitetura; 6 `expectedFailure` com a sessão que resolve cada um).
- **Pendências da sessão:** nenhuma.


### S1 — Application em services + view models (fronteiras de dependência)

- **Escopo real desta sessão:** as 5 violações de fronteira registradas em `KNOWN_VIOLATIONS` com sessão "S1" (ver tabela acima). A extração completa dos services (`TrainingService`, `ExamService`, `HistoryService`, `PackService`, `ReadinessService`, `SettingsService`, `ProgressService`) e dos view models (Obj. 9/10 completos) **não** estava coberta pelos testes de arquitetura já registrados e fica para uma sessão seguinte — este relatório não a reivindica como feita.
- **Onde foi trabalhado:** sem shell no computador do usuário nesta sessão (D.1 → espelho na nuvem). Mirror do `src/`, `tests/`, `examples/packs/` (públicos) e configuração; venv Python 3.13 (mesma versão dos `.pyc` locais), PySide6 6.11.2 com `QT_QPA_PLATFORM=offscreen`.
- **Mudanças:**
  1. `domain/workspace.py`: `Workspace.path` vira `PurePath`; `expanduser()` sai do domain e vai para `InitializeApplication` (application).
  2. `ProgressEntry` migra de `application/mvp_models.py` para `domain/progress.py` (reexportada em `mvp_models` por compatibilidade). `ports/progress_repository.py` importa de `domain.progress`.
  3. Novo port `EditorFactory` (+ `EditorLaunchError`) em `ports/editor_port.py`; adapter `SubprocessEditorFactory` em `adapters/editor/subprocess_editor.py`. `MVPTrainerCoordinator` recebe `editor_factory` no construtor e não importa mais `adapters.editor`.
  4. `ExerciseWorkspacePort` ganha `move_directory`/`remove_directory`, implementados em `LocalExerciseWorkspace`. `mvp_coordinator.py` delega a migração do workspace legado de treino e a limpeza da sessão de prova a esses métodos; `import shutil` sai da application.
  5. `MVPTrainerCoordinator` não aceita mais `compiler`; `runtimes: RuntimeRegistry` é obrigatório (quem monta é o composition root/teste). `app_factory.py` atualizado.
  6. UI: `main_window.py` para de importar `adapters.editor` e `domain.pack_definition` direto (usa `application.mvp_models.DEFAULT_LANGUAGE` e `coordinator.resolve_known_editor(...)`); `startup_window.py` importa `WorkspaceError` via `application.use_cases.initialize_application`.
  - Detalhe completo da decisão: ADR 0007.
- **Testes adaptados** (mesma cobertura; só a construção do coordinator mudou — `teste antigo → teste novo`, mesmo nome de teste em todos os casos, só o `setUp`/helper de construção mudou):
  - `tests/test_mvp_coordinator.py::MVPTrainerCoordinatorTest._coordinator`
  - `tests/test_progress_by_pack.py::...coordinator`
  - `tests/test_exam_rules.py::...coordinator`
  - `tests/test_python_runtime.py::PythonBasicsPackTest.test_coordinator_trains_python_pack_with_language_preflight`
  - `tests/test_runtime_layer.py::PreflightByLanguageTest.test_pack_language_without_runtime_is_blocked`
  - `tests/test_qt_main_window.py::MainWindowTest._window`
- **Testes de arquitetura:** as 5 entradas de `KNOWN_VIOLATIONS` com sessão "S1" saem do dicionário; os `@expected_until` correspondentes são removidos. `tests/test_architecture.py`: 11 passed, 1 xfailed (só `test_language_checks_only_in_language_aware_modules`, S2).
- **Suíte completa (ambiente de nuvem, Linux, sem packs privados nem PyInstaller):** 185 passed, 14 failed, 2 skipped, 1 xfailed, 44 subtests passed. Comparado bit a bit com a mesma suíte antes da mudança (`git stash`): **exatamente o mesmo conjunto de 14 falhas antes e depois** — nenhuma regressão. As 14 falhas restantes são pré-existentes e fora do escopo desta sessão:
  - `tests/test_build_script.py` (10): dependem de um build real (PyInstaller/`dist/`), não disponível no espelho da nuvem;
  - `tests/test_pack_contract_v2.py` / `tests/test_pack_importer.py` (4, incl. 1 subtest): `rank02-practice` é o pack tautológico já documentado em "Outros achados" — só será corrigido quando o Objetivo 13.2 (reescrita do pack) rodar.
- **Suíte completa no computador do usuário (Windows, `.venv` do projeto, com os packs privados):** ainda precisa ser rodada localmente ao aplicar os patches — o `apply-v1-close-S1.ps1` desta entrega faz isso e grava o resultado em `Claude outputs/v1-close/S1/result.json`, seguindo o mesmo protocolo da S0.
- **ADR criado:** 0007 (`docs/decisions/0007-s1-application-service-boundaries.md`).
- **Pendências desta sessão:** a extração dos services/view models completos (Obj. 9/10) e a migração do `GenericGrader` para `application/grading/` ficam para a sessão seguinte que assumir essas fases do protocolo (D.2, fases 2 em diante) — não estavam cobertas pelo board de violações verificado nesta rodada e não foram tocadas para não expandir o escopo sem um teste que as trave.
