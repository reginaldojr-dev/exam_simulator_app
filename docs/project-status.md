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

| Regra | Onde | Sessão que resolve |
| --- | --- | --- |
| domain só com `PurePath` | `domain/workspace.py` importa `pathlib.Path` e chama `expanduser()` | S1 |
| application não importa adapters | `mvp_coordinator.py` importa `adapters.editor.subprocess_editor` e, dentro de uma função, `adapters.runtime.c_runtime` | S1 |
| application não mexe em arquivos | `mvp_coordinator.py` usa `shutil.rmtree` (fim da prova) e `Path.rename`/`mkdir` (migração da workspace de treino) | S1 |
| ports só dependem de domain | `ports/progress_repository.py` importa `application.mvp_models.ProgressEntry` | S1 |
| UI só importa application | `main_window.py` importa `adapters.editor` e `domain.pack_definition`; `startup_window.py` importa `domain.workspace` | S1 |
| sem `language ==` fora dos módulos de linguagem | `main_window.py` (card de Configurações compara com `DEFAULT_LANGUAGE`) | S2 |

**Já respeitadas** (testes verdes desde a S0):

- domain só importa stdlib pura;
- só a UI e o `main.py` importam PySide6;
- o GenericGrader não conhece runtime nem compilador concreto;
- nada importa cliente HTTP ou framework web.

### Outros achados

- **`language == "c"` na config:** `adapters/persistence/json_app_config_repository.py` mapeia `compiler_path` (legado). Está na lista de exceções até a migração de configuração da S2.
- **Grader:** o `GenericGrader` mora em `adapters/grader/`; a árvore-alvo o coloca em `application/grading/` (S1/S2).
- **Teste tautológico:** `tests/test_pack_contract_v2.py::PracticePackGradingRegressionTest` corrige o `rank02-practice` usando as referências dele mesmo. Como as 55 referências são o mesmo echo, o teste não prova nada sobre o caminho C. Será substituído na S2 pelo pack de fixture `c-regression`.
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
