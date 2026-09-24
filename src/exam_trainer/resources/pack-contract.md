# Contrato de Pack — Exam Trainer

Fonte única do contrato suportado por esta versão do app.

Packs são declarativos: eles descrevem atividades, arquivos, validação e metadados.
Eles não podem declarar comandos de shell, scripts arbitrários, plugins ou graders próprios.

## Segurança

Harnesses e soluções de referência são compilados/executados durante a correção, com as
permissões do usuário local. A importação nunca executa código.

O app valida ids, paths relativos, ZIPs, symlinks/junctions e arquivos declarados antes
de copiar o pack. Não há sandbox completa; importe apenas conteúdo confiável.

## Schema

Use `schema_version: 3`.

O contrato v3 separa:

- `programming_language`: linguagem/runtime da atividade (`c`, `cpp`, `python`, `java`);
- `content_language`: idioma humano do conteúdo (`pt-BR`, `en`, etc.).

O idioma do conteúdo cobre subject, título, descrição, instruções, dicas e textos
pedagógicos. Ele não altera runtime, validação, compilação ou execução. UTF-8 é o padrão.

## Estrutura

```text
my-pack/
├── pack.json
└── level0/
    └── activity_id/
        ├── exercise.json
        ├── subject.md
        └── solution/
            └── reference.ext
```

## pack.json

```json
{
  "schema_version": 3,
  "id": "c-basics",
  "name": "C Basics",
  "version": "1.0.0",
  "languages": ["c"],
  "content_language": "pt-BR",
  "topics": ["c", "basics"],
  "description": "Pack autoral de fundamentos.",
  "exam": { "duration_minutes": 60 },
  "levels": [
    { "id": "level0", "path": "level0" }
  ]
}
```

`languages` é metadado/índice. A linguagem efetiva pertence à atividade.
Sem `exam.duration_minutes`, a prova usa 4 horas.

## exercise.json

```json
{
  "schema_version": 3,
  "id": "argc_counter",
  "type": "exercise",
  "name": "Argc Counter",
  "subject": "subject.md",
  "programming_language": "c",
  "content_language": "pt-BR",
  "topics": ["c", "basics"],
  "submission": { "filename": "argc_counter.c" },
  "validation": {
    "strategy": "program_output",
    "reference": { "source": "solution/reference.c" },
    "tests": {
      "generator": "fixed_cases",
      "expectation": "reference_output",
      "cases": [
        { "args": ["a", "b"], "stdin": "" }
      ]
    },
    "limits": { "timeout_seconds": 3 }
  }
}
```

### submission

- `filename`: arquivo principal esperado na workspace do aluno;
- `extra_files`: arquivos extras que o aluno também deve implementar, para exercícios
  multi-file.

### validation

Campos comuns:

- `strategy`: estratégia de execução reconhecida pelo app;
- `harness`: harness fornecido pelo pack quando a linguagem/strategy exige;
- `entry`: função/classe principal quando a linguagem/strategy exige;
- `args_format`: formato dos argumentos para function_call com harness do app;
- `reference`: solução de referência;
- `tests`: casos e expectation;
- `limits.timeout_seconds`: timeout por caso;
- `support_files`: arquivos copiados para a workspace.

Estratégias atuais:

- `program_output`: compila/executa programa completo;
- `function_call`: valida função usando harness do pack ou do app.

O app pode evoluir para novas strategies/validators via registries. Packs devem usar
somente capabilities suportadas pela versão instalada.

### reference

```json
{
  "source": "solution/main.cpp",
  "harness": "harness/main.cpp",
  "extra_files": ["solution/helper.cpp"]
}
```

`extra_files` permite referências multi-file em C++, Java e linguagens futuras.

### tests

Geradores atuais:

- `fixed_cases`;
- `random_arguments`;
- `random_int_array`;
- `random_integer`;
- `random_string`.

Expectations atuais:

- `reference_output`;
- `literal`;
- `echo_arguments`;
- `sum_integers`.

Para packs novos, prefira `reference_output` ou `literal`. Expectations embutidas são
mantidas para regressão e exemplos simples.

## Linguagens

| programming_language | Runtime/toolchain | Observação |
| --- | --- | --- |
| `c` | compilador C compatível | `program_output` e `function_call` com harness do pack |
| `cpp` | compilador C++17 compatível | suporta arquivos `.cpp/.hpp` e exercícios multi-file |
| `python` | Python 3.9+ do sistema | `function_call` usa harness do app com `entry` |
| `java` | JDK (`javac` + `java`) | `program_output` usa `entry` como classe principal |

Ausência de runtime/toolchain bloqueia correção e preflight de prova, mas não impede
visualizar o subject.

## Subject

Subjects são UTF-8 e podem estar em `pt-BR`, `en` ou outro locale futuro:

```text
Assignment name  : argc_counter
Expected files   : argc_counter.c
--------------------------------------------------------------------------------

Escreva um programa em C que imprime a quantidade de argumentos recebidos.
```

O app não infere runtime a partir do idioma humano do subject.

## Importação

1. Crie uma pasta ou ZIP com `pack.json`.
2. Importe em Configurações > Packs.
3. O app valida schema, arquivos declarados, paths seguros e capabilities.
4. Se houver código executável, o app lista os arquivos antes de copiar o pack.
