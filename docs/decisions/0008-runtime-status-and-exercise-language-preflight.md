# ADR 0008 - S2: status de runtime e preflight por linguagem do exercício

- Status: Aceita (roadmap de fechamento da V1, sessão S2)

## Contexto

A S1 deixou uma violação arquitetural pendente: a UI comparava a linguagem do runtime com
`DEFAULT_LANGUAGE` para tratar C como um card especial de "COMPILADOR". Além disso, o
preflight de prova usava `pack.language`, o que não cobre packs futuros com exercícios de
linguagens diferentes.

## Decisão

1. `RuntimeRegistry` é a autoridade para runtimes registrados, linguagens suportadas,
   lookup e status de disponibilidade.
2. `RuntimeStatus` passa a ser o modelo genérico para a UI/application renderizarem suporte,
   disponibilidade, ferramenta detectada e mensagem, sem lógica específica de linguagem.
3. A linguagem efetiva pertence ao exercício. `exercise.json` v2 pode declarar `language`;
   quando ausente, herda `pack.language`.
4. `pack.json.languages`, quando presente, é tratado como metadado/índice opcional. O
   preflight deriva as linguagens reais dos exercícios carregados.
5. O preflight de prova verifica todas as linguagens exigidas pelos exercícios possíveis do
   pack selecionado antes de iniciar a prova.
6. A UI renderiza um card por runtime registrado e não compara mais linguagem com C,
   Python ou `DEFAULT_LANGUAGE`.
7. Atalhos legados com nome "compiler" permanecem apenas como compatibilidade interna
   durante a transição; eles delegam ao primeiro runtime registrado, sem codificar C.

## Consequências

- `tests/test_architecture.py` não tem mais `expectedFailure`; a regra de comparação de
  linguagem passa a ser obrigatória.
- Packs multilíngua passam a ser representáveis pelo contrato interno sem alterar UI ou
  application.
- Um runtime futuro (ex.: Java) entra implementando `LanguageRuntime`, registrando-se no
  `RuntimeRegistry` e expondo status próprio. A UI renderiza o novo runtime automaticamente.
- A migração de configuração legada (`compiler_path` para C) continua isolada em
  `JsonAppConfigRepository` até a sessão de configuração/migração completa.
