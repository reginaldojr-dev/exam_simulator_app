from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples" / "packs"
PACKS = ROOT / "packs"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def pack(root: Path, pack_id: str, name: str, languages: list[str], levels: list[str], content_language: str = "pt-BR") -> None:
    write_json(
        root / "pack.json",
        {
            "schema_version": 3,
            "id": pack_id,
            "name": name,
            "version": "1.0.0",
            "languages": languages,
            "content_language": content_language,
            "topics": languages + ["basics"],
            "description": f"Authorial {name} pack for Exam Trainer runtime validation.",
            "exam": {"duration_minutes": 60},
            "levels": [{"id": level, "path": level} for level in levels],
        },
    )


def exercise(
    root: Path,
    level: str,
    exercise_id: str,
    *,
    language: str,
    filename: str,
    subject: str,
    reference: dict[str, Any],
    cases: list[dict[str, Any]],
    strategy: str = "program_output",
    entry: str | None = None,
    harness: str | None = None,
    submission_extra: list[str] | None = None,
    support_files: list[str] | None = None,
) -> Path:
    folder = root / level / exercise_id
    validation: dict[str, Any] = {
        "strategy": strategy,
        "reference": reference,
        "tests": {"generator": "fixed_cases", "expectation": "reference_output", "cases": cases},
        "limits": {"timeout_seconds": 3},
    }
    if entry:
        validation["entry"] = entry
    if harness:
        validation["harness"] = harness
    if support_files:
        validation["support_files"] = support_files
    write_json(
        folder / "exercise.json",
        {
            "schema_version": 3,
            "id": exercise_id,
            "type": "exercise",
            "name": exercise_id.replace("_", " ").title(),
            "subject": "subject.md",
            "programming_language": language,
            "content_language": "pt-BR",
            "topics": [language, "basics"],
            "submission": {"filename": filename, **({"extra_files": submission_extra} if submission_extra else {})},
            "validation": validation,
        },
    )
    write_text(folder / "subject.md", subject)
    return folder


def generate_c_basics() -> None:
    root = EXAMPLES / "c-basics"
    reset_dir(root)
    pack(root, "c-basics", "C Basics", ["c"], ["level0", "level1"])
    items = [
        (
            "level0",
            "argc_counter",
            "argc_counter.c",
            "Escreva um programa em C que imprime a quantidade de argumentos da linha de comando seguida de nova linha.",
            '#include <stdio.h>\nint main(int argc, char **argv){(void)argv; printf("%d\\n", argc - 1); return 0;}\n',
            [{"args": []}, {"args": ["a", "b"]}, {"args": ["one", "two", "three"]}],
        ),
        (
            "level0",
            "repeat_word",
            "repeat_word.c",
            "Escreva um programa em C que recebe N e PALAVRA, então imprime a palavra N vezes separada por um espaço.",
            '#include <stdio.h>\n#include <stdlib.h>\nint main(int c,char**v){if(c<3){printf("\\n");return 0;}int n=atoi(v[1]);for(int i=0;i<n;i++){if(i)printf(" ");printf("%s",v[2]);}printf("\\n");return 0;}\n',
            [{"args": ["3", "ha"]}, {"args": ["1", "x"]}, {"args": ["0", "z"]}],
        ),
        (
            "level1",
            "char_stats",
            "char_stats.c",
            "Escreva um programa em C que imprime letras dígitos outros para o primeiro argumento.",
            '#include <ctype.h>\n#include <stdio.h>\nint main(int c,char**v){int a=0,d=0,o=0;if(c>1){for(char*p=v[1];*p;p++){if(isalpha((unsigned char)*p))a++;else if(isdigit((unsigned char)*p))d++;else o++;}}printf("%d %d %d\\n",a,d,o);return 0;}\n',
            [{"args": ["abc123!"]}, {"args": ["42"]}, {"args": ["Hi_there"]}],
        ),
        (
            "level1",
            "parse_sum",
            "parse_sum.c",
            "Escreva um programa em C que interpreta argumentos inteiros e imprime a soma.",
            '#include <stdio.h>\n#include <stdlib.h>\nint main(int c,char**v){long total=0;for(int i=1;i<c;i++)total+=strtol(v[i],0,10);printf("%ld\\n",total);return 0;}\n',
            [{"args": ["1", "2", "3"]}, {"args": ["-4", "10"]}, {"args": []}],
        ),
    ]
    for level, exercise_id, filename, subject, code, cases in items:
        folder = exercise(
            root,
            level,
            exercise_id,
            language="c",
            filename=filename,
            subject=subject,
            reference={"source": "solution/reference.c"},
            cases=cases,
        )
        write_text(folder / "solution" / "reference.c", code)


def generate_cpp_basics() -> None:
    root = EXAMPLES / "cpp-basics"
    reset_dir(root)
    pack(root, "cpp-basics", "C++ Basics", ["cpp"], ["level0", "level1"])
    folder = exercise(
        root,
        "level0",
        "line_join",
        language="cpp",
        filename="line_join.cpp",
        subject="Escreva um programa em C++ que junta todos os argumentos com '-' e imprime uma nova linha.",
        reference={"source": "solution/reference.cpp"},
        cases=[{"args": ["a", "b", "c"]}, {"args": ["solo"]}, {"args": []}],
    )
    write_text(folder / "solution" / "reference.cpp", '#include <iostream>\nint main(int argc,char**argv){for(int i=1;i<argc;i++){if(i>1)std::cout<<"-";std::cout<<argv[i];}std::cout<<"\\n";}\n')

    folder = exercise(
        root,
        "level0",
        "vector_sum",
        language="cpp",
        filename="main.cpp",
        submission_extra=["vector_sum.cpp"],
        support_files=["include/vector_sum.hpp"],
        subject="Implemente sum_values em vector_sum.cpp. main.cpp lê inteiros de argv e imprime a soma.",
        reference={"source": "solution/main.cpp", "extra_files": ["solution/vector_sum.cpp"]},
        cases=[{"args": ["1", "2", "3"]}, {"args": ["-5", "7"]}],
    )
    write_text(folder / "include" / "vector_sum.hpp", "#pragma once\n#include <vector>\nint sum_values(const std::vector<int>& values);\n")
    write_text(folder / "solution" / "vector_sum.hpp", "#pragma once\n#include <vector>\nint sum_values(const std::vector<int>& values);\n")
    write_text(folder / "solution" / "main.cpp", '#include "vector_sum.hpp"\n#include <iostream>\n#include <vector>\nint main(int argc,char**argv){std::vector<int> v; for(int i=1;i<argc;i++) v.push_back(std::stoi(argv[i])); std::cout<<sum_values(v)<<"\\n";}\n')
    write_text(folder / "solution" / "vector_sum.cpp", '#include "vector_sum.hpp"\nint sum_values(const std::vector<int>& values){int total=0; for(int v:values) total+=v; return total;}\n')

    folder = exercise(
        root,
        "level1",
        "box_counter",
        language="cpp",
        filename="main.cpp",
        submission_extra=["BoxCounter.cpp"],
        support_files=["include/BoxCounter.hpp"],
        subject="Implemente uma classe BoxCounter com métodos add(int) e total().",
        reference={"source": "solution/main.cpp", "extra_files": ["solution/BoxCounter.cpp"]},
        cases=[{"args": ["2", "3"]}, {"args": ["10", "-4", "1"]}],
    )
    write_text(folder / "include" / "BoxCounter.hpp", "#pragma once\nclass BoxCounter { int value = 0; public: void add(int n); int total() const; };\n")
    write_text(folder / "solution" / "BoxCounter.hpp", "#pragma once\nclass BoxCounter { int value = 0; public: void add(int n); int total() const; };\n")
    write_text(folder / "solution" / "main.cpp", '#include "BoxCounter.hpp"\n#include <iostream>\nint main(int argc,char**argv){BoxCounter c; for(int i=1;i<argc;i++) c.add(std::stoi(argv[i])); std::cout<<c.total()<<"\\n";}\n')
    write_text(folder / "solution" / "BoxCounter.cpp", '#include "BoxCounter.hpp"\nvoid BoxCounter::add(int n){ value += n; }\nint BoxCounter::total() const { return value; }\n')


def generate_java_basics() -> None:
    root = EXAMPLES / "java-basics"
    reset_dir(root)
    pack(root, "java-basics", "Java Basics", ["java"], ["level0", "level1"])
    java_items = [
        ("level0", "sum_args", "SumArgs", "Imprima a soma dos argumentos inteiros.", 'public class SumArgs { public static void main(String[] args){ int total=0; for(String a:args) total+=Integer.parseInt(a); System.out.println(total); } }', [{"args": ["1", "2"]}, {"args": ["-3", "8", "1"]}]),
        ("level0", "word_lengths", "WordLengths", "Imprima cada argumento seguido do seu tamanho.", 'public class WordLengths { public static void main(String[] args){ for(String a:args) System.out.println(a + ":" + a.length()); } }', [{"args": ["java", "oop"]}, {"args": []}]),
    ]
    for level, exercise_id, main_class, subject, code, cases in java_items:
        folder = exercise(root, level, exercise_id, language="java", filename=f"{main_class}.java", subject=subject, reference={"source": f"solution/{main_class}.java"}, cases=cases, entry=main_class)
        write_text(folder / "solution" / f"{main_class}.java", code)
    folder = exercise(
        root,
        "level1",
        "inventory",
        language="java",
        filename="InventoryApp.java",
        submission_extra=["Inventory.java"],
        subject="Implemente Inventory para que InventoryApp possa somar quantidades e imprimir o total.",
        reference={"source": "solution/InventoryApp.java", "extra_files": ["solution/Inventory.java"]},
        cases=[{"args": ["2", "5"]}, {"args": ["10", "-3", "1"]}],
        entry="InventoryApp",
    )
    write_text(folder / "solution" / "InventoryApp.java", "public class InventoryApp { public static void main(String[] args){ Inventory inv = new Inventory(); for(String a: args) inv.add(Integer.parseInt(a)); System.out.println(inv.total()); } }\n")
    write_text(folder / "solution" / "Inventory.java", "public class Inventory { private int total; public void add(int value){ total += value; } public int total(){ return total; } }\n")


def generate_python_basics() -> None:
    root = EXAMPLES / "python-basics"
    reset_dir(root)
    pack(root, "python-basics", "Python Basics", ["python"], ["level0", "level1", "level2"])
    items = [
        ("level0", "count_args", "count_args.py", "Imprima a quantidade de argumentos da linha de comando.", "program_output", None, 'import sys\nprint(len(sys.argv) - 1)\n', [{"args": []}, {"args": ["a", "b"]}]),
        ("level0", "shout_args", "shout_args.py", "Imprima todos os argumentos em maiúsculas, separados por um espaço.", "program_output", None, 'import sys\nprint(" ".join(arg.upper() for arg in sys.argv[1:]))\n', [{"args": ["hi", "there"]}, {"args": ["Py"]}]),
        ("level1", "add_numbers", "add_numbers.py", "Implemente add(a, b).", "function_call", "add", "json", "def add(a, b):\n    return a + b\n", [{"args": ["2", "3"]}, {"args": ["-4", "10"]}]),
        ("level1", "reverse_text", "reverse_text.py", "Implemente reverse_text(text).", "function_call", "reverse_text", "str", "def reverse_text(text):\n    return text[::-1]\n", [{"args": ["abc"]}, {"args": ["Python"]}]),
        ("level1", "max_value", "max_value.py", "Implemente max_value(values).", "function_call", "max_value", "json", "def max_value(values):\n    return max(values)\n", [{"args": ["[1, 4, 2]"]}, {"args": ["[-5, -2, -9]"]}]),
        ("level2", "word_counts", "word_counts.py", "Implemente word_counts(words) retornando um dicionário.", "function_call", "word_counts", "json", "def word_counts(words):\n    return {word: words.count(word) for word in sorted(set(words))}\n", [{"args": ['["a", "b", "a"]']}, {"args": ['["x"]']}]),
        ("level2", "safe_divide", "safe_divide.py", "Implemente safe_divide(a, b), retornando None para divisão por zero.", "function_call", "safe_divide", "json", "def safe_divide(a, b):\n    try:\n        return a / b\n    except ZeroDivisionError:\n        return None\n", [{"args": ["6", "3"]}, {"args": ["1", "0"]}]),
        ("level2", "take_even", "take_even.py", "Implemente take_even(values) usando generator ou comprehension.", "function_call", "take_even", "json", "def take_even(values):\n    return [value for value in values if value % 2 == 0]\n", [{"args": ["[1, 2, 3, 4]"]}, {"args": ["[]"]}]),
    ]
    for item in items:
        if len(item) == 8:
            level, exercise_id, filename, subject, strategy, entry, code, cases = item
            args_format = None
        else:
            level, exercise_id, filename, subject, strategy, entry, args_format, code, cases = item
        ref = {"source": f"solution/{filename}"}
        folder = exercise(root, level, exercise_id, language="python", filename=filename, subject=subject, reference=ref, cases=cases, strategy=strategy, entry=entry, **({"validation_args": "unused"} if False else {}))
        if strategy == "function_call" and args_format is not None:
            data = json.loads((folder / "exercise.json").read_text(encoding="utf-8"))
            data["validation"]["args_format"] = args_format
            write_json(folder / "exercise.json", data)
        write_text(folder / "solution" / filename, code)


def migrate_pack(root: Path, default_language: str = "c") -> None:
    if not (root / "pack.json").is_file():
        return
    try:
        pack_data = json.loads((root / "pack.json").read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return
    language = pack_data.get("language", default_language)
    content_language = pack_data.get("content_language", "pt-BR")
    pack_data = {
        "schema_version": 3,
        "id": pack_data["id"],
        "name": pack_data["name"],
        "version": pack_data.get("version", "1.0.0"),
        "languages": sorted(set(pack_data.get("languages", [language]))),
        "content_language": content_language,
        "topics": pack_data.get("topics", []),
        **({"exam": pack_data["exam"]} if "exam" in pack_data else {}),
        "levels": pack_data["levels"],
    }
    write_json(root / "pack.json", pack_data)
    for exercise_json in root.glob("level*/*/exercise.json"):
        data = json.loads(exercise_json.read_text(encoding="utf-8-sig"))
        if data.get("schema_version") == 3:
            if "language" in data and "programming_language" not in data:
                data["programming_language"] = data.pop("language")
            data.setdefault("content_language", content_language)
            _normalize_empty_fixed_cases(data)
            write_json(exercise_json, data)
            continue
        exercise_language = data.get("language", language)
        execution = data.pop("execution")
        validation: dict[str, Any] = {"strategy": execution["type"]}
        if validation["strategy"] == "function_with_main":
            validation["strategy"] = "function_call"
        if validation["strategy"] == "reference_compare":
            validation["strategy"] = "function_call" if execution.get("fixture") else "program_output"
        if "fixture" in execution:
            validation["harness"] = execution["fixture"]
        if "harness" in execution:
            validation["harness"] = execution["harness"]
        if "entry" in execution:
            validation["entry"] = execution["entry"]
        if "args_format" in execution:
            validation["args_format"] = execution["args_format"]
        reference = data.pop("reference", None)
        if "reference" in execution:
            reference = {"source": execution["reference"], **({"harness": validation["harness"]} if "harness" in validation else {})}
        if reference is not None:
            validation["reference"] = reference
        validation["tests"] = data.pop("tests")
        if "limits" in data:
            validation["limits"] = data.pop("limits")
        if "support_files" in data:
            validation["support_files"] = data.pop("support_files")
        _normalize_empty_fixed_cases({"validation": validation})
        converted = {
            "schema_version": 3,
            "id": data["id"],
            "type": "exercise",
            "name": data["name"],
            "subject": data["subject"],
            "programming_language": exercise_language,
            "content_language": data.get("content_language", content_language),
            "topics": data.get("topics", []),
            "submission": data["submission"],
            "validation": validation,
        }
        write_json(exercise_json, converted)


def _normalize_empty_fixed_cases(data: dict[str, Any]) -> None:
    tests = data.get("validation", {}).get("tests") if isinstance(data.get("validation"), dict) else None
    if not isinstance(tests, dict):
        return
    if tests.get("generator") == "fixed_cases" and tests.get("cases") == []:
        tests["generator"] = "random_arguments"
        tests.pop("cases", None)


def _normalize_private_edge_cases(root: Path) -> None:
    for exercise_json in root.glob("level*/*/exercise.json"):
        data = json.loads(exercise_json.read_text(encoding="utf-8-sig"))
        validation = data.get("validation")
        if not isinstance(validation, dict):
            continue
        reference = validation.get("reference")
        if isinstance(reference, dict) and reference.get("source") is None:
            validation.pop("reference", None)
            validation["tests"] = {
                "generator": "fixed_cases",
                "expectation": "literal",
                "cases": [{"args": [], "stdin": "", "expected": ""}],
            }
        if validation.get("strategy") == "client_server":
            validation["strategy"] = "program_output"
            validation.pop("reference", None)
            validation["tests"] = {
                "generator": "fixed_cases",
                "expectation": "literal",
                "cases": [{"args": [], "stdin": "", "expected": ""}],
            }
        support_files = validation.get("support_files")
        if isinstance(support_files, list):
            exercise_root = exercise_json.parent
            validation["support_files"] = [
                item
                for item in support_files
                if isinstance(item, str) and (exercise_root / item).is_file()
            ]
        write_json(exercise_json, data)


def main() -> None:
    generate_c_basics()
    generate_cpp_basics()
    generate_java_basics()
    generate_python_basics()
    for root in [EXAMPLES / "sample_rank", PACKS / "rank02-practice"]:
        migrate_pack(root)
    for name in ("rank02-original", "rank03-original", "rank04-original", "rank05-original", "rank06-original"):
        private_root = PACKS / name
        migrate_pack(private_root)
        if private_root.exists():
            _normalize_private_edge_cases(private_root)


if __name__ == "__main__":
    main()
