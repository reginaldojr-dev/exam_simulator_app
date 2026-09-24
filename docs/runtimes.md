# Runtimes e toolchains

Este documento descreve o modelo atual de runtimes do Exam Trainer. A fonte
normativa do contrato de packs e activities fica em
`src/exam_trainer/resources/pack-contract.md`.

## Modelo

Cada exercicio declara sua linguagem de programacao por activity:

- `programming_language`: linguagem usada para preparar, compilar e executar a
  solucao do exercicio;
- `content_language`: idioma humano do titulo, enunciado, dicas e textos do
  conteudo.

Esses campos sao independentes. Um pack pode conter exercicios de varias
linguagens de programacao e subjects em `pt-BR`, `en` ou outro locale futuro.
O idioma do conteudo nao altera compilacao, execucao, validacao ou selecao de
runtime.

## RuntimeRegistry

`RuntimeRegistry` e a autoridade da application para:

- listar runtimes registrados;
- descobrir se uma linguagem e suportada;
- consultar disponibilidade de toolchain;
- recuperar descritores de capacidades;
- entregar o runtime correto para a estrategia de execucao.

A UI e os casos de uso nao devem comparar linguagens concretas como `c`,
`python`, `cpp` ou `java`. Eles consultam os servicos de application e os dados
derivados do registry.

## RuntimePort

Cada runtime implementa o contrato `LanguageRuntime`:

- `language`;
- `detect()`;
- `prepare()`;
- `run()`.

Runtimes concretos tambem podem expor um `RuntimeDescriptor`, com:

- nome exibivel;
- extensoes de arquivos aceitas;
- estrategias de execucao suportadas;
- formatos de argumentos suportados;
- suporte a harness de funcao;
- necessidade de classe principal.

O descriptor permite que loaders, validadores e UI consultem capacidades sem
espalhar regras especificas de linguagem.

## Disponibilidade

`detect()` retorna um `RuntimeAvailability`:

- `supported`: o app possui runtime para essa linguagem;
- `available`: a toolchain necessaria foi encontrada e validada;
- `reason`: mensagem tecnica amigavel quando indisponivel;
- `details`: informacoes opcionais, como caminho e versao.

Quando uma toolchain esta ausente, treino ainda pode exibir enunciado e
workspace. A correcao que depende dela e bloqueada com a mensagem retornada
pelo runtime. Em prova, o preflight consulta as linguagens obrigatorias antes
do inicio e bloqueia a sessao se algo necessario estiver indisponivel.

## Runtimes atuais

### C

Usa compilador nativo detectado pelo adapter de compiler. O runtime aceita
programas C e comparacao de saida.

### C++

Usa compilador C++ nativo detectado pelo adapter de compiler. Suporta
exercicios multi-file via `submission.extra_files` e `reference.extra_files`.

### Python

Usa Python de sistema detectado pelo adapter de runtime. A regra permanece:
quando o app estiver empacotado, o Python interno do aplicativo nao deve ser
tratado como Python do usuario.

### Java

Valida `javac` e `java`. O runtime compila fontes para um diretorio de build e
executa a classe principal declarada no plano de validacao. A UI nao contem
regras especiais de Java.

## Adicionando um runtime

Para adicionar uma linguagem nova:

1. implementar um adapter que satisfaça `LanguageRuntime`;
2. declarar um `RuntimeDescriptor` com as capacidades reais;
3. registrar o runtime no composition root;
4. adicionar testes de disponibilidade, preparo e execucao;
5. criar ou migrar packs usando `programming_language` com o novo id.

Nao deve ser necessario alterar a UI nem espalhar condicionais de linguagem
pela application.
