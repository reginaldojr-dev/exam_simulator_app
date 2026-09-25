Percorra o primeiro argumento e conte letras minúsculas, letras maiúsculas, dígitos e outros caracteres.

## Arquivo esperado

`char_stats.c`

## Comportamento esperado
- Imprima quatro números: `lower upper digit other`.
- Se não houver argumento, todos os contadores devem ser zero.
- Considere apenas ASCII.

## Permitido
- `write`

## Não permitido
- `printf`
- `isalpha`
- `isdigit`

## Exemplos

Entrada/args: `./char_stats abc123!`

Saída:

```text
3 0 3 1
```
