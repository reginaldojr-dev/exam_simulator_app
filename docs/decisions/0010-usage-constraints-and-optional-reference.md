# ADR 0010 — Restrições de uso e referência opcional por validação

## Status

Aceita.

## Contexto

O contrato v3 já separa `ActivityDefinition`, `ValidationPlan` e `ValidationStep`.
Durante a criação dos packs autorais de estudo, ficou claro que nem toda atividade
precisa carregar uma solução oficial. Muitos exercícios podem ser validados por casos
determinísticos suficientes, enquanto outros precisam executar uma referência para
gerar a saída esperada.

Também faltava um campo estruturado para declarar funções, bibliotecas, imports,
headers e regras permitidas/proibidas. Deixar isso apenas no subject tornaria difícil
reutilizar essas informações no futuro PackPromptBuilder ou em validators capazes de
verificar restrições específicas.

## Decisão

- `reference` não é obrigatória no nível genérico da activity.
- A necessidade de referência pertence à expectation/validator. Nesta versão,
  `reference_output` exige `reference`; `literal` não exige.
- O loader consulta as capabilities registradas para saber se uma expectation exige
  referência, em vez de hardcode global por activity.
- `usage` passa a descrever restrições estruturadas da atividade:
  - `allowed` e `forbidden` agrupam `functions`, `libraries`, `imports`, `headers`,
    `apis` e `flags`;
  - `constraints`, `style`, `behavior` e `notes` registram regras textuais.
- Na V1, `usage` é declarativo/pedagógico. O loader valida formato, mas não afirma
  verificação automática de funções, imports ou estilo.

## Consequências

- Packs podem existir sem `solution/` quando bons testes independentes bastarem.
- Validators futuros podem declarar suas dependências e capabilities sem espalhar
  regras no loader, UI ou grader.
- Subjects continuam livres para renderizar restrições em pt-BR, mas a informação
  principal também fica disponível em estrutura de dados.
- Não há promessa falsa de enforcement: restrições de uso só serão automáticas quando
  um validator específico implementar essa capability.
