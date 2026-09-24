# Handoff Exam Trainer

## Estado atual
- Branch atual: `v1/close`
- HEAD atual: `1f29492ea494a1b236135156d6e64a6dae5b7312` (conforme reportado por você; confirmado indiretamente por bater com o blob hash real de `src/exam_trainer/application/mvp_models.py`)
- Working tree: limpa (conforme reportado por você)
- Remoto: `origin/v1/close` sincronizada com a local (conforme reportado por você)
- Última sessão realmente concluída e aplicada no repositório real: **S0**

## O que já foi feito
- Branch `v1/close` criada a partir de `v1/packs` (0a7b28c), com a série anterior refeita sobre essa base + commits da S0 (ADR 0006).
- `tests/test_architecture.py` criado na S0 com 12 testes; 6 registrados em `KNOWN_VIOLATIONS` como `expectedFailure` (5 atribuídas à S1, 1 à S2).
- Um script de remoção de trailers `Co-authored-by: Claude`/`Claude-Session` (`remove-claude-trailers-v1-close.ps1` v2) foi entregue em sessão anterior. **O resultado real da execução desse script nunca foi confirmado por você** — não sei se foi rodado, nem o resultado. Trate como pendente de confirmação.
- Patches da S1 foram **regenerados do zero** contra a árvore real (`1f29492e...`) e testados por mim de forma isolada (worktree limpo, fora do seu computador) — ver seção S1. **Ainda não foram aplicados no seu repositório real.**

## S0
- Status: concluída e presente no histórico de `v1/close`.
- O que foi concluído: linha de base medida, testes de arquitetura criados (12 testes, 6 `KNOWN_VIOLATIONS`), ADR 0006 (base da branch `v1/close`).
- Commits principais: commit único de base do `v1/close` (ponta reportada por você como `1f29492e...` inclui S0; hash exato do commit de S0 isoladamente não foi confirmado por mim neste repositório).

## S1
- Status atual: **patches prontos, mas não aplicados no seu repositório real.**
- Se foi aplicada: **não**. Antes desta última rodada, os arquivos reais (`main_window.py`, `mvp_coordinator.py`, `runtime_registry.py`, `project-status.md`, `test_architecture.py`) foram conferidos via staging do seu computador e confirmaram que nenhuma mudança da S1 estava presente, apesar de um relato anterior de que a S1 estaria concluída.
- Base correta: `v1/close @ 1f29492ea494a1b236135156d6e64a6dae5b7312`.
- HEAD correto: ainda não existe — só existirá depois que você aplicar os patches localmente. (Em teste isolado, meu ambiente chegou a um HEAD `6ab3307`, mas esse hash **não é o hash real que vai aparecer no seu repositório**, porque metadados de commit — data do committer — diferem por ambiente. O hash real só se conhece depois de aplicar aí.)
- Problema encontrado (causa raiz, já corrigida nesta rodada): seu repositório usa `core.autocrlf=true` (Windows) e guarda blobs normalizados para LF; o espelho antigo usado para gerar patches (ambiente Linux) guardava CRLF cru, gerando SHAs de blob que não existiam no seu banco de objetos real. Isso causava `sha1 information is lacking or useless` / `could not build fake ancestor` no `git am --3way`. Os patches novos foram gerados com normalização LF equivalente ao `core.autocrlf=true`, e o hash calculado para `mvp_models.py` bateu exatamente com o hash que você reportou do seu repositório real.
- Quais patches/scripts existem (atuais, em `Claude outputs/v1-close/S1/`):
  - `apply-v1-close-S1.ps1` — não alterado nesta rodada.
  - `base-manifest.tsv` — regenerado contra a árvore real.
  - `patches/0001` a `0006` (mesmos 6 nomes de antes) — conteúdo regenerado do zero contra `1f29492e...`.
- Quais estão obsoletos: os patches que existiam nessa pasta antes desta entrega (gerados contra um espelho com base incompleta/CRLF divergente) — já substituídos pelos novos.
- Exatamente o que falta para concluir S1:
  1. Rodar `-DryRun`.
  2. Se OK, aplicar de verdade.
  3. Rodar a suíte completa no seu ambiente (o próprio script já faz isso).
  4. Confirmar visualmente que as 5 violações da S1 saíram de `KNOWN_VIOLATIONS` e que a suíte não regrediu.
  5. Só depois disso considerar push (não incluído no escopo dos scripts).

## S2
- Status atual: patches antigos existentes em `Claude outputs/v1-close/S2/` estão **obsoletos** — foram gerados contra uma base da S1 que nunca correspondeu ao estado real.
- Por que não pode ser aplicada ainda: depende do HEAD real pós-S1, que só existe depois que você aplicar os patches da S1 no seu repositório. Sem esse HEAD real, qualquer patch de S2 gerado agora ficaria errado do mesmo jeito que os da S1 estavam.
- O que precisa ser regenerado depois da S1: toda a série de patches da S2 (código + `base-manifest.tsv` + validação), usando como base o HEAD real resultante da aplicação da S1 no seu computador — não o HEAD de nenhum ambiente de teste isolado.

## Próximas sessões
- S2: runtimes, estratégias de execução, toolchains e prontidão (linguagem).
- S3: contrato de pack, validador e segurança de execução.
- S4: persistência, IDs, eventos de progresso e deep links.
- S5: UI responsiva, temas e componentes.
- S6: build, licença, documentação, limpeza e fechamento da V1.

## Arquitetura atual
- **domain**: modelos e regras puras (exercise/pack definitions, grading, identifiers, attempt modes, workspace). Hoje `domain/workspace.py` ainda importa `pathlib.Path` concreto (I/O) — violação prevista para sair na S1.
- **application**: `MVPTrainerCoordinator` (649 linhas, ~48 métodos públicos) concentra a maior parte da lógica; ainda importa adapters concretos (`adapters.editor`, `adapters.runtime.c_runtime`) e mexe em arquivo (`shutil`, `Path.rename`) diretamente — violações previstas para sair na S1.
- **ports**: compiler, config, editor, grader, pack, progress, runtime, workspace. `ports/progress_repository.py` hoje importa `ProgressEntry` de `application.mvp_models` — inverte a regra "port só depende de domain" — violação da S1.
- **adapters**: compiler, editor, exercise_definition, filesystem, grader, pack, persistence, runtime, workspace, UI (Qt).
- **infrastructure**: `app_factory.py` (composition root), `paths.py`.
- **runtimes**: um runtime por linguagem, registrados em `RuntimeRegistry` (`application/engine/runtime_registry.py`).
- **grader**: `GenericGrader` mora em `adapters/grader/`; arquitetura-alvo o move para `application/grading/` — não faz parte do escopo de violações verificadas na S1, fica para sessão futura.
- **packs**: pacotes públicos de exemplo em `examples/packs/`; packs privados (`rank02..06-original`, etc.) ficam fora do Git.
- **UI**: `main_window.py` (1418 linhas, todas as telas num arquivo só); hoje importa `adapters.editor` e `domain.pack_definition` direto — violação da S1.

**Violações arquiteturais ainda conhecidas** (registradas em `tests/test_architecture.py::KNOWN_VIOLATIONS`, todas ainda presentes no repositório real porque a S1 não foi aplicada):
1. `domain/workspace.py` usa `pathlib.Path` concreto (I/O) — S1.
2. `application/use_cases/mvp_coordinator.py` importa adapters concretos direto — S1.
3. `mvp_coordinator.py` mexe em arquivo direto (`shutil`, `Path.rename`) — S1.
4. `ports/progress_repository.py` importa de `application` — S1.
5. UI (`main_window.py`, `startup_window.py`) importa `domain`/`adapters` direto — S1.
6. `main_window.py` compara `language == DEFAULT_LANGUAGE` fora dos módulos cientes de linguagem — S2.

## Decisões já fechadas
- Nunca incluir `Co-authored-by`, `Claude-Session` ou qualquer assinatura de IA em commits deste projeto — mensagens de commit convencionais simples.
- `main` nunca é reescrita; qualquer reescrita de histórico fica restrita a `v1/close` (ou branches derivadas), sempre com branch de backup antes.
- Nenhum push é feito automaticamente — push é sempre decisão e ação sua.
- Patches são gerados como série `git format-patch`, aplicados com `git am --3way --keep-cr`, validados por um `base-manifest.tsv` de conteúdo (não por hash de commit fixo).
- A causa raiz dos patches da S1 falharem era CRLF/`core.autocrlf`, não os scripts `.ps1` — os scripts de aplicação (`apply-v1-close-S1.ps1`/`S2.ps1`) já estão corretos e não devem ser alterados sem necessidade real.
- Escopo da S1 é exatamente as 5 violações listadas em `KNOWN_VIOLATIONS` com sessão "S1" — a extração completa de services/view models (Obj. 9/10) fica para sessão futura, fora do escopo já verificado.

## Arquivos/scripts importantes
- **Scripts atuais**: `Claude outputs/v1-close/S1/apply-v1-close-S1.ps1`; `Claude outputs/v1-close/S1/base-manifest.tsv` (regenerado); `Claude outputs/v1-close/S1/patches/0001–0006` (regenerados).
- **Scripts obsoletos**: os patches antigos que existiam em `Claude outputs/v1-close/S1/patches/` antes desta rodada (gerados contra base incorreta); toda a pasta `Claude outputs/v1-close/S2/` (patches gerados contra uma S1 que nunca existiu de fato no seu repositório).
- **Patches atuais**: ver "Scripts atuais" acima — série S1, 6 patches.
- **Documentos importantes**: `Claude outputs/prompt-fechamento-v1.md`, `Claude outputs/roadmap-fechamento-v1.md`, `docs/project-status.md`, `docs/decisions/0006-v1-close-branch-base.md` (e 0007, se você já tiver aplicado algo que o crie — confirme no seu repositório).
- **Diretórios privados que não podem ir para o Git** (já no `.gitignore`): `reference/`, `packs/rank02-original/`, `packs/*-original/`, `packs/_private_backup/`, `packs/_private_notes/`, `docs/rank02_analysis.md`, `Claude outputs/`.

## Próximos passos
1. Rodar `-DryRun` do `apply-v1-close-S1.ps1`.
2. Se o DryRun passar sem erro, aplicar a S1 de verdade.
3. Rodar a suíte completa (o script já faz isso automaticamente).
4. Validar que as 5 violações da S1 saíram de `KNOWN_VIOLATIONS` e que não houve regressão nas outras falhas pré-existentes.
5. Decidir sobre push de `v1/close` (ação manual sua).
6. Só depois disso, pedir a regeneração completa da série S2 contra o HEAD real pós-S1.

## Próxima ação
Rodar `.\Claude outputs\v1-close\S1\apply-v1-close-S1.ps1 -DryRun` a partir da raiz do repositório.
