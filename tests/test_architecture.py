"""Architecture tests: protect boundaries between layers.

They read source code with `ast` and do not import any modules. Rules:

- domain: pure stdlib only; no PySide6, sqlite3, subprocess, shutil, os, socket,
  HTTP, or concrete `pathlib.Path` (only PurePath/PurePosixPath). Does not import
  other layers.
- application: does not import adapters, infrastructure, PySide6, sqlite3,
  subprocess, or HTTP.
- application does not touch files directly (shutil/os): that is adapter work.
- ports: depend only on domain and other ports.
- UI (adapters/ui): imports only application, UI modules, and resources.
- GenericGrader does not know concrete runtimes or compilers.
- comparing `language` with a specific language (`language == "c"`,
  `language == DEFAULT_LANGUAGE`, `language in ("c", "cpp")`) is allowed only in
  language-aware places: runtimes, RuntimeRegistry, and legacy configuration
  migration.
- nothing in the app imports FastAPI/requests/httpx/aiohttp/http.client/urllib.request.

Remaining violations live in `KNOWN_VIOLATIONS`, with the V1 closure roadmap
session that resolves them. The corresponding test is marked `expectedFailure`:
when the session resolves it, the test becomes an unexpected success and the mark
must be removed. In S6 this dictionary must be empty.
"""

from __future__ import annotations

import ast
import unittest
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "exam_trainer"

# test -> roadmap session that removes the violation
KNOWN_VIOLATIONS: dict[str, str] = {}


def expected_until(session: str):
    """Mark a test as a known violation until `session`."""

    def decorate(test):
        test.__doc__ = f"{test.__doc__ or ''} [known violation until {session}]"
        return unittest.expectedFailure(test)

    return decorate


@dataclass(frozen=True)
class ImportRef:
    module: str  # imported module, absolute
    names: tuple[str, ...]  # imported names in `from x import a, b`
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
                found.append(f"{ref.file}:{ref.line} imports {ref.module}")
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

    def test_domain_uses_only_pure_paths(self) -> None:
        """domain does not use concrete pathlib.Path (which does I/O), only PurePath/PurePosixPath."""
        found = []
        for path in files_in("domain"):
            for ref in imports_of(path):
                if ref.module == "pathlib" and "Path" in ref.names:
                    found.append(f"{ref.file}:{ref.line} imports pathlib.Path")
        self.assertNoViolations(found)

    # ------------------------------------------------------------- application
    def test_application_does_not_import_adapters_or_infrastructure(self) -> None:
        forbidden = (
            *PROCESS_AND_DB,
            *HTTP_MODULES,
            "exam_trainer.adapters",
            "exam_trainer.infrastructure",
        )
        self.assertNoViolations(violations(files_in("application"), forbidden))

    def test_application_does_not_touch_the_filesystem(self) -> None:
        """Moving/deleting folders is workspace adapter work, not application work."""
        self.assertNoViolations(violations(files_in("application"), ("shutil", "os")))

    # ------------------------------------------------------------------- ports
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
    def test_ui_only_imports_application(self) -> None:
        allowed = ("exam_trainer.application", "exam_trainer.adapters.ui", "exam_trainer.resources")
        found = []
        for path in files_in("adapters", "ui"):
            for ref in imports_of(path):
                if ref.module.startswith("exam_trainer") and not _matches(ref.module, allowed):
                    found.append(f"{ref.file}:{ref.line} imports {ref.module}")
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
    def test_language_checks_only_in_language_aware_modules(self) -> None:
        """`language == "c"`/`language == DEFAULT_LANGUAGE` only where language is the module subject."""
        allowed_prefixes = (
            "adapters/runtime/",
            "application/engine/runtime_registry.py",
            "adapters/persistence/json_app_config_repository.py",  # legacy config migration (S2)
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
                    found.append(f"{rel}:{node.lineno} compares language with a specific language")
        self.assertNoViolations(found)

    # -------------------------------------------------------------------- HTTP
    def test_app_does_not_depend_on_http_clients_or_web_frameworks(self) -> None:
        self.assertNoViolations(violations(files_in(), HTTP_MODULES))

    # ---------------------------------------------------------------- registries
    def test_no_parallel_editor_preset_list_outside_editor_registry(self) -> None:
        """Only editor_registry.py may enumerate the known editor presets as a
        literal collection; everywhere else must read them from EditorRegistry,
        so the list is never duplicated (Fase 4)."""
        self.assertNoViolations(
            _literal_collection_violations(files_in(), {"VS Code", "Zed", "Cursor"})
        )

    def test_no_parallel_theme_key_list_outside_theme_registry(self) -> None:
        """No module besides theme/themes.py may enumerate the legacy theme
        keys as a literal collection; everywhere else must read them from
        ThemeRegistry/THEME_REGISTRY (Fase 4)."""
        allowed = {"adapters/ui/qt/theme/themes.py"}
        found = _literal_collection_violations(
            [p for p in files_in() if p.relative_to(SRC).as_posix() not in allowed],
            {"terminal", "amber", "gameboy", "neon", "minimal", "paper"},
        )
        self.assertNoViolations(found)

    # ----------------------------------------------------------- declarative themes
    def test_theme_loader_never_executes_code(self) -> None:
        """Fase 5: theme.json is purely declarative. Neither the contract
        parser nor the folder loader may contain any code-execution
        primitive -- they only read JSON and build a ThemeTokens value."""
        forbidden_names = {"eval", "exec", "compile", "__import__"}
        forbidden_modules = ("subprocess", "importlib", "os.system", "pty", "ctypes")
        paths = [
            SRC / "adapters" / "theme" / "theme_contract.py",
            SRC / "adapters" / "theme" / "user_theme_loader.py",
        ]
        found = []
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden_names:
                    found.append(f"{path.relative_to(SRC).as_posix()}:{node.lineno} calls {node.func.id}()")
                if isinstance(node, ast.Name) and node.id in forbidden_names:
                    found.append(f"{path.relative_to(SRC).as_posix()}:{node.lineno} references {node.id}")
        found.extend(violations(paths, forbidden_modules))
        self.assertNoViolations(found)



def _literal_collection_violations(paths: list[Path], forbidden_together: set[str]) -> list[str]:
    """Flag any tuple/list/set literal in `paths` that contains every string in
    `forbidden_together` -- the signature of a hand-duplicated registry list."""
    found = []
    for path in paths:
        rel = path.relative_to(SRC).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                continue
            values = {
                element.value
                for element in node.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            }
            if forbidden_together.issubset(values):
                found.append(f"{rel}:{node.lineno} hardcodes {sorted(forbidden_together)}")
    return found

def _is_specific_language_value(node: ast.AST) -> bool:
    """String literal, uppercase constant, or literal collection of strings.

    `language in self._runtimes` (registry membership) does not count: it is a
    lookup, not a per-language `if`.
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
