Conte argumentos de linha de comando em um script Python.

## Arquivo esperado

`count_args.py`

## Comportamento esperado
- Imprima `len(sys.argv) - 1` seguido de newline.
- Não leia stdin.
- Não escreva texto extra.

## Permitido
- `sys`

## Não permitido
- `input`

## Exemplos

Entrada/args: `python count_args.py a b`

Saída:

```text
2
```
