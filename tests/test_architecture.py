"""Testes de arquitetura: protegem as fronteiras entre camadas.

Leem o código-fonte com `ast` (não importam módulo nenhum). Regras:

- domain: só stdlib pura; sem PySide6, sqlite3, subprocess, shutil, os, socket, HTTP,
  e sem `pathlib.Path` concreto (só PurePath/PurePosixPath). Não importa outras camadas.
- application: não importa adapters, infrastructure, PySide6, sqlite3, subprocess nem HTTP.
- application não mexe em arquivos diretamente (shutil/os): isso é trabalho de adapter.
- ports: só dependem de domain (e de outros ports).
- UI (adapters/ui): só importa application, os próprios módulos de UI e resources.
- GenericGrader não conhece runtime nem compilador concreto.
- comparar `language` com uma linguagem específica (`language == "c"`,
  `language == DEFAULT_LANGUAGE`, `language in ("c", "cpp")`) só nos lugares que conhecem
  linguagens: runtimes, RuntimeRegistry e a migração de configuração legada.
- nada no app importa FastAPI/requests/httpx/aiohttp/http.client/urllib.request.

Violações que ainda existem ficam em `KNOWN_VIOLATIONS`, com a sessão do roadmap de
fechamento da V1 que as resolve. O teste correspondente é `expectedFailure`: quando a
sessão resolver, o teste passa a dar "unexpected success" e a marcação precisa sair.
Na S6 este dicionário tem que estar vazio.
"""

from __future__ import annotations

import ast
import unittest
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "exam_trainer"

# teste -> sessão do roadmap que remove a violação
KNOWN_VIOLATIONS: dict[str, str] = {
    "test_domain_uses_only_pure_paths": "S1",
    "test_application_does_not_import_adapters_or_infrastructure": "S1",
    "test_application_does_not_touch_the_filesystem": "S1",
    "test_ports_depend_only_on_domain": "S1",
    "test_ui_only_imports_application": "S1",
    "test_language_checks_only_in_language_aware_modules": "S2",
}


def expected_until(session: str):
    """Marca um teste como violação conhecida até a sessão `session`."""

    def decorate(test):
        test.__doc__ = f"{test.__doc__ or ''} [violação conhecida até {session}]"
        return unittest.expectedFailure(test)

    return decorate


@dataclass(frozen=True)
class ImportRef:
    module: str  # módulo importado (absoluto)
    names: tuple[str, ...]  # nomes importados em `from x import a, b`
    file: str
    line: int


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_relative(current: str, level: int, module: str | None, is_package: bool) -> str:
    base = current.split(".")
    if not is_package:
        base = base[:-1]
    base = base[: len(base) - (level - 1)] if level > 1 else base
    return ".".join(base + ([module] if module else []))


def imports_of(path: Path) -> list[ImportRef]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current = _module_name(path)
    is_package = path.name == "__init__.py"
    refs: list[ImportRef] = []
    rel = str(path.relative_to(SRC))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                refs.append(ImportRef(alias.name, (), rel, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = _resolve_relative(current, node.level, node.module, is_package)
            refs.append(ImportRef(module, tuple(a.name for a in node.names), rel, node.lineno))
    return refs


def files_in(*parts: str) -> list[Path]:
    root = SRC.joinpath(*parts)
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _matches(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == p or module.startswith(p + ".") for p in prefixes)


def violations(paths: list[Path], forbidden: tuple[str, ...]) -> list[str]:
    found = []
    for path in paths:
        for ref in imports_of(path):
            if _matches(ref.module, forbidden):
                found.append(f"{ref.file}:{ref.line} importa {ref.module}")
    return found


HTTP_MODULES = ("fastapi", "requests", "httpx", "aiohttp", "http.client", "urllib.request", "starlette")
PROCESS_AND_DB = ("PySide6", "sqlite3", "subprocess", "socket")


class DependencyBoundariesTest(unittest.TestCase):
    def assertNoViolations(self, found: list[str]) -> None:
        self.assertEqual(found, [], "\n" + "\n".join(found))

    # ------------------------------------------------------------------ domain
    def test_domain_imports_only_pure_stdlib(self) -> None:
        forbidden = (
            *PROCESS_AND_DB,
            *HTTP_MODULES,
            "shutil",
            "os",
            "exam_trainer.adapters",
            "exam_trainer.application",
            "exam_trainer.infrastructure",
            "exam_trainer.ports",
        )
        self.assertNoViolations(violations(files_in("domain"), forbidden))

    @expected_until(KNOWN_VIOLATIONS["test_domain_uses_only_pure_paths"])
    def test_domain_uses_only_pure_paths(self) -> None:
        """domain não usa pathlib.Path concreto (que faz I/O); só PurePath/PurePosixPath."""
        found = []
        for path in files_in("domain"):
            for ref in imports_of(path):
                if ref.module == "pathlib" and "Path" in ref.names:
                    found.append(f"{ref.file}:{ref.line} importa pathlib.Path")
        self.assertNoViolations(found)

    # ------------------------------------------------------------- application
    @expected_until(KNOWN_VIOLATIONS["test_application_does_not_import_adapters_or_infrastructure"])
    def test_application_does_not_import_adapters_or_infrastructure(self) -> None:
        forbidden = (
            *PROCESS_AND_DB,
            *HTTP_MODULES,
            "exam_trainer.adapters",
            "exam_trainer.infrastructure",
        )
        self.assertNoViolations(violations(files_in("application"), forbidden))

    @expected_until(KNOWN_VIOLATIONS["test_application_does_not_touch_the_filesystem"])
    def test_application_does_not_touch_the_filesystem(self) -> None:
        """Mover/apagar pastas é trabalho do adapter de workspace, não da application."""
        self.assertNoViolations(violations(files_in("application"), ("shutil", "os")))

    # ------------------------------------------------------------------- ports
    @expected_until(KNOWN_VIOLATIONS["test_ports_depend_only_on_domain"])
    def test_ports_depend_only_on_domain(self) -> None:
        forbidden = (
            *PROCESS_AND_DB,
            *HTTP_MODULES,
            "exam_trainer.adapters",
            "exam_trainer.application",
            "exam_trainer.infrastructure",
        )
        self.assertNoViolations(violations(files_in("ports"), forbidden))

    # ---------------------------------------------------------------------- UI
    @expected_until(KNOWN_VIOLATIONS["test_ui_only_imports_application"])
    def test_ui_only_imports_application(self) -> None:
        allowed = ("exam_trainer.application", "exam_trainer.adapters.ui", "exam_trainer.resources")
        found = []
        for path in files_in("adapters", "ui"):
            for ref in imports_of(path):
                if ref.module.startswith("exam_trainer") and not _matches(ref.module, allowed):
                    found.append(f"{ref.file}:{ref.line} importa {ref.module}")
        self.assertNoViolations(found)

    def test_only_ui_and_entry_point_import_pyside(self) -> None:
        paths = [p for p in files_in() if not str(p.relative_to(SRC)).startswith(("adapters/ui", "adapters\\ui"))]
        paths = [p for p in paths if p.name != "main.py" or p.parent != SRC]
        self.assertNoViolations(violations(paths, ("PySide6",)))

    # ----------------------------------------------------------------- grading
    def test_generic_grader_does_not_know_concrete_runtimes(self) -> None:
        grader_files = [
            p for p in files_in() if "class GenericGrader" in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(len(grader_files), 1, grader_files)
        forbidden = ("exam_trainer.adapters.runtime", "exam_trainer.adapters.compiler", "subprocess")
        self.assertNoViolations(violations(grader_files, forbidden))

    # --------------------------------------------------------------- language
    @expected_until(KNOWN_VIOLATIONS["test_language_checks_only_in_language_aware_modules"])
    def test_language_checks_only_in_language_aware_modules(self) -> None:
        """`language == "c"`/`language == DEFAULT_LANGUAGE` só onde a linguagem é o assunto do módulo."""
        allowed_prefixes = (
            "adapters/runtime/",
            "application/engine/runtime_registry.py",
            "adapters/persistence/json_app_config_repository.py",  # migração da config legada (S2)
        )
        found = []
        for path in files_in():
            rel = path.relative_to(SRC).as_posix()
            if rel.startswith(allowed_prefixes):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                if not any(isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) for op in node.ops):
                    continue
                operands = [node.left, *node.comparators]
                if any(_is_language_name(item) for item in operands) and any(
                    _is_specific_language_value(item) for item in operands
                ):
                    found.append(f"{rel}:{node.lineno} compara language com uma linguagem específica")
        self.assertNoViolations(found)

    # -------------------------------------------------------------------- HTTP
    def test_app_does_not_depend_on_http_clients_or_web_frameworks(self) -> None:
        self.assertNoViolations(violations(files_in(), HTTP_MODULES))


def _is_specific_language_value(node: ast.AST) -> bool:
    """Literal de string, constante em MAIÚSCULAS ou coleção literal de strings.

    `language in self._runtimes` (pertinência a um registro) não conta: isso é consulta,
    não um `if` por linguagem.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.Name) and node.id.isupper():
        return True
    if isinstance(node, ast.Attribute) and node.attr.isupper():
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return any(_is_specific_language_value(item) for item in node.elts)
    return False


def _is_language_name(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "language" or node.id.endswith("_language")
    if isinstance(node, ast.Attribute):
        return node.attr == "language"
    return False


class KnownViolationsRegistryTest(unittest.TestCase):
    def test_every_known_violation_has_a_marked_test(self) -> None:
        names = set(dir(DependencyBoundariesTest))
        self.assertEqual(sorted(set(KNOWN_VIOLATIONS) - names), [])
        for name in KNOWN_VIOLATIONS:
            method = getattr(DependencyBoundariesTest, name)
            self.assertTrue(getattr(method, "__unittest_expecting_failure__", False), name)

    def test_sessions_are_from_the_roadmap(self) -> None:
        self.assertTrue(set(KNOWN_VIOLATIONS.values()) <= {"S1", "S2", "S3", "S4", "S5", "S6"})


if __name__ == "__main__":
    unittest.main()
