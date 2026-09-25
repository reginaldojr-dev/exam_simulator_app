from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
EXAMPLES = ROOT / "examples" / "packs"
PACKS = ROOT / "_local" / "packs"


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


def pack(root: Path, pack_id: str, name: str, languages: list[str], levels: list[str]) -> None:
    write_json(root / "pack.json", {
        "schema_version": 3,
        "id": pack_id,
        "name": name,
        "version": "1.1.0",
        "languages": languages,
        "content_language": "pt-BR",
        "topics": [*languages, "basics", "practice"],
        "description": f"Pack autoral de estudo {name} para o Exam Trainer.",
        "exam": {"duration_minutes": 60},
        "levels": [{"id": level, "path": level} for level in levels],
    })


def md(title: str, objetivo: str, arquivo: str, comportamento: list[str], permitido: list[str], proibido: list[str], exemplos: list[tuple[str, str]], extra: list[str] | None = None) -> str:
    parts = [f"# {title}", "", objetivo, "", "## Arquivo esperado", "", f"`{arquivo}`", "", "## Comportamento esperado"]
    parts += [f"- {item}" for item in comportamento]
    if extra:
        parts += ["", "## Observações", *[f"- {item}" for item in extra]]
    if permitido:
        parts += ["", "## Permitido", *[f"- `{item}`" for item in permitido]]
    if proibido:
        parts += ["", "## Não permitido", *[f"- `{item}`" for item in proibido]]
    if exemplos:
        parts += ["", "## Exemplos"]
        for entrada, saida in exemplos:
            parts += ["", f"Entrada/args: `{entrada}`", "", "Saída:", "", "```text", saida, "```"]
    return "\n".join(parts)


def usage(allowed=None, forbidden=None, constraints=None, style=None, behavior=None, notes=None):
    data: dict[str, Any] = {}
    if allowed:
        data["allowed"] = allowed
    if forbidden:
        data["forbidden"] = forbidden
    if constraints:
        data["constraints"] = constraints
    if style:
        data["style"] = style
    if behavior:
        data["behavior"] = behavior
    if notes:
        data["notes"] = notes
    return data


def exercise(root: Path, level: str, exercise_id: str, *, language: str, filename: str, subject: str, cases: list[dict[str, Any]], usage_data: dict[str, Any], strategy: str = "program_output", entry: str | None = None, args_format: str | None = None, harness: str | None = None, submission_extra: list[str] | None = None, support_files: list[str] | None = None, timeout: int = 3) -> Path:
    folder = root / level / exercise_id
    validation: dict[str, Any] = {
        "strategy": strategy,
        "tests": {"generator": "fixed_cases", "expectation": "literal", "cases": cases},
        "limits": {"timeout_seconds": timeout},
    }
    if entry:
        validation["entry"] = entry
    if args_format:
        validation["args_format"] = args_format
    if harness:
        validation["harness"] = harness
    if support_files:
        validation["support_files"] = support_files
    write_json(folder / "exercise.json", {
        "schema_version": 3,
        "id": exercise_id,
        "type": "exercise",
        "name": exercise_id.replace("_", " ").title(),
        "subject": "subject.md",
        "programming_language": language,
        "content_language": "pt-BR",
        "topics": [language, "basics"],
        "submission": {"filename": filename, **({"extra_files": submission_extra} if submission_extra else {})},
        "usage": usage_data,
        "validation": validation,
    })
    write_text(folder / "subject.md", subject)
    return folder


def generate_c_basics() -> None:
    root = EXAMPLES / "c-basics"
    reset_dir(root)
    pack(root, "c-basics", "C Basics", ["c"], ["level0", "level1", "level2"])
    exercise(root, "level0", "argc_counter", language="c", filename="argc_counter.c", cases=[
        {"args": [], "expected": "0\n"}, {"args": ["alpha"], "expected": "1\n"}, {"args": ["a", "b", "c"], "expected": "3\n"}], usage_data=usage(allowed={"functions": ["write"], "headers": ["unistd.h"]}, forbidden={"functions": ["printf", "puts"]}, constraints=["Não escreva mensagens extras.", "Sempre finalize a saída com newline."]), subject=md("argc_counter", "Crie um programa que conte quantos argumentos foram passados pela linha de comando, desconsiderando o nome do executável.", "argc_counter.c", ["Imprima apenas um número decimal seguido de `\\n`.", "Sem argumentos adicionais, imprima `0`.", "Não leia da entrada padrão."], ["write"], ["printf", "puts"], [("./argc_counter", "0"), ("./argc_counter a b c", "3")]))
    exercise(root, "level0", "char_stats", language="c", filename="char_stats.c", cases=[
        {"args": ["abc123!"], "expected": "3 0 3 1\n"}, {"args": ["Hi_there"], "expected": "6 1 0 1\n"}, {"args": [], "expected": "0 0 0 0\n"}], usage_data=usage(allowed={"functions": ["write"], "headers": ["unistd.h"]}, forbidden={"functions": ["printf", "isalpha", "isdigit"]}, constraints=["Classifique ASCII manualmente."]), subject=md("char_stats", "Percorra o primeiro argumento e conte letras minúsculas, letras maiúsculas, dígitos e outros caracteres.", "char_stats.c", ["Imprima quatro números: `lower upper digit other`.", "Se não houver argumento, todos os contadores devem ser zero.", "Considere apenas ASCII."], ["write"], ["printf", "isalpha", "isdigit"], [("./char_stats abc123!", "3 0 3 1")]))
    folder = exercise(root, "level1", "ft_strlen_lite", language="c", filename="ft_strlen_lite.c", strategy="function_call", harness="harness/main.c", cases=[
        {"args": [""], "expected": "0\n"}, {"args": ["abc"], "expected": "3\n"}, {"args": ["ponteiros"], "expected": "9\n"}], usage_data=usage(allowed={"headers": ["stddef.h"]}, forbidden={"functions": ["strlen", "printf"]}, constraints=["Implemente usando aritmética de ponteiro ou indexação simples."]), subject=md("ft_strlen_lite", "Implemente uma função que retorna o tamanho de uma string C terminada por `\\0`.", "ft_strlen_lite.c", ["Assinatura obrigatória: `size_t ft_strlen_lite(const char *s);`", "Não crie `main` no arquivo de submissão.", "O harness do pack chama sua função com diferentes strings."], ["stddef.h"], ["strlen", "printf"], [("ft_strlen_lite(\"abc\")", "3")]))
    write_text(folder / "harness" / "main.c", "#include <stddef.h>\n#include <stdio.h>\nsize_t ft_strlen_lite(const char *s);\nint main(int argc, char **argv){ const char *s = argc > 1 ? argv[1] : \"\"; printf(\"%zu\\n\", ft_strlen_lite(s)); return 0; }\n")
    exercise(root, "level1", "array_peak", language="c", filename="array_peak.c", cases=[
        {"args": ["1", "5", "3"], "expected": "5\n"}, {"args": ["-8", "-2", "-9"], "expected": "-2\n"}, {"args": [], "expected": "0\n"}], usage_data=usage(allowed={"functions": ["write"], "headers": ["unistd.h"]}, forbidden={"functions": ["printf", "qsort"]}, constraints=["Não ordene a lista; percorra os valores uma vez."]), subject=md("array_peak", "Receba inteiros pelos argumentos e imprima o maior valor encontrado.", "array_peak.c", ["Se não houver números, imprima `0`.", "Os argumentos podem ser negativos.", "Assuma entradas numéricas válidas."], ["write"], ["printf", "qsort"], [("./array_peak -8 -2 -9", "-2")]))
    exercise(root, "level2", "parse_sum", language="c", filename="parse_sum.c", cases=[
        {"args": ["1", "2", "3"], "expected": "6\n"}, {"args": ["-4", "10", "x"], "expected": "6\n"}, {"args": ["abc"], "expected": "0\n"}], usage_data=usage(allowed={"functions": ["write"], "headers": ["unistd.h"]}, forbidden={"functions": ["atoi", "strtol", "printf"]}, constraints=["Implemente parsing decimal simples.", "Argumentos inválidos contam como zero."]), subject=md("parse_sum", "Some todos os argumentos que representam inteiros decimais simples.", "parse_sum.c", ["Aceite sinal `+` ou `-` no começo.", "Se algum caractere não numérico aparecer, trate aquele argumento como zero.", "Imprima a soma seguida de newline."], ["write"], ["atoi", "strtol", "printf"], [("./parse_sum -4 10 x", "6")]))


def generate_cpp_basics() -> None:
    root = EXAMPLES / "cpp-basics"
    reset_dir(root)
    pack(root, "cpp-basics", "C++ Basics", ["cpp"], ["level0", "level1", "level2"])
    exercise(root, "level0", "line_join", language="cpp", filename="line_join.cpp", cases=[{"args": ["a", "b", "c"], "expected": "a-b-c\n"}, {"args": ["solo"], "expected": "solo\n"}, {"args": [], "expected": "\n"}], usage_data=usage(allowed={"libraries": ["iostream", "string"]}, forbidden={"functions": ["printf"]}), subject=md("line_join", "Junte os argumentos em uma única linha usando hífen como separador.", "line_join.cpp", ["Use `std::string` ou saída incremental com `std::cout`.", "Sem argumentos, imprima apenas newline.", "Não adicione espaços extras."], ["iostream", "string"], ["printf"], [("./line_join a b c", "a-b-c")]))
    folder = exercise(root, "level1", "vector_sum", language="cpp", filename="vector_sum.cpp", strategy="function_call", harness="harness/main.cpp", support_files=["include/vector_sum.hpp"], cases=[{"args": ["1", "2", "3"], "expected": "6\n"}, {"args": ["-5", "7"], "expected": "2\n"}], usage_data=usage(allowed={"libraries": ["vector"]}, constraints=["Passe o vetor por referência constante."]), subject=md("vector_sum", "Implemente uma função que soma valores armazenados em `std::vector<int>`.", "vector_sum.cpp", ["Assinatura: `int sum_values(const std::vector<int>& values);`", "Não escreva `main`.", "O harness converte os argumentos para vetor e imprime o retorno."], ["vector"], ["variáveis globais para acumular estado"], [("sum_values({1,2,3})", "6")]))
    write_text(folder / "include" / "vector_sum.hpp", "#pragma once\n#include <vector>\nint sum_values(const std::vector<int>& values);\n")
    write_text(folder / "harness" / "main.cpp", "#include \"../include/vector_sum.hpp\"\n#include <iostream>\n#include <vector>\nint main(int argc,char**argv){ std::vector<int> v; for(int i=1;i<argc;i++) v.push_back(std::stoi(argv[i])); std::cout << sum_values(v) << '\\n'; }\n")
    folder = exercise(root, "level1", "word_score", language="cpp", filename="word_score.cpp", strategy="function_call", harness="harness/main.cpp", support_files=["include/word_score.hpp"], cases=[{"args": ["abc"], "expected": "294\n"}, {"args": ["Az"], "expected": "187\n"}], usage_data=usage(allowed={"libraries": ["string"]}, forbidden={"libraries": ["numeric"]}, constraints=["Some manualmente os códigos dos caracteres." ]), subject=md("word_score", "Calcule a soma dos códigos ASCII dos caracteres de uma string.", "word_score.cpp", ["Assinatura: `int word_score(const std::string& text);`", "Não escreva `main`.", "A função deve funcionar para string vazia."], ["string"], ["numeric"], [("word_score(\"abc\")", "294")]))
    write_text(folder / "include" / "word_score.hpp", "#pragma once\n#include <string>\nint word_score(const std::string& text);\n")
    write_text(folder / "harness" / "main.cpp", "#include \"../include/word_score.hpp\"\n#include <iostream>\nint main(int argc,char**argv){ std::string s = argc > 1 ? argv[1] : \"\"; std::cout << word_score(s) << '\\n'; }\n")
    folder = exercise(root, "level2", "box_counter", language="cpp", filename="BoxCounter.cpp", strategy="function_call", harness="harness/main.cpp", support_files=["include/BoxCounter.hpp"], cases=[{"args": ["2", "3"], "expected": "5\n"}, {"args": ["10", "-4", "1"], "expected": "7\n"}], usage_data=usage(allowed={"libraries": ["classe própria"]}, constraints=["Mantenha o total encapsulado como detalhe privado." ]), subject=md("box_counter", "Implemente uma classe simples que acumula valores inteiros.", "BoxCounter.cpp", ["Use o header fornecido em `include/BoxCounter.hpp`.", "Implemente `void add(int)` e `int total() const`.", "Não altere a assinatura pública."], ["classes", "encapsulamento"], ["estado global"], [("BoxCounter + 2 + 3", "5")]))
    write_text(folder / "include" / "BoxCounter.hpp", "#pragma once\nclass BoxCounter { int value = 0; public: void add(int n); int total() const; };\n")
    write_text(folder / "harness" / "main.cpp", "#include \"../include/BoxCounter.hpp\"\n#include <iostream>\nint main(int argc,char**argv){ BoxCounter c; for(int i=1;i<argc;i++) c.add(std::stoi(argv[i])); std::cout << c.total() << '\\n'; }\n")


def generate_python_basics() -> None:
    root = EXAMPLES / "python-basics"
    reset_dir(root)
    pack(root, "python-basics", "Python Basics", ["python"], ["level0", "level1", "level2", "level3"])
    exercise(root, "level0", "count_args", language="python", filename="count_args.py", cases=[{"args": [], "expected": "0\n"}, {"args": ["a", "b"], "expected": "2\n"}], usage_data=usage(allowed={"imports": ["sys"]}, forbidden={"functions": ["input"]}), subject=md("count_args", "Conte argumentos de linha de comando em um script Python.", "count_args.py", ["Imprima `len(sys.argv) - 1` seguido de newline.", "Não leia stdin.", "Não escreva texto extra."], ["sys"], ["input"], [("python count_args.py a b", "2")]))
    exercise(root, "level0", "shout_args", language="python", filename="shout_args.py", cases=[{"args": ["hi", "there"], "expected": "HI THERE\n"}, {"args": [], "expected": "\n"}], usage_data=usage(allowed={"imports": ["sys"], "apis": ["str.upper"]}, forbidden={"functions": ["input"]}), subject=md("shout_args", "Transforme todos os argumentos em maiúsculas e una com espaço.", "shout_args.py", ["Sem argumentos, imprima linha vazia.", "Preserve a ordem dos argumentos.", "Finalize com newline."], ["sys", "str.upper"], ["input"], [("python shout_args.py hi there", "HI THERE")]))
    py_funcs = [
        ("level1", "add_numbers", "add_numbers.py", "add", "json", [{"args": ["2", "3"], "expected": "5\n"}, {"args": ["-4", "10"], "expected": "6\n"}], "Implemente `add(a, b)` retornando a soma.", ["Não faça print dentro da função."]),
        ("level1", "reverse_text", "reverse_text.py", "reverse_text", "str", [{"args": ["abc"], "expected": '"cba"\n'}, {"args": ["Python"], "expected": '"nohtyP"\n'}], "Implemente `reverse_text(text)` retornando a string invertida.", ["A função deve retornar string, não imprimir."]),
        ("level1", "max_value", "max_value.py", "max_value", "json", [{"args": ["[1, 4, 2]"], "expected": "4\n"}, {"args": ["[-5, -2, -9]"], "expected": "-2\n"}], "Implemente `max_value(values)` sem usar `max`.", ["Percorra a lista manualmente."]),
        ("level2", "word_counts", "word_counts.py", "word_counts", "json", [{"args": ['["a", "b", "a"]'], "expected": '{"a": 2, "b": 1}\n'}, {"args": ['["x"]'], "expected": '{"x": 1}\n'}], "Implemente `word_counts(words)` retornando um dicionário ordenado por chave.", ["Use dict/comprehension quando fizer sentido."]),
        ("level2", "safe_divide", "safe_divide.py", "safe_divide", "json", [{"args": ["6", "3"], "expected": "2.0\n"}, {"args": ["1", "0"], "expected": "null\n"}], "Implemente `safe_divide(a, b)` retornando `None` quando houver divisão por zero.", ["Use tratamento de exceção ou checagem explícita."]),
        ("level2", "take_even", "take_even.py", "take_even", "json", [{"args": ["[1, 2, 3, 4]"], "expected": "[2, 4]\n"}, {"args": ["[]"], "expected": "[]\n"}], "Implemente `take_even(values)` retornando apenas os pares.", ["Prefira comprehension ou generator interno."]),
        ("level3", "group_initials", "group_initials.py", "group_initials", "json", [{"args": ['["ana", "bia", "alice"]'], "expected": '{"a": ["ana", "alice"], "b": ["bia"]}\n'}], "Implemente `group_initials(names)` agrupando nomes pela inicial minúscula.", ["Preserve a ordem de aparição dentro de cada lista."]),
    ]
    for level, exercise_id, filename, entry, args_format, cases, objective, extra in py_funcs:
        exercise(root, level, exercise_id, language="python", filename=filename, strategy="function_call", entry=entry, args_format=args_format, cases=cases, usage_data=usage(allowed={"imports": []}, forbidden={"functions": ["print"]}, constraints=extra), subject=md(exercise_id, objective, filename, [f"Assinatura obrigatória: `{entry}(...)`.", "Retorne o valor; o harness do app serializa em JSON.", "Não escreva código de execução no topo do módulo."], ["funções", "estruturas nativas"], ["print dentro da função"], []))


def generate_java_basics() -> None:
    root = EXAMPLES / "java-basics"
    reset_dir(root)
    pack(root, "java-basics", "Java Basics", ["java"], ["level0", "level1", "level2"])
    exercise(root, "level0", "sum_args", language="java", filename="SumArgs.java", entry="SumArgs", cases=[{"args": ["1", "2"], "expected": "3\n"}, {"args": ["-3", "8", "1"], "expected": "6\n"}], usage_data=usage(allowed={"libraries": ["java.lang"]}, forbidden={"apis": ["Scanner"]}), subject=md("sum_args", "Some os argumentos inteiros recebidos em `main`.", "SumArgs.java", ["Classe pública obrigatória: `SumArgs`.", "Imprima somente a soma seguida de newline.", "Sem argumentos, imprima `0`."], ["Integer.parseInt"], ["Scanner"], [("java SumArgs 1 2", "3")]))
    exercise(root, "level0", "word_lengths", language="java", filename="WordLengths.java", entry="WordLengths", cases=[{"args": ["java", "oop"], "expected": "java:4\noop:3\n"}, {"args": [], "expected": ""}], usage_data=usage(allowed={"apis": ["String.length"]}, forbidden={"apis": ["Scanner"]}), subject=md("word_lengths", "Imprima cada argumento seguido do seu tamanho.", "WordLengths.java", ["Classe pública obrigatória: `WordLengths`.", "Formato de cada linha: `palavra:tamanho`.", "Sem argumentos, não imprima nada."], ["String.length"], ["Scanner"], [("java WordLengths java oop", "java:4\\noop:3")]))
    exercise(root, "level1", "unique_words", language="java", filename="UniqueWords.java", entry="UniqueWords", cases=[{"args": ["a", "b", "a"], "expected": "a b\n"}, {"args": ["z", "z"], "expected": "z\n"}], usage_data=usage(allowed={"libraries": ["java.util.LinkedHashSet"]}, constraints=["Preserve a ordem da primeira ocorrência."]), subject=md("unique_words", "Remova palavras repetidas preservando a primeira ocorrência.", "UniqueWords.java", ["Classe pública obrigatória: `UniqueWords`.", "Imprima as palavras únicas separadas por espaço.", "Sem argumentos, imprima linha vazia."], ["LinkedHashSet"], ["ordenar a saída"], [("java UniqueWords a b a", "a b")]))
    folder = exercise(root, "level2", "inventory", language="java", filename="InventoryApp.java", submission_extra=["Inventory.java"], entry="InventoryApp", cases=[{"args": ["2", "5"], "expected": "7\n"}, {"args": ["10", "-3", "1"], "expected": "8\n"}], usage_data=usage(allowed={"apis": ["classes", "encapsulamento"]}, constraints=["Mantenha o total como estado privado de Inventory."]), subject=md("inventory", "Crie uma pequena classe de domínio para acumular quantidades.", "InventoryApp.java + Inventory.java", ["`InventoryApp` deve conter o `main`.", "`Inventory` deve expor `add(int)` e `total()`.", "Compile e rode com os dois arquivos."], ["classes", "campos privados"], ["estado global"], [("java InventoryApp 2 5", "7")]))


def migrate_pack(root: Path, default_language: str = "c") -> None:
    if not (root / "pack.json").is_file():
        return
    # Local migration kept intentionally small for private study packs.
    data = json.loads((root / "pack.json").read_text(encoding="utf-8-sig"))
    if data.get("schema_version") != 3:
        return
    data.setdefault("content_language", "pt-BR")
    write_json(root / "pack.json", data)


def main() -> None:
    generate_c_basics()
    generate_cpp_basics()
    generate_python_basics()
    generate_java_basics()
    for root in [EXAMPLES / "sample_rank"]:
        migrate_pack(root)
    for name in ("rank02-practice", "rank02-original", "rank03-original", "rank04-original", "rank05-original", "rank06-original"):
        migrate_pack(PACKS / name)


if __name__ == "__main__":
    main()
