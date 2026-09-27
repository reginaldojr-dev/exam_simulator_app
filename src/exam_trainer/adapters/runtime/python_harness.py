"""App-provided harness for Python `function_call`.

Usage: python -I -B -X utf8 <this file> <submission.py> <entry> <args_format> [args...]

- loads the submission as a module, not as __main__;
- converts each case argument according to `args_format`:
    json -> json.loads(arg)   (numbers, lists, quoted strings, true/false/null)
    str  -> the text as-is
- calls entry(*args) and, if the return value is not None, prints
  json.dumps(return_value) + "\n" (values that are not JSON-serializable are
  printed with repr).

The text below (HARNESS_SOURCE) is written into the workspace .build folder. It
stays as a string, not an importable module, because inside the PyInstaller
executable modules do not exist as files.
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
