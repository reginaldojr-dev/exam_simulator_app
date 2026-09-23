# Runtimes por linguagem

## Camadas

```text
GenericGrader            casos, expectations, comparação, fail-fast, trace, seeds, política
  └─ ExecutionStrategy   program_output | function_call: QUAIS arquivos formam o programa
       └─ RuntimeRegistry   language -> runtime (único lugar que sabe o que o app executa)
            └─ LanguageRuntime   disponibilidade, preparar (compilar/checar), executar,
                                 stdout/stderr/exit code, timeout
```

- `ports/runtime_port.py`: `LanguageRuntime` (Protocol), `ProgramSpec`, `PreparedProgram`, `ProcessOutcome`.
- `application/engine/execution.py`: estratégias por tipo neutro. Nenhum `if language == ...`.
- `application/engine/runtime_registry.py`: `RuntimeRegistry`.
- `adapters/grader/generic_grader.py`: `GenericGrader`. `GenericCGrader` ficou como wrapper de compatibilidade.
- `adapters/runtime/c_runtime.py`: `CRuntime` (usa o `SystemCCompiler`; o `CompilerPort` fica interno ao runtime).
- `adapters/runtime/python_runtime.py`: `PythonRuntime` (Python do sistema, probe real, `py_compile`, `-I -B -X utf8`).
- `adapters/runtime/python_harness.py`: harness do app para `function_call` em Python (texto gravado na pasta `.build`).
- `adapters/runtime/process.py`: execução de processo comum (lista de argumentos, sem shell, com timeout).

A factory (`infrastructure/app_factory.py`) monta o registry e injeta o mesmo registry no grader e no coordinator.

## Regras de um runtime

1. `is_ready()` nunca roda processo (é chamado na thread da UI). `check_available()` pode rodar (probe) e é chamado em segundo plano.
2. Nada de `shell=True`. Argumentos do caso chegam literalmente ao programa.
3. Timeout sempre aplicado; timeout vira `ProcessOutcome(timed_out=True)`.
4. Não existe sandbox; não finja que existe. O código do aluno e o código do pack rodam com as permissões do usuário.
5. Falha de preparação (compilação/sintaxe) vai para `PreparedProgram.build` (aparece no trace).

## Preflight

O preflight da prova e da correção usa a linguagem do pack (`pack.language`):

- linguagem sem runtime registrado: bloqueia com mensagem ("este app não executa exercícios em X");
- runtime registrado mas indisponível: leva às Configurações daquela ferramenta.

## Como adicionar uma linguagem (roteiro, passo 7)

1. Implementar `LanguageRuntime` em `adapters/runtime/<lang>_runtime.py` (detecção, `prepare`, `run`).
2. Declarar o suporte no contrato: `LanguageSupport` em `application/capabilities.py` (tipos de execução, quem fornece o harness de `function_call`, formatos de argumento).
3. Registrar o runtime na factory.
4. Documentar em `src/exam_trainer/resources/pack-contract.md` (seção Linguagens) e criar um pack autoral mínimo com PASS/FAIL/erro/timeout.
5. Testes: runtime isolado + grader com esse runtime + regressão dos packs C.

## Próximas linguagens (passo 7 — só documentado, nada implementado)

A interface está pronta; nenhuma linguagem além de C e Python é executada hoje. Um pack com
`language` fora de `c`/`python` é recusado na importação.

| Linguagem | Preparação | `function_call` | Pontos de atenção |
| --- | --- | --- | --- |
| C++ | compilar com g++/clang++ (reusar o probe do C) | harness do pack (`main.cpp`) | flags próprias; mesmo formato de saída do C |
| JavaScript (Node) | `node --check` | harness do app (como Python) | detectar `node` do sistema; `--disallow-code-generation-from-strings` não é sandbox |
| Java | `javac` para a pasta `.build` | harness do pack (classe `Main`) ou do app | JDK x JRE; tempo de start da JVM pede timeout maior |
| Shell | `bash -n` | só `program_output` | execução de shell é exatamente o que o app evita: exigir decisão explícita antes |

Decisões que precisam ser tomadas antes de qualquer uma delas: ver ADR 0005.
