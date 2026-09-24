# Decisões de produto e arquitetura (ADRs)

Cada arquivo registra UMA decisão: contexto, decisão, consequências. Mudou a decisão?
Crie um ADR novo que substitui o antigo (não reescreva o histórico).

| ADR | Decisão | Status |
| --- | --- | --- |
| [0001](0001-exam-absolute-deadline.md) | Relógio da prova não pausa (deadline absoluto) | Aceita |
| [0002](0002-exam-duration-from-pack.md) | Duração da prova vem do pack, fallback 4h | Aceita |
| [0003](0003-training-vs-exam-progress.md) | Prova não altera o progresso pedagógico de treino | Aceita |
| [0004](0004-pack-code-is-executable.md) | Código de pack é executável; sem sandbox | Aceita |
| [0005](0005-runtime-per-language.md) | Um runtime por linguagem, contrato neutro | Aceita |
| [0006](0006-v1-close-branch-base.md) | Base da branch `v1/close` e blobs com LF | Aceita |
| [0007](0007-s1-application-service-boundaries.md) | Fronteiras entre application, ports, adapters e UI | Aceita |
| [0008](0008-runtime-status-and-exercise-language-preflight.md) | RuntimeRegistry centraliza disponibilidade e preflight por linguagem | Aceita |
| [0009](0009-pack-v3-activity-validation-and-content-language.md) | Pack v3 separa runtime, activity validation e idioma do conteúdo | Aceita |
