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
| sem `language ==` fora dos módulos de linguagem | `main_window.py` (card de Configurações comparava com `DEFAULT_LANGUAGE`) | S2 | ✅ resolvida na S2 |

**Já respeitadas** (testes verdes desde a S0):

- domain só importa stdlib pura;
- só a UI e o `main.py` importam PySide6;
- o GenericGrader não conhece runtime nem compilador concreto;
- nada importa cliente HTTP ou framework web.

### Outros achados

- **`language == "c"` na config:** `adapters/persistence/json_app_config_repository.py` mapeia `compiler_path` (legado). Está na lista de exceções até a migração de configuração da S2.
- **Grader:** o `GenericGrader` mora em `adapters/grader/`; a árvore-alvo o coloca em `application/grading/` (S1/S2). Não foi movido na S1 — não fazia parte das 5 violações registradas em `KNOWN_VIOLATIONS`; fica para a extração dos services (Obj. 9/10) numa sessão seguinte.
- **Teste tautológico histórico:** `rank02-practice` foi usado temporariamente como pack público de regressão, mas não era uma boa fonte de verdade. Na S3, os testes públicos passaram a usar os packs autorais em `examples/packs/`, e `_local/packs/` virou a área local ignorada pelo Git.
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
- **Suíte completa naquele momento (ambiente de nuvem, Linux, sem packs privados nem PyInstaller):** 185 passed, 14 failed, 2 skipped, 1 xfailed, 44 subtests passed. Comparado bit a bit com a mesma suíte antes da mudança (`git stash`): **exatamente o mesmo conjunto de 14 falhas antes e depois** — nenhuma regressão. As 14 falhas restantes eram pré-existentes e fora do escopo daquela sessão:
  - `tests/test_build_script.py` (10): dependem de um build real (PyInstaller/`dist/`), não disponível no espelho da nuvem;
  - `tests/test_pack_contract_v2.py` / `tests/test_pack_importer.py` (4, incl. 1 subtest): naquele momento ainda dependiam do `rank02-practice` tautológico; a S3 substituiu essa cobertura pelos packs autorais em `examples/packs/`.
- **Suíte completa no computador do usuário (Windows, `.venv` do projeto, com os packs privados):** foi validada posteriormente durante o fechamento real da S1 no repositório local. O histórico operacional antigo em `Claude outputs/` está obsoleto; a área local atual para artefatos de agentes é `_local/agents_outputs/`.
- **ADR criado:** 0007 (`docs/decisions/0007-s1-application-service-boundaries.md`).
- **Pendências desta sessão:** a extração dos services/view models completos (Obj. 9/10) e a migração do `GenericGrader` para `application/grading/` ficam para a sessão seguinte que assumir essas fases do protocolo (D.2, fases 2 em diante) — não estavam cobertas pelo board de violações verificado nesta rodada e não foram tocadas para não expandir o escopo sem um teste que as trave.


### S2 — Runtimes, linguagens e preflight

- **Objetivo:** remover hardcode de linguagem da UI/application, tornar `RuntimeRegistry` a autoridade de linguagens registradas e preparar o app para packs com exercícios de linguagens diferentes.
- **Mudanças:**
  1. `RuntimeStatus` passa a representar `language`, nome exibido, suporte, disponibilidade, ferramenta detectada e mensagem.
  2. `RuntimeRegistry` expõe `status(...)`, `statuses(...)`, `primary_language()` e mantém lookup/listagem centralizados.
  3. `exercise.json` v2 aceita `language` por exercício, herdando `pack.language` quando ausente. `pack.json` passa a aceitar `languages` como metadado/índice opcional, sem virar fonte da verdade.
  4. `MVPTrainerCoordinator` calcula `pack_languages(pack_id)` a partir dos exercícios carregados, faz preflight de prova sobre todas as linguagens exigidas e expõe status/detecção manual de runtimes sem a UI conhecer linguagem específica.
  5. A UI de Configurações renderiza um card por runtime registrado. O card especial "COMPILADOR" deixou de decidir que C é diferente das demais linguagens; wrappers antigos ficam só como compatibilidade interna.
  6. Correção de treino/prova passa a validar o runtime da linguagem efetiva do exercício antes de executar.
  7. `PythonRuntime.probe` rejeita rapidamente, no Windows, um `.exe` que não tem assinatura PE (`MZ`), evitando travamento ao validar um falso `python.exe`.
- **Decisão arquitetural:** ADR 0008 (`docs/decisions/0008-runtime-status-and-exercise-language-preflight.md`).
- **Testes adicionados/ajustados:**
  - `RuntimeRegistry` reporta runtime suportado, desconhecido e conhecido porém indisponível;
  - preflight de prova usa linguagens efetivas dos exercícios em pack multilíngua;
  - `tests/test_architecture.py` remove o último `expectedFailure`.
- **Resultados locais principais:** `tests/test_architecture.py`: 12 passed; `tests/test_runtime_layer.py`: 12 passed, 2 skipped; `tests/test_python_runtime.py`: 16 passed, 4 subtests passed; `tests/test_qt_main_window.py`: 20 passed.
- **Pendências da sessão:** nenhuma específica da S2. Falhas remanescentes classificadas fora da S2: comparações de `PurePosixPath`/`PureWindowsPath` em testes de contrato no Windows e o pack privado local `rank02-original` gerado anteriormente com JSON BOM/estrutura inválida.


### S3 — Runtimes obrigatórios, pack v3, Activity/Validation e conteúdo pt-BR

- **Roadmap oficial atualizado:** `_local/agents_outputs/roadmap-fechamento-v1-final-v8.md` substitui cumulativamente o v7 e registra a separação entre linguagem de programação e idioma humano do conteúdo.
- **Objetivo:** completar a base genérica de runtimes/contrato/validação da V1, preparar o núcleo para `ActivityDefinition`/`ValidationPlan` e entregar packs autorais por runtime obrigatório.
- **Mudanças principais:**
  1. `RuntimeDescriptor` passa a expor capabilities consultáveis por runtime; `RuntimeRegistry` lista descriptors.
  2. Adicionados runtimes concretos `cpp` e `java`; Java valida `javac` + `java`, C++ valida compilador C++17 quando disponível.
  3. Contrato principal de packs vira `schema_version: 3`.
  4. Activities declaram `programming_language` e `content_language` separadamente. `content_language` cobre subject, título, instruções e textos pedagógicos; runtime/grader/strategy não dependem dele.
  5. `ExerciseDefinition` expõe `ActivityDefinition`, `ValidationPlan` e `ValidationStep` como fronteira neutra para evolução futura.
  6. `submission.extra_files` e `reference.extra_files` suportam exercícios multi-file.
  7. `src/exam_trainer/resources/pack-contract.md` passa a documentar o contrato v3.
  8. Packs públicos versionados em `examples/packs/`: `c-basics`, `cpp-basics`, `python-basics`, `java-basics` e `sample_rank` foram migrados/gerados em v3.
  9. Packs locais em `_local/packs/` (`rank02-practice` e `rank02-original` a `rank06-original`) foram migrados localmente para v3 e continuam ignorados pelo Git.
  10. `docs/HANDOFF_REPORT.md` foi removido por ser handoff histórico obsoleto que apontava para artefatos antigos.
- **Decisão arquitetural:** ADR 0009.
- **Validações:**
  - packs públicos importáveis: `c-basics` 4, `cpp-basics` 3, `python-basics` 8, `java-basics` 3, `sample_rank` 3;
  - packs locais importáveis e não versionados: `rank02-practice` 55, `rank02-original` 55, `rank03-original` 8, `rank04-original` 5, `rank05-original` 5, `rank06-original` 2;
  - referências de `python-basics` e `java-basics` passam no grader real neste ambiente;
  - `tests/test_content_language_contract.py` prova `programming_language` independente de `content_language`, subject UTF-8/pt-BR e grading sem dependência do idioma humano;
  - suíte completa local: 208 passed, 5 skipped, 7 warnings, 48 subtests passed.
- **Pendências:** C e C++ não puderam ser executados manualmente neste ambiente porque gcc/clang/g++/clang++ não estão no PATH; os runtimes reportam indisponibilidade sem crash e os packs são importáveis. `client_server` real do Rank 06 foi normalizado localmente para importação básica; um validator específico continua evolução futura.
