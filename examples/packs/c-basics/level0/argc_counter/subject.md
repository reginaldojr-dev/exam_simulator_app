# argc_counter

Crie um programa que conte quantos argumentos foram passados pela linha de comando, desconsiderando o nome do executável.

## Arquivo esperado

`argc_counter.c`

## Comportamento esperado
- Imprima apenas um número decimal seguido de `\n`.
- Sem argumentos adicionais, imprima `0`.
- Não leia da entrada padrão.

## Permitido
- `write`

## Não permitido
- `printf`
- `puts`

## Exemplos

Entrada/args: `./argc_counter`

Saída:

```text
0
```

Entrada/args: `./argc_counter a b c`

Saída:

```text
3
```
