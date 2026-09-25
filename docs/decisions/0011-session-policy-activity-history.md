# ADR 0011 — SessionPolicy, ActivityIdentity e histórico neutro

## Status

Aceita.

## Contexto

Até a S3, treino e prova preservavam corretamente as regras da V1, mas parte do
código ainda usava `mode`/`exercise_id` como conceitos estruturais. Isso dificultaria
adicionar no futuro uma policy como Project/Milestone ou Quiz sem criar um segundo
subsistema de progresso, histórico e workspace.

## Decisão

- Introduzir `ActivityIdentity(pack_id, activity_id, activity_kind)` no domain.
- Manter `exercise_id` nas APIs e tabelas atuais por compatibilidade, mas persistir
  também `activity_id` e `activity_kind`.
- Introduzir `SessionPolicy` com `TrainingPolicy` e `ExamPolicy`, registradas por
  `SessionPolicyRegistry`.
- Manter os métodos públicos atuais de treino/prova, mas resolver policy/scope por um
  ponto de composição no coordinator.
- Introduzir `WorkspaceScope` no port de workspace; o adapter resolve paths físicos
  como `training/<pack_id>` e `exams/<session_id>`.
- Introduzir `HistoryService` como projeção de leitura sobre dados persistidos. Ele
  consulta e filtra histórico, mas não decide PASS/FAIL, avanço, score ou policy.
- Adicionar migration SQLite v3, preservando dados existentes e colunas legadas.

## Consequências

- Training e Exam continuam com o comportamento atual.
- Uma policy futura pode entrar pelo registry sem alterar persistence/history/UI central.
- Histórico e progresso passam a carregar identidade neutra, mas a UI atual pode seguir
  exibindo "exercícios" até a S5 redesenhar as visões.
- Workspaces novos de prova usam `exams/`; cleanup também reconhece o layout legado
  `exam/` quando uma sessão antiga já tiver esse path persistido.
- O schema SQLite antes da S4 era v2; após esta decisão é v3.
