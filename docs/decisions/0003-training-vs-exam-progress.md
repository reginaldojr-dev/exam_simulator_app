# ADR 0003 — Prova não altera o progresso pedagógico de treino

- Status: Aceita (decisão da PM, roadmap passo 3)
- Implementação: roadmap passo 4 (migração 2)

## Decisão

- Toda tentativa fica no histórico com `mode` = `training` ou `exam`.
- O progresso pedagógico (status, melhor resultado, "não feito/tentado/concluído",
  prioridade de sorteio no treino) só considera tentativas de `training`.
- Tentativas de prova aparecem no histórico de provas e na lista de tentativas.
- A chave de progresso é `(pack_id, exercise_id)`: o mesmo id em packs diferentes é outro exercício.

## Migração dos dados legados (conservadora)

- Nada é apagado. O banco é copiado (`*.bak-v<N>-<data>`) antes de migrar.
- Linhas legadas sem `pack_id` recebem o pack que declara aquele `exercise_id`, se houver
  exatamente um pack instalado com ele; senão recebem `pack_id = 'legacy'` e continuam visíveis.
- Tentativas legadas com `mode` nulo são tratadas como `training` (antes não havia distinção
  confiável; é o comportamento que não faz o usuário perder progresso).
- O progresso é recalculado a partir das tentativas de treino. A tabela antiga não é apagada:
  é renomeada para `progress_legacy_v0` e fica no banco para consulta/rollback.
