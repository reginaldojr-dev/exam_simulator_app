# ADR 0004 — Código de pack é executável; não há sandbox

- Status: Aceita (roadmap passo 1)

## Decisão

- Fixtures e references de um pack são compilados e EXECUTADOS com as permissões do usuário.
  O app não tem sandbox e não finge ter.
- A importação nunca executa nada: só lê JSON e verifica caminhos.
- A importação recusa ids inseguros, caminhos absolutos/drive/UNC/`..`, qualquer escape da
  raiz do pack ou do diretório gerenciado (conferido com `resolve()`), symlinks/junctions,
  ZIPs com entradas inseguras, symlinks ou tamanho excessivo.
- Antes de importar um pack com código executável a UI lista os arquivos e pede confirmação.
