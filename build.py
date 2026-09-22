from pathlib import Path
import argparse
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
SPEC_FILE = ROOT / "42 Exam Trainer.spec"
EXE_PATH = DIST_DIR / "42 Exam Trainer.exe"


def remove_dir(path: Path) -> None:
    if path.exists():
        print(f"Removendo {path.name}/...")
        shutil.rmtree(path)


def run_build() -> int:
    if not SPEC_FILE.exists():
        print(f"Arquivo .spec não encontrado: {SPEC_FILE}")
        return 1

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

    print("\nBuild concluída.")

    if EXE_PATH.exists():
        print(f"Executável: {EXE_PATH}")
    else:
        print(f"Saída disponível em: {DIST_DIR}")

    return 0


def run_executable() -> int:
    if not EXE_PATH.exists():
        print(f"Executável não encontrado: {EXE_PATH}")
        return 1

    print(f"Abrindo: {EXE_PATH}")
    subprocess.Popen([str(EXE_PATH)], cwd=DIST_DIR)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build helper do 42 Exam Trainer"
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Abre o executável após uma build bem-sucedida",
    )
    args = parser.parse_args()

    result = run_build()
    if result != 0:
        return result

    if args.run:
        return run_executable()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
