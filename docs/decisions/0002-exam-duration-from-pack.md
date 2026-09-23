# ADR 0002 — Duração da prova vem do pack

- Status: Aceita (decisão da PM, roadmap passo 3)

## Decisão

- `pack.json` pode declarar `"exam": {"duration_minutes": N}` (inteiro, 1..1440).
- Packs sem esse campo (v1 legados) usam o fallback de 4 horas (`LEGACY_EXAM_DURATION_SECONDS`).
- A tela "Preparar prova" mostra a duração e avisa quando é o padrão.

## Consequências

- Nenhum pack existente quebra. Valor fora do intervalo rejeita o pack na importação.
