# Contrato de Pack — 42 Exam Trainer

Fonte única do contrato. O README, a ajuda dentro do app ("Como criar um pack") e o
executável usam ESTE arquivo.

O 42 Exam Trainer não é limitado ao Rank 02. Qualquer rank, trilha, lista de escola ou
coleção pessoal pode virar um pack, desde que siga este contrato e use capabilities que o
app suporta. O programa define o contrato; os exercícios se adaptam a ele. Packs não podem
declarar comandos de shell, graders próprios nem plugins.

Não coloque em packs públicos subjects oficiais da 42, soluções oficiais ou conteúdo
copiado de provas.

## 1. Segurança: pack contém código executável

Harnesses (`main.c`) e soluções de referência são compilados e EXECUTADOS no seu
computador durante a correção, com as permissões do seu usuário. NÃO há sandbox.
Importe só packs de fontes em que você confia. Antes de importar, o app lista os
arquivos executáveis e pede confirmação.

A importação nunca executa nada. Ela garante:

- ids (`pack.id`, ids de level e de exercício) seguem `[A-Za-z0-9][A-Za-z0-9_-]{0,63}` e
  não são nomes reservados do Windows (`..`, `C:`, pontos e barras são recusados);
- todo caminho declarado é relativo, sem `..`, drive, UNC ou `:`, e fica dentro do pack
  (conferido com o caminho resolvido);
- symlinks e junctions em qualquer lugar do pack são recusados;
- entradas de ZIP são checadas antes de extrair (caminho absoluto, `..`, symlink, número
  de entradas e tamanho descompactado);
- o destino fica dentro da pasta de packs gerenciada pelo app.

Se qualquer coisa for inválida, o pack inteiro é recusado e nada é copiado.

## 2. Versões do contrato

| Versão | Como declarar | Situação |
| --- | --- | --- |
| v1 | sem `schema_version` | suportado; normalizado para o modelo v2 ao carregar |
| v2 | `"schema_version": 2` em `pack.json` e em cada `exercise.json` | recomendado para packs novos |

- `schema_version` ausente = v1. Qualquer valor diferente de 1 ou 2 é recusado.
- v1 ignora campos desconhecidos (como sempre fez). v2 é estrito: campo desconhecido é erro
  (pega erro de digitação).
- O app carrega v1 e v2 para o MESMO modelo interno. Packs v1 existentes continuam
  funcionando sem mudança.

## 3. Estrutura de pastas

```text
meu_pack/
├── pack.json
├── level0/
│   └── steady_echo/
│       ├── exercise.json
│       └── subject.md
└── level1/
    └── sum_values/
        ├── exercise.json
        ├── subject.md
        ├── harness/
        │   └── main.c
        └── solution/
            └── sum_values.c
```

Cada level é uma pasta com uma subpasta por exercício. Caminhos declarados em
`exercise.json` são relativos à pasta do exercício.

## 4. pack.json

v2:

```json
{
  "schema_version": 2,
  "id": "meu_rank",
  "name": "Meu Rank",
  "version": "1.0.0",
  "language": "c",
  "topics": ["strings", "ponteiros"],
  "description": "Opcional.",
  "exam": { "duration_minutes": 180 },
  "levels": [
    { "id": "level0", "path": "level0" },
    { "id": "level1", "path": "level1" }
  ]
}
```

- `id`: estável; vira nome de pasta e chave do progresso. Mudar o id = pack novo.
- `language`: linguagem de TODOS os exercícios do pack. v1 = `c`. Linguagem não
  suportada pelo app = pack recusado.
- `topics`: opcional, até 20 textos curtos.
- `exam.duration_minutes`: opcional, inteiro de 1 a 1440. Sem ele, a prova dura 4 horas.
- `levels`: usados NA ORDEM declarada (treino e prova). Ids nunca são ordenados
  alfabeticamente: `level10` vem depois de `level9` se estiver declarado depois.

v1 (continua válido): o mesmo sem `schema_version`, `language`, `topics` e `description`.

## 5. exercise.json

### 5.1 Campos

| Campo | Obrigatório | Descrição |
| --- | --- | --- |
| `schema_version` | v2 | `2` |
| `id`, `name` | sim | id seguro e nome exibido |
| `subject` | sim | arquivo do enunciado (ex.: `subject.md`) |
| `topics` | não | lista de textos curtos |
| `submission.filename` | sim | nome do arquivo que o aluno entrega |
| `execution` | sim | como a submissão roda (ver 5.2) |
| `reference` | quando `expectation` = `reference_output` (v2) | solução de referência (ver 5.3) |
| `tests` | sim | geração de casos e saída esperada (ver 5.4) |
| `limits.timeout_seconds` | não | padrão 2 |
| `support_files` | não | arquivos copiados para a workspace do aluno (ex.: `.h`) |

### 5.2 execution — tipos neutros

| Tipo | O aluno entrega | Como roda |
| --- | --- | --- |
| `program_output` | um programa completo | o app executa o programa com os argumentos/stdin do caso |
| `function_call` | uma função | um harness chama a função; a saída do harness é comparada |

Quem fornece o harness de `function_call` depende da linguagem:

- **C**: o PACK fornece o harness (`execution.harness`, um `main.c` que chama a função).
  `entry`/`args_format` não são usados em C.
- **Python**: o APP fornece o harness. O pack declara só:
  - `execution.entry`: nome da função que o aluno escreve (ex.: `"add"`);
  - `execution.args_format`: como cada argumento do caso vira argumento da função:
    `json` (padrão: `"42"` → 42, `"[1, 2]"` → lista, `"\"abc\""` → string) ou `str`
    (o texto como está).
  O harness chama `entry(*args)` e, se o retorno não for `None`, imprime
  `json.dumps(retorno)` + quebra de linha (ex.: `"cba"` sai como `"cba"` com aspas; `None`
  não imprime nada). O que a função imprimir com `print` também entra na saída.
  `execution.harness` é recusado em Python.

Aliases do v1 (continuam aceitos; prefira os tipos neutros em packs novos):

| v1 | Vira |
| --- | --- |
| `function_with_main` + `fixture` | `function_call` com `harness` = `fixture` |
| `reference_compare` + `reference` (sem `fixture`) | `program_output` + `reference.source` |
| `reference_compare` + `reference` + `fixture` | `function_call` com harness + `reference` com o mesmo harness |

`execution.fixture` (v1) e `execution.harness` (v2) são o mesmo campo; declare só um.
O tipo `custom` não é suportado e é recusado.

### 5.3 reference — solução de referência (v2)

```json
"reference": { "source": "solution/sum_values.c", "harness": "harness/main.c" }
```

Dica: neste repositório uma pasta chamada `reference/` é ignorada pelo Git (proteção de
material privado); em packs públicos use outro nome, como `solution/`.

A referência roda com os mesmos casos; a saída dela vira a saída esperada
(`expectation: reference_output`). `harness` é opcional (use quando a referência é uma
função). No v1 a referência fica em `execution.reference` (só com `reference_compare`).

### 5.4 tests — casos e saída esperada

- `generator`: `fixed_cases`, `random_arguments`, `random_int_array`, `random_integer`,
  `random_string`.
- `expectation` (como obter a saída esperada):
  - `reference_output`: saída da solução de referência (recomendado);
  - `literal`: o `expected` de cada caso fixo;
  - `echo_arguments`, `sum_integers`: regras embutidas no app. Mantidas por
    compatibilidade; para packs novos prefira `reference_output` ou casos fixos.
- `cases`: casos fixos, rodados antes dos gerados. Obrigatório com `fixed_cases`.

```json
{ "args": ["hello", "world"], "stdin": "", "expected": "hello world\n" }
```

Um caso passa quando o código de saída é 0 e o stdout é idêntico ao esperado. Na prova a
correção para no primeiro caso que falha (fail-fast).

### 5.5 Exemplos

Programa (v1, ainda válido):

```json
{
  "id": "steady_echo",
  "name": "Steady Echo",
  "subject": "subject.md",
  "submission": { "filename": "steady_echo.c" },
  "execution": { "type": "program_output" },
  "tests": { "generator": "random_arguments", "expectation": "echo_arguments" },
  "limits": { "timeout_seconds": 2 }
}
```

Função com harness (v1, `function_with_main`):

```json
{
  "id": "sum_values",
  "name": "Sum Values",
  "subject": "subject.md",
  "submission": { "filename": "sum_values.c" },
  "execution": { "type": "function_with_main", "fixture": "fixtures/main.c" },
  "tests": { "generator": "random_int_array", "expectation": "sum_integers" }
}
```

Função com referência (v2):

```json
{
  "schema_version": 2,
  "id": "sum_values",
  "name": "Sum Values",
  "subject": "subject.md",
  "topics": ["arrays"],
  "submission": { "filename": "sum_values.c" },
  "execution": { "type": "function_call", "harness": "harness/main.c" },
  "reference": { "source": "solution/sum_values.c", "harness": "harness/main.c" },
  "tests": { "generator": "random_int_array", "expectation": "reference_output" },
  "limits": { "timeout_seconds": 2 }
}
```

## 6. subject.md

Texto simples ou Markdown no formato de prova. A UI mostra em fonte monoespaçada e
preserva espaços e quebras de linha. A linha `Expected files` deve bater com
`submission.filename`.

```text
Assignment name  : steady_echo
Expected files   : steady_echo.c
Allowed functions: write
--------------------------------------------------------------------------------

Write a program that displays all command-line arguments on a single line,
separated by exactly one space, followed by a newline.

$> ./steady_echo hello world | cat -e
hello world$
```

## 7. Linguagens

| Linguagem | `language` | `function_call` | Requisito na máquina |
| --- | --- | --- | --- |
| C | `c` | harness do pack | compilador C compatível (gcc/clang/MinGW) |
| Python | `python` | harness do app (`entry` + `args_format`) | Python 3.9+ instalado no sistema |

Python:

- o app usa o Python INSTALADO no computador (`py -3`, `python3` ou `python` do PATH, ou o
  executável escolhido em `Configurações > Python`), validado rodando o interpretador de
  verdade. O executável do app nunca é usado como Python;
- a submissão passa por `py_compile` antes de rodar (erro de sintaxe = falha de preparação,
  mostrada no trace);
- execução com `python -I -B -X utf8`: modo isolado (ignora variáveis `PYTHON*`, o site do
  usuário e o diretório atual no `sys.path`), sem `.pyc` na workspace, saída em UTF-8. Isso
  NÃO é sandbox;
- programas (`program_output`) recebem os argumentos do caso em `sys.argv[1:]`.

Exemplo Python (`function_call`):

```json
{
  "schema_version": 2,
  "id": "reverse_text",
  "name": "Reverse Text",
  "subject": "subject.md",
  "submission": { "filename": "reverse_text.py" },
  "execution": { "type": "function_call", "entry": "reverse_text", "args_format": "str" },
  "reference": { "source": "solution/reverse_text.py" },
  "tests": { "generator": "random_string", "expectation": "reference_output" }
}
```

O pack de exemplo `examples/packs/python-basics` usa `program_output` e `function_call`.

Uma linguagem só aparece aqui quando o app tem um runtime para ela. Pack com linguagem não
listada é recusado na importação.

## 8. Validar e importar

1. Crie a pasta do pack ou um `.zip` com ela.
2. Abra `Configurações > Packs` e clique em `Importar Pack`.
3. O app valida `pack.json`, cada `exercise.json`, os arquivos declarados e as capabilities.
4. Se o pack tiver código executável, o app lista os arquivos e pede confirmação.
5. O pack é copiado para a pasta gerenciada e aparece em Treino e Prova.

## 9. Progresso

O progresso é guardado por `(pack_id, exercise_id)`: o mesmo id de exercício em dois packs
são dois exercícios. Só tentativas de treino contam para o progresso pedagógico;
tentativas de prova ficam no histórico.
