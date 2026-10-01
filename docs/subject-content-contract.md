# Contrato de conteúdo do subject — Markdown vs. metadata estruturada

Este documento é para quem escreve packs (oficiais ou externos). Ele explica a
divisão de responsabilidade entre `subject.md` (texto pedagógico) e
`exercise.json` (metadata técnica estruturada) para o que a sidebar do
exercício exibe hoje: arquivo esperado, funções/recursos permitidos e
proibidos.

Ele não depende de tema visual ou do layout atual da tela de exercício —
descreve o contrato de **conteúdo**, não a apresentação. Para o schema JSON
completo (todos os campos de `exercise.json`/`pack.json`), veja
`src/rankeddojo/resources/pack-contract.md`; este documento foca só na parte
"o que vai em Markdown vs. o que vai em metadata" e no comportamento da UI.

## Por que isso existe

A sidebar da tela de exercício mostra três blocos técnicos curtos: **arquivo
esperado**, **permitido** e **não permitido**. Até esta mudança, "permitido"
e "não permitido" só existiam como texto dentro do `subject.md`, extraído por
um parser best-effort de headings (`## Permitido`, `## Not allowed`, etc.).
Isso tem dois problemas: depende do autor escrever um dos headings
reconhecidos (em um idioma específico), e texto localizado não deveria
determinar lógica/apresentação estrutural da UI.

`exercise.json` já suporta um campo `usage` estruturado (ver
`pack-contract.md`). Este documento formaliza que **packs novos devem usar
esse campo**, e explica o que acontece quando ele não existe.

## O que fica no Markdown (`subject.md`)

Texto pedagógico, livre, em qualquer formatação Markdown:

- objetivo do exercício;
- comportamento esperado, passo a passo;
- regras explicativas e raciocínio;
- exemplos de entrada/saída;
- observações e dicas.

O Markdown continua a fonte única para todo esse conteúdo — nada disso vira
metadata estruturada nesta mudança.

## O que fica em metadata (`exercise.json`)

Fatos técnicos curtos e estáveis que a UI apresenta como blocos/tags:

| Informação | Campo | Fonte |
|---|---|---|
| Arquivo esperado | `submission.filename` | já existia, sem mudança |
| Permitido | `usage.allowed.<categoria>` | estruturado (este contrato) |
| Não permitido | `usage.forbidden.<categoria>` | estruturado (este contrato) |

`usage.allowed`/`usage.forbidden` agrupam por categoria (`functions`,
`libraries`, `imports`, `headers`, `apis`, `flags`) — todas opcionais, todas
listas de strings não vazias, em inglês/neutras de locale (ex.: `"write"`,
`"printf"`, não a tradução de "escreva"). A sidebar mostra todas as
categorias concatenadas, na ordem acima; se seu exercício só usa uma
categoria (o caso comum é `functions`), as outras simplesmente ficam de fora.

Nada em `usage` é executado, interpolado ou usado como política de grading —
é puramente declarativo/pedagógico. Um validator futuro pode escolher
verificar um subconjunto disso, mas isso é fora do escopo deste contrato.

### Por que não duplicar `submission.filename`

O arquivo esperado já tem uma fonte estruturada única (`submission.filename`).
Não existe um campo paralelo "expected files" neste contrato — se um
exercício precisar de múltiplos arquivos do aluno no futuro, isso é extensão
de `submission` (que já tem `extra_files` para arquivos auxiliares), não um
novo conceito de metadata de conteúdo.

## Campos opcionais e validação

Todo o objeto `usage` é opcional, assim como cada categoria dentro de
`allowed`/`forbidden`. Regras do loader (`json_loader.py`):

- campo `usage` ausente → válido, equivalente a tudo vazio;
- lista vazia (`"functions": []`) → válida;
- cada item da lista precisa ser uma string não vazia (depois de `.strip()`);
  qualquer outro tipo, ou string vazia/só espaços, é rejeitado;
- a ordem declarada no JSON é preservada até a UI;
- nada é executado ou avaliado — são apenas strings.

## Fallback para packs antigos (sem `usage`)

Packs escritos antes deste contrato (ou packs externos que ainda não o
adotaram) podem continuar usando headings no `subject.md`:

```markdown
## Permitido
- `write`

## Não permitido
- `printf`
```

O parser que lê esses headings (`subject_sections.py`) continua funcionando,
mas é explicitamente um **fallback de compatibilidade legado** — não ganha
novos heading reconhecidos nem fica "mais esperto". A direção para conteúdo
novo é sempre o campo `usage`.

Prioridade exata que a UI aplica, por bloco (permitido / não permitido,
independentemente):

1. `usage.allowed` / `usage.forbidden` estruturado, se não estiver vazio;
2. senão, o parser legado de headings do `subject.md`;
3. se nenhuma das duas fontes tiver dado nada, o bloco correspondente fica
   oculto na sidebar (nunca mostra vazio nem inventa conteúdo).

Isso significa: se um exercício tiver as duas fontes (por exemplo, um pack
antigo que ainda não removeu os headings), **a estruturada sempre vence**,
mesmo que o texto do Markdown diga outra coisa.

## `schema_version`

Nenhuma mudança de versão foi necessária. `usage` já é um campo válido desde
`schema_version: 3` (compatível/opcional) — ver `pack-contract.md`. Packs
`schema_version: 1`/`2` simplesmente não têm esse campo e usam o fallback
legado acima.

## Exemplo mínimo de `exercise.json`

```json
{
  "schema_version": 3,
  "id": "char_stats",
  "type": "exercise",
  "name": "Char Stats",
  "subject": "subject.md",
  "programming_language": "c",
  "content_language": "pt-BR",
  "submission": { "filename": "char_stats.c" },
  "usage": {
    "allowed": { "functions": ["write"] },
    "forbidden": { "functions": ["printf", "isalpha", "isdigit"] }
  },
  "validation": {
    "strategy": "program_output",
    "tests": { "generator": "fixed_cases", "expectation": "literal", "cases": [] },
    "limits": { "timeout_seconds": 3 }
  }
}
```

## Exemplo de `subject.md` correspondente

Quando `usage` já está estruturado, o Markdown não precisa repetir
"Permitido"/"Não permitido" — só o conteúdo pedagógico:

```markdown
Percorra o primeiro argumento e conte letras minúsculas, maiúsculas, dígitos
e outros caracteres.

## Arquivo esperado

`char_stats.c`

## Comportamento esperado
- Imprima quatro números: `lower upper digit other`.
- Se não houver argumento, todos os contadores devem ser zero.
- Considere apenas ASCII.

## Exemplos

Entrada/args: `./char_stats abc123!`

Saída:

```text
3 0 3 1
```
```

(Este é, literalmente, o `char_stats` real do pack `c-basics`, usado como
piloto desta migração.)

## Comportamento da UI (resumo)

- "Expected file" vem sempre de `submission.filename` — nunca muda.
- "Permitido" / "Não permitido": estruturado primeiro, fallback legado
  depois, bloco oculto se nenhuma fonte tiver dado.
- Os rótulos dos blocos ("Permitido", "Not allowed", etc.) passam por i18n
  normalmente. Os **valores técnicos** (`write`, `printf`, ...) nunca são
  traduzidos — são identificadores, não texto de interface.
- A UI só lê esses valores através dos modelos de domínio normais
  (`ExerciseDefinition.usage` via `ActiveExercise.ref.definition.usage`) —
  nunca lê o JSON do pack diretamente.
