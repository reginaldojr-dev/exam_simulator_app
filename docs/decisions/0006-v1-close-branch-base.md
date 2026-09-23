# ADR 0006 — Base da branch `v1/close` e blobs com LF

- Status: Aceita (roadmap de fechamento da V1, sessão S0)

## Contexto

- A série do roadmap anterior (11 commits) nunca foi aplicada no repositório local: não existia `roadmap/execution`.
- Nesse meio tempo foi criada a branch `v1/packs` a partir de `visual-redesign`, com:
  - as regras de `.gitignore` para packs privados;
  - o commit do branding da Home ("EXAM TRAINER").
- A branch foi enviada ao remoto.
- O repositório guarda os arquivos com LF (conversão automática de fim de linha no Windows). A série anterior tinha sido preparada sobre um espelho com CRLF no `.spec` e no `rank02-practice`, e a conferência do manifesto do script antigo recusaria a aplicação.

## Decisão

1. `v1/close` nasce de `v1/packs` (0a7b28c), que já contém o branding e as regras de ignore.
2. A série anterior é refeita sobre um espelho idêntico ao índice local (275 arquivos, todos os blobs conferidos) e entregue junto com a S0, na mesma aplicação.
3. Arquivos de texto são versionados com LF. O script de aplicação não força CRLF.

## Consequências

- **Pacote antigo inválido:** o conjunto `Claude outputs/roadmap/` (script e patches antigos) fica obsoleto e não deve ser usado. A entrega válida é `Claude outputs/v1-close/S0/`.
- **Ordem das branches:** a `v1/packs` atual passa a ser ancestral de `v1/close`. Quando o prompt de geração de packs rodar (depois da S4), a `v1/packs` local é avançada por fast-forward até a ponta de `v1/close`, sem perder nenhum commit. O remoto não é tocado, porque nada faz push.
