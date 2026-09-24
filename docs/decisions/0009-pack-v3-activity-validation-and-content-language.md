# ADR 0009 — Pack v3, Activity/Validation e idioma do conteúdo

## Status

Aceita.

## Contexto

A S3 precisava fechar runtimes obrigatórios, contrato de packs, validação e segurança sem
prender o núcleo ao nome `Exercise` ou ao contrato antigo. Durante a sessão, o roadmap foi
atualizado para separar linguagem de programação de idioma humano do conteúdo.

## Decisão

1. O contrato principal passa a ser `schema_version: 3`.
2. Activities declaram `programming_language` para runtime/toolchain e
   `content_language` para idioma humano do subject/título/instruções.
3. `language` permanece apenas como alias interno/legado durante normalização; packs novos
   usam `programming_language`.
4. `ExerciseDefinition` passa a expor uma representação neutra `ActivityDefinition` com
   `ValidationPlan` e `ValidationStep`.
5. Runtimes expõem `RuntimeDescriptor`; capabilities de linguagens podem ser derivadas dos
   runtimes registrados.
6. `reference.extra_files` e `submission.extra_files` dão suporte a atividades multi-file.
7. Packs autorais de S3 usam `content_language: pt-BR` para provar subject UTF-8 em
   português.

## Consequências

- O loader não depende de inglês nem infere runtime a partir do idioma humano.
- Runtime, execution strategy e grader continuam guiados por `programming_language`.
- C, C++, Python e Java entram pelo mesmo `RuntimePort`/`RuntimeRegistry`.
- O app fica preparado para `StudyIntent` e `PackPromptBuilder` futuros com campos
  separados para linguagem de programação e idioma do conteúdo.
- Formatos antigos ainda são normalizados para proteger testes/migração, mas não são o
  contrato recomendado nem a fonte de verdade da S3.
