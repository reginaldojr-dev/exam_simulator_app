# ADR 0005 — Um runtime por linguagem, contrato neutro

- Status: Aceita (roadmap passos 5b, 6 e 7)

## Decisão

- O grader é único e neutro (`GenericGrader`). O que muda por linguagem fica num
  `LanguageRuntime` registrado no `RuntimeRegistry`.
- O pack declara a linguagem (`pack.json` → `language`); todos os exercícios do pack usam a mesma.
- O contrato de exercício tem só dois tipos de execução: `program_output` e `function_call`.
- `function_call`: em linguagens compiladas com `main` (C) o PACK fornece o harness; em
  linguagens interpretadas (Python) o APP fornece o harness e o pack declara `entry` e
  `args_format`. Isso é declarado em `LanguageSupport` (`capabilities.py`), não em `if`s.
- O app só usa ferramentas instaladas no sistema do usuário (compilador, interpretador),
  validadas com um probe real. O executável do app nunca é usado como interpretador.
- Nenhum runtime usa shell nem promete sandbox.

## Consequências

- Adicionar uma linguagem = runtime + `LanguageSupport` + registro na factory + doc + pack de exemplo.
- Novas linguagens NÃO são implementadas sem decisão da PM (passo 7 só documenta).
