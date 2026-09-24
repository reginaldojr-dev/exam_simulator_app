# ADR 0001 — Relógio da prova não pausa (deadline absoluto)

- Status: Aceita (decisão da PM, roadmap passo 3)
- Implementação: `fix(exam): use pack level order, random first exercise and absolute deadline`

## Contexto

Antes, a sessão guardava `remaining_seconds` e decrementava a cada segundo, gravando no
SQLite. Fechar o app pausava o relógio, o que não corresponde a um exame real e gerava
uma escrita no banco por segundo.

## Decisão

- Ao iniciar, a prova grava `deadline_at` (UTC) e `duration_seconds`.
- O tempo restante é sempre `deadline_at - agora`. Fechar o app NÃO pausa: 20 minutos fora contam.
- Se o prazo acabar com o app fechado, ao abrir a prova é encerrada como `timeout` com a nota parcial.
- O estado só é gravado em eventos (início, correção, troca de level, fim); nunca por segundo.
- Uma correção já em andamento quando o prazo vence termina e conta; a prova é encerrada logo depois.

## Consequências

- Migração 1 do banco: sessões ativas legadas recebem `deadline_at = agora + remaining_seconds`
  (não cobra o tempo em que o app ficou fechado ANTES desta versão).
- Mudar o relógio do sistema afeta o tempo restante (aceito; o app não é um proctor).
