from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
SPEC_FILE = ROOT / "42 Exam Trainer.spec"
EXE_PATH = DIST_DIR / "42 Exam Trainer.exe"
STATE_FILE = DIST_DIR / ".build_state.json"
PROJECT_VENV = ROOT / ".venv"
PROJECT_SRC = ROOT / "src"

# Códigos de saída
EXIT_OK = 0
EXIT_LAUNCH_BLOCKED = 3  # build ok, mas o sistema operacional impediu abrir o exe

# WinError de bloqueio por política do Windows (Smart App Control / WDAC / AppLocker).
WINDOWS_POLICY_BLOCK_ERRORS = {
    4551: "uma política de Controle de Aplicativo bloqueou este arquivo",
    1260: "uma política de grupo bloqueou este programa",
}

# Pastas que podem alterar o executável.
SOURCE_DIRS = (
    ROOT / "src",
    ROOT / "packs",
    ROOT / "examples",
)

# Arquivos de configuração que também podem afetar a build.
SOURCE_FILES = (
    SPEC_FILE,
    ROOT / "pyproject.toml",
)

# Arquivos/pastas que não precisam provocar uma nova build.
IGNORED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "tests",
    "workspace",
}


def remove_dir(path: Path) -> None:
    if path.exists():
        print(f"Removendo {path.name}/...")
        shutil.rmtree(path)


def should_ignore(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False

    return any(part in IGNORED_PARTS for part in relative.parts)


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
            if not path.is_file() or should_ignore(path):
                continue
            if path in seen:
                continue

            seen.add(path)
            yield path


def calculate_source_hash() -> str:
    digest = hashlib.sha256()

    for path in iter_build_inputs():
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        digest.update(relative)
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
        json.dumps({"source_hash": source_hash}, indent=2),
        encoding="utf-8",
    )


def executable_is_current(source_hash: str) -> bool:
    if not EXE_PATH.exists():
        return False

    previous_hash = load_build_hash()
    return previous_hash == source_hash


def run_build(source_hash: str | None = None) -> int:
    if not SPEC_FILE.exists():
        print(f"Arquivo .spec não encontrado: {SPEC_FILE}")
        return 1

    if source_hash is None:
        source_hash = calculate_source_hash()

    remove_dir(BUILD_DIR)
    remove_dir(DIST_DIR)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC_FILE),
        "--clean",
        "--noconfirm",
    ]

    print("=== 42 Exam Trainer Build ===")
    print("Gerando executável...")

    result = subprocess.run(command, cwd=ROOT)

    if result.returncode != 0:
        print("\nBuild falhou.")
        return result.returncode

    if not EXE_PATH.exists():
        print(f"\nBuild terminou, mas o executável não foi "
              f"encontrado em: {EXE_PATH}")
        return 1

    save_build_hash(source_hash)

    print("\nBuild concluída.")
    print(f"Executável: {EXE_PATH}")
    return 0


def run_executable() -> int:
    if not EXE_PATH.exists():
        print(f"Executável não encontrado: {EXE_PATH}")
        return 1

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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build helper do 42 Exam Trainer"
    )
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Força uma nova build mesmo se não houve mudanças.",
    )
    args = parser.parse_args()

    check_environment()
    source_hash = calculate_source_hash()

    if args.run and not args.force and executable_is_current(source_hash):
        print("Nenhuma mudança desde a última build. Pulando PyInstaller.")
        return run_executable()

    result = run_build(source_hash)
    if result != 0:
        return result

    if args.run:
        return run_executable()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
