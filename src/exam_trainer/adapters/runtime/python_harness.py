"""Harness do APP para `function_call` em Python.

Uso: python -I -B -X utf8 <este arquivo> <submissão.py> <entry> <args_format> [args...]

- carrega a submissão como módulo (sem ser __main__);
- converte cada argumento do caso conforme `args_format`:
    json -> json.loads(arg)   (números, listas, strings com aspas, true/false/null)
    str  -> o texto como está
- chama entry(*args) e, se o retorno não for None, imprime json.dumps(retorno) + "\n"
  (valores não serializáveis em JSON são impressos com repr).

O texto abaixo (HARNESS_SOURCE) é gravado na pasta .build da workspace. Ele fica como
string (e não como módulo importável) porque dentro do executável do PyInstaller os
módulos não existem como arquivos.
"""

HARNESS_SOURCE = r'''
import importlib.util
import json
import sys


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: harness <submission.py> <entry> <args_format> [args...]", file=sys.stderr)
        return 2
    submission, entry, args_format, raw_args = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
    spec = importlib.util.spec_from_file_location("submission", submission)
    if spec is None or spec.loader is None:
        print(f"cannot load submission: {submission}", file=sys.stderr)
        return 2
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, entry, None)
    if not callable(function):
        print(f"function not found in submission: {entry}", file=sys.stderr)
        return 2
    if args_format == "json":
        try:
            args = [json.loads(value) for value in raw_args]
        except json.JSONDecodeError as error:
            print(f"invalid JSON argument: {error}", file=sys.stderr)
            return 2
    else:
        args = list(raw_args)
    result = function(*args)
    if result is not None:
        try:
            text = json.dumps(result, ensure_ascii=False)
        except (TypeError, ValueError):
            text = repr(result)
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
