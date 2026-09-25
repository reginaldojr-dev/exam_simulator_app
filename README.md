# Exam Trainer

Exam Trainer is a local-first desktop app for programming practice and exam simulation.
It manages study packs, workspaces, runtime/toolchain checks, correction traces,
training progress, exam sessions and history in a compact PySide6 UI.

This repository contains the app engine and public example packs. It does not contain
private/original exam packs or proprietary study material.

## Features

- Training mode with level-based or random activity selection.
- Exam mode with absolute deadlines, resume, PASS/FAIL flow and 100% completion rule.
- Generic runtime layer for C, C++, Python and Java/JDK.
- Runtime preflight: missing toolchains block correction/exam start with clear messages.
- Pack contract v3 with Markdown subjects, `programming_language`, `content_language`,
  usage constraints, validation plans and optional references only when needed.
- SQLite progress/history with migrations and backups.
- Workspace separation for training and exams.
- Home flow for `QUERO ESTUDAR ALGO NOVO`: create a vendor-neutral prompt for generating
  compatible packs, then import them.
- PyInstaller build flow for `Exam Trainer.exe` with safe replacement and SHA-256 checksum.

## Requirements

- Python 3.12+
- PySide6
- Optional external toolchains depending on the pack:
  - C: GCC/Clang compatible compiler
  - C++: C++17-capable compiler
  - Python: system Python 3.9+ (`py -3`, `python3` or `python`)
  - Java: JDK (`javac` and `java`)

The app never installs runtimes automatically. Missing runtimes are reported in the UI.
When frozen, Python exercises must use a system Python, not the bundled app executable.

## Development

Use the project-local virtual environment at the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[build]"
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[build]"
```

Run from source:

```bash
python -m exam_trainer.main
```

Run tests:

```bash
python -m pytest -q
```

## Packs

Packs can be imported from a folder or ZIP through `Configuracoes > Packs`.
The full supported contract is the single source of truth:

- [`src/exam_trainer/resources/pack-contract.md`](src/exam_trainer/resources/pack-contract.md)

Public example packs live in [`examples/packs`](examples/packs):

- `c-basics`
- `cpp-basics`
- `python-basics`
- `java-basics`
- `sample_rank`
- `rank02-practice` when present in the checkout

Private/original packs belong under `_local/packs/` and are ignored by Git.

Security note: packs may contain harnesses or references that are compiled/executed during
correction with the current user's permissions. Import only packs you trust. The importer
rejects unsafe paths, ZIP traversal, symlinks/junctions and unsupported strategies, but it
does not provide a full sandbox.

## Workspace And Data

On Windows, app configuration and the local SQLite database use:

```text
%APPDATA%\exam-trainer\
```

Training and exam files are separate:

```text
workspace/
├── training/
│   └── <pack_id>/
│       └── <activity_id>/
└── exams/
    └── <session_id>/
        └── <activity_id>/
```

Legacy training workspaces are migrated defensively when safe. Existing user files are not
deleted silently.

## Build

Build from the project `.venv`:

```bash
python build.py            # build only if relevant inputs changed
python build.py --force    # force rebuild
python build.py --run      # build if needed, then open the executable
```

Output:

```text
_local/dist/Exam Trainer.exe
_local/dist/Exam Trainer.exe.sha256
```

On Linux/macOS the executable name is `Exam Trainer`.

Build behavior:

- hashes only release/build inputs (`src/`, `examples/`, README, LICENSE, CHANGELOG,
  spec, pyproject and environment versions);
- ignores `_local/`, private packs, Git metadata, caches, logs and temporary files;
- builds in `_local/build/_staging`;
- keeps the previous executable if PyInstaller fails;
- replaces the executable only after a successful build;
- reports Windows App Control / Smart App Control launch blocks without traceback.

Trusted code signing is an external release step. No certificate is stored in this repo.

## Release Checklist

1. Run the full test suite.
2. Build with `python build.py --force`.
3. Smoke test the executable.
4. Sign the executable when a trusted certificate is available.
5. Verify the SHA-256 checksum.
6. Publish a release manually if desired.

No remote release is created by the build script.

## Documentation

- Current operational snapshot: [`docs/current-state.md`](docs/current-state.md)
- Session/status log: [`docs/project-status.md`](docs/project-status.md)
- Architectural decisions: [`docs/decisions`](docs/decisions)
- Runtime notes: [`docs/runtimes.md`](docs/runtimes.md)
- Pack contract: [`src/exam_trainer/resources/pack-contract.md`](src/exam_trainer/resources/pack-contract.md)

## License

Exam Trainer is released under the [MIT License](LICENSE).
