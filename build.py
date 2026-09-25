"""Build helper do Exam Trainer (PyInstaller).

Uso (com a .venv do projeto ativa):
    python build.py            gera o executável (pula se nada mudou)
    python build.py --run      abre o executável; recompila antes só se algo mudou
    python build.py --force    recompila mesmo sem mudanças

Garantias:
- o executável anterior NÃO é apagado antes de o novo build dar certo (o PyInstaller gera
  numa pasta de staging e só no fim o exe é trocado);
- o hash considera só o que entra no executável (src/, examples/, docs de release, .spec,
  pyproject.toml) e as versões do ambiente (Python, PyInstaller, PySide6, plataforma);
- _local/ (packs privados locais, artefatos de agentes e rascunhos) não entra no
  executável nem no hash;
- erro de política do Windows ao abrir o exe (WinError 4551/1260) é explicado, sem traceback.
"""

from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
LOCAL_DIR = ROOT / "_local"
BUILD_DIR = LOCAL_DIR / "build"
DIST_DIR = LOCAL_DIR / "dist"
STAGING_DIR = BUILD_DIR / "_staging"
SPEC_FILE = ROOT / "Exam Trainer.spec"
APP_NAME = "Exam Trainer"
EXE_NAME = f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME
EXE_PATH = DIST_DIR / EXE_NAME
CHECKSUM_PATH = DIST_DIR / f"{EXE_NAME}.sha256"
STATE_FILE = DIST_DIR / ".build_state.json"
PROJECT_VENV = ROOT / ".venv"
PROJECT_SRC = ROOT / "src"

# Códigos de saída
EXIT_OK = 0
EXIT_BUILD_FAILED = 1
EXIT_LAUNCH_BLOCKED = 3  # build ok, mas o sistema operacional impediu abrir o exe
EXIT_REPLACE_FAILED = 4  # build ok, mas o exe antigo está em uso e não pôde ser trocado

# WinError de bloqueio por política do Windows (Smart App Control / WDAC / AppLocker).
WINDOWS_POLICY_BLOCK_ERRORS = {
    4551: "uma política de Controle de Aplicativo bloqueou este arquivo",
    1260: "uma política de grupo bloqueou este programa",
}

# O que entra no executável (tem que bater com o .spec).
SOURCE_DIRS = (
    ROOT / "src",
    ROOT / "examples",
)
SOURCE_FILES = (
    SPEC_FILE,
    ROOT / "pyproject.toml",
    ROOT / "README.md",
    ROOT / "LICENSE",
    ROOT / "CHANGELOG.md",
)

# Ignorados em QUALQUER nível (caches gerados).
IGNORED_ANYWHERE = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
# Ignorados SÓ na raiz do projeto. Uma pasta com o mesmo nome dentro de src/
# (como src/exam_trainer/adapters/workspace/) continua no hash.
IGNORED_AT_ROOT = {
    ".git",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "tests",
    "_local",
    "Claude outputs",
}


def should_ignore(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    parts = relative.parts
    if not parts:
        return False
    if parts[0] in IGNORED_AT_ROOT:
        return True
    if path.suffix in IGNORED_SUFFIXES:
        return True
    return any(part in IGNORED_ANYWHERE for part in parts)


def iter_build_inputs():
    seen = set()
    for path in SOURCE_FILES:
        if path.is_file() and path not in seen:
            seen.add(path)
            yield path
    for directory in SOURCE_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or should_ignore(path) or path in seen:
                continue
            seen.add(path)
            yield path


def _package_version(name: str) -> str | None:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover
        return None
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def environment_fingerprint() -> dict[str, str | None]:
    """Versões que mudam o executável mesmo sem mudar o código."""
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": f"{sys.platform}-{platform.machine()}",
        "pyinstaller": _package_version("pyinstaller"),
        "pyside6": _package_version("PySide6"),
    }


def calculate_source_hash() -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(environment_fingerprint(), sort_keys=True).encode("utf-8"))
    digest.update(b"\0")
    for path in iter_build_inputs():
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def load_build_hash() -> str | None:
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = data.get("source_hash")
    return value if isinstance(value, str) else None


def save_build_hash(source_hash: str) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"source_hash": source_hash, "environment": environment_fingerprint()}, indent=2),
        encoding="utf-8",
    )


def executable_is_current(source_hash: str) -> bool:
    return EXE_PATH.exists() and load_build_hash() == source_hash


def run_build(source_hash: str | None = None) -> int:
    if not SPEC_FILE.exists():
        print(f"Arquivo .spec não encontrado: {SPEC_FILE}")
        return EXIT_BUILD_FAILED
    if source_hash is None:
        source_hash = calculate_source_hash()

    staging_dist = STAGING_DIR / "dist"
    staging_work = STAGING_DIR / "work"
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC_FILE),
        "--clean",
        "--noconfirm",
        "--distpath",
        str(staging_dist),
        "--workpath",
        str(staging_work),
    ]
    print("=== Exam Trainer Build ===")
    print("Gerando executável (o executável atual só é trocado se o build der certo)...")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        print("\nBuild falhou. O executável anterior foi mantido." if EXE_PATH.exists() else "\nBuild falhou.")
        return result.returncode or EXIT_BUILD_FAILED

    staged_exe = staging_dist / EXE_NAME
    if not staged_exe.exists():
        print(f"\nBuild terminou, mas o executável não foi encontrado em: {staged_exe}")
        return EXIT_BUILD_FAILED

    code = install_executable(staged_exe)
    if code != EXIT_OK:
        return code
    write_checksum()
    save_build_hash(source_hash)
    shutil.rmtree(STAGING_DIR, ignore_errors=True)
    print("\nBuild concluída.")
    print(f"Executável: {EXE_PATH}")
    return EXIT_OK


def write_checksum() -> str:
    digest = hashlib.sha256()
    with EXE_PATH.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    checksum = digest.hexdigest()
    CHECKSUM_PATH.write_text(f"{checksum}  {EXE_NAME}\n", encoding="utf-8")
    print(f"SHA-256: {CHECKSUM_PATH}")
    return checksum


def install_executable(staged_exe: Path) -> int:
    """Troca o exe antigo pelo novo de forma atômica (os.replace)."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(staged_exe, EXE_PATH)
    except OSError as error:
        print()
        print(f"Build concluído, mas não foi possível substituir {EXE_PATH.name}: {error}")
        print("Feche o app se ele estiver aberto e rode o build de novo.")
        print(f"O novo executável ficou em: {staged_exe}")
        return EXIT_REPLACE_FAILED
    return EXIT_OK


def run_executable() -> int:
    if not EXE_PATH.exists():
        print(f"Executável não encontrado: {EXE_PATH}")
        return EXIT_BUILD_FAILED
    print(f"Abrindo: {EXE_PATH}")
    try:
        subprocess.Popen([str(EXE_PATH)], cwd=DIST_DIR)
    except OSError as error:
        return report_launch_error(error)
    return EXIT_OK


def report_launch_error(error: OSError) -> int:
    """Erro ao ABRIR o exe não é erro de build: explica sem despejar traceback."""
    winerror = getattr(error, "winerror", None)
    print()
    print("Build concluído com sucesso.")
    if winerror in WINDOWS_POLICY_BLOCK_ERRORS:
        print(
            "O Windows bloqueou a execução do executável: "
            f"{WINDOWS_POLICY_BLOCK_ERRORS[winerror]} (WinError {winerror})."
        )
        print("Isso costuma ser o Controle Inteligente de Aplicativos com um exe sem assinatura digital.")
        print("Para testar agora, rode pelo código-fonte: python -m exam_trainer.main")
    else:
        print(f"Não foi possível abrir o executável: {error}")
    print(f"Executável: {EXE_PATH}")
    return EXIT_LAUNCH_BLOCKED


def check_environment() -> None:
    """Avisa quando o build roda fora do ambiente do projeto.

    PyInstaller empacota as dependências do interpretador que o executa;
    fora da .venv do projeto, o exe pode sair com versões erradas.
    """
    in_project_venv = Path(sys.prefix).resolve() == PROJECT_VENV.resolve()
    if not in_project_venv:
        print(
            "AVISO: build rodando fora da .venv do projeto.\n"
            f"  Python em uso: {sys.executable}\n"
            f"  Recomendado : {PROJECT_VENV / ('Scripts' if sys.platform == 'win32' else 'bin')}"
            " (ative a .venv antes de rodar build.py)"
        )
    try:
        import exam_trainer  # noqa: PLC0415
    except ImportError:
        return
    origin = Path(exam_trainer.__file__).resolve()
    if PROJECT_SRC.resolve() not in origin.parents:
        print(
            "AVISO: neste Python, 'exam_trainer' vem de outra cópia do projeto:\n"
            f"  {origin}\n"
            "  Rode 'python -m pip install -e .' dentro da .venv deste projeto."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build helper do Exam Trainer")
    parser.add_argument(
        "-r",
        "--run",
        action="store_true",
        help=(
            "Abre o executável. Se não houve mudanças desde a última build, "
            "não recompila; se houve, gera uma nova build antes de abrir. "
            "Sai com código 3 se o build existe mas o sistema bloqueou a abertura."
        ),
    )
    parser.add_argument("--force", action="store_true", help="Força uma nova build mesmo sem mudanças.")
    args = parser.parse_args(argv)

    check_environment()
    source_hash = calculate_source_hash()

    if not args.force and executable_is_current(source_hash):
        print("Nenhuma mudança desde a última build. Pulando PyInstaller.")
        return run_executable() if args.run else EXIT_OK

    result = run_build(source_hash)
    if result != EXIT_OK:
        return result
    return run_executable() if args.run else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

