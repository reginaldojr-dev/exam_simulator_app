# Current Project State

## Git

- Branch base: `main`.
- Branch de trabalho atual: `v1/s5`.
- HEAD base confirmado para iniciar S5: `1278b5620d6bfac100fe362a9515c305b0c48550`.
- Última etapa concluída: S5.
- Working tree esperado após conclusão/commit: limpo.
- Roadmap oficial mais recente encontrado: `_local/agents_outputs/roadmap-fechamento-v1-final-v8.md`.

## Tests

- Suíte completa validada após S5: `234 passed, 5 skipped, 7 warnings, 40 subtests passed`.
- Focados S5: `125 passed, 4 skipped, 2 warnings, 40 subtests passed`.
- Smoke S5: Home/StudyIntent/prompt/copy, History views, Settings > Packs, Training subject/workspace, Exam preflight/start e tamanhos 760x520, 1024x720, 1440x900 cobertos por smoke Qt/offscreen.
- Skips conhecidos: compilador C/C++ ausente em testes dependentes de toolchain; symlink no Windows exige privilégio.
- Warnings conhecidos: `PytestCollectionWarning` para classes do app/domínio iniciadas com `Test*` e construtor próprio.
- Testes focados recentes:
  - `tests/test_architecture.py`: `12 passed`.
  - `tests/test_runtime_layer.py`: `12 passed, 2 skipped`.
  - `tests/test_python_runtime.py`: `16 passed`.
  - Qt main window + StudyIntent: `26 passed`.

## Architecture

- Domain: modelos puros para activity/exercise, validation, progress, grading, identifiers e workspace; sem Qt/SQLite/filesystem concreto.
- Application: `MVPTrainerCoordinator` ainda centraliza fluxos, mas delega projeções de histórico para `HistoryService` e resolve behavior/scope por `SessionPolicyRegistry`.
- Ports: contratos para compiler, editor, grader, pack, progress, runtime e workspace.
- Adapters: Qt UI, SQLite, filesystem/workspace, pack loading/import, runtimes/toolchains, editor e graders concretos.
- UI: PySide6; recebe dados da application; subjects renderizados como Markdown por widget Qt centralizado; Home gera prompts por `StudyIntent`/`PackPromptBuilder`; Histórico consome projeções da application.
- Persistence: SQLite local via adapters; progresso separado por pack; schema v3 guarda identidade neutra (`activity_id`, `activity_kind`) e `policy` mantendo colunas legadas.

## Core Contracts

- ActivityDefinition: fronteira neutra exposta por ExerciseDefinition; inclui `programming_language`, `content_language`, `usage` e `validation_plan`.
- ValidationPlan: contém steps declarativos derivados do contrato de pack.
- ValidationStep: representa strategy/execution/testes necessários para validação atual.
- RuntimeRegistry: autoridade para runtimes registrados, status, disponibilidade, descriptors e lookup por linguagem.
- SessionPolicy: `TrainingPolicy` e `ExamPolicy` registradas em `SessionPolicyRegistry`; policy futura pode ser registrada pelo coordinator.
- History: `HistoryService` é leitura/projeção e oferece query/timeline por pack, activity, session, policy e status.
- Workspace: `WorkspaceScope` no port; adapter resolve roots físicos para training/exams/projects.
- StudyIntent/PackPromptBuilder: modelo de intenção de estudo e prompt vendor-neutral para criação externa de packs.

## Pack Contract

- Schema atual: `schema_version: 3`.
- `programming_language`: linguagem/runtime efetiva da activity.
- `content_language`: idioma humano do conteúdo; independente do runtime.
- `usage`: restrições estruturadas declarativas/pedagógicas (`allowed`, `forbidden`, `constraints`, `style`, `behavior`, `notes`).
- `reference`/`solution`: opcionais; exigidas apenas quando expectation/validator declara necessidade, como `reference_output`.
- Runtimes suportados no contrato/app: C, C++, Python e Java.
- Packs públicos autorais: `c-basics` 5, `cpp-basics` 4, `python-basics` 9, `java-basics` 4.

## Persistence

- SQLite é a autoridade local da V1.
- Schema atual após S4: v3.
- Migration v3 adiciona identidade neutra e policy preservando colunas/dados antigos.
- Paths relevantes: configuração/dados locais via infrastructure paths; packs públicos em `examples/packs`; packs locais privados em `_local/packs`.
- DB readonly investigado: bancos reais não têm atributo readonly e abrem em modo read-only; ACL dá `FullControl` ao usuário e só `ReadAndExecute` a `CodexSandboxUsers`, compatível com erro ao rodar sob sandbox.

## Workspace

- Layout atual de treino usa `training/<pack_id>/<activity_id>`.
- Novas provas usam `exams/<session_id>/<activity_id>`.
- Existe migração defensiva de workspace legado de treino quando seguro.
- Nenhum workspace antigo deve ser apagado silenciosamente.
- `projects/<pack>/<project>` é reservado no adapter como scope futuro, sem feature funcional.

## UI

- Home inclui `QUERO ESTUDAR ALGO NOVO`, geração/cópia de prompt e importação de pack.
- Training, Exam, Histórico, Configurações e ajuda de pack existem em Qt.
- Histórico oferece visões: visão geral, por pack, activities, sessões e linha do tempo, com filtros simples por pack/session.
- Configurações > Packs mostra resumo de contrato/capabilities e abre a documentação completa de packs.
- Subjects `subject.md` continuam Markdown e são renderizados na UI com `SubjectMarkdownView` usando suporte nativo do Qt.
- Janela inicial de workspace fecha corretamente após seleção.
- UI não deve acessar SQL nem decidir regras de session/policy.
- Redesign visual amplo continua fora do escopo; S5 reorganizou fluxos principais sem trocar identidade visual.

## Known Issues

- `MVPTrainerCoordinator` ainda é grande e concentra fluxos de treino/prova.
- Colunas legadas `exercise_id`/`mode` permanecem por compatibilidade.
- Restrições de `usage` ainda não são verificadas automaticamente.
- C/C++ podem ficar indisponíveis no ambiente se compiler/toolchain não estiver no PATH.
- Banco antigo readonly em `%APPDATA%` real foi investigado na S4; causa provável é ACL/sandbox, não schema corrompido.

## Important Invariants

- Exam default: 4 horas.
- Pack pode sobrescrever duração da prova.
- Deadline de prova é absoluto; fechar o app não pausa o tempo.
- Prova exige 100%.
- Em prova: PASS avança; FAIL mantém a mesma activity; timeout salva resultado parcial.
- Training e Exam têm progresso separado.
- Progresso é namespaced por pack.
- Runtime/toolchain ausente bloqueia correção/preflight, mas não impede ver subject/workspace quando aplicável.
- `programming_language` != `content_language`.
- StudyIntent mantém `programming_language` separado de `content_language`.
- Reference só é obrigatória quando validator/expectation exige.
- Pack não pode declarar comandos shell arbitrários.
- Domain não depende de Qt/SQLite/filesystem concreto.
- Application não deve importar adapter concreto.
- UI não deve conter regra de negócio nem SQL.
