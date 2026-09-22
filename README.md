# 42 Exam Trainer

42 Exam Trainer is a desktop application prototype for studying programming exam workflows inspired by the 42 ecosystem.

This repository is public and intentionally does not include real exam questions, exercise packs, graders, compilation logic, or official 42 content.

## Current Stage

This MVP contains:

- Python 3.12+ project structure
- PySide6 desktop entrypoint
- local workspace setup flow
- small JSON-based local configuration adapter
- compact PySide6 UI for training, exam mode, trace, history, settings, and pack import
- typed `exercise.json` and `pack.json` contracts
- generic C grading foundation for `program_output` and `function_with_main`
- deterministic test generators and internal expectations
- technical trace generation
- SQLite persistence foundation for attempts/progress
- unit tests for workspace, configuration, parsing, packs, compiler/grader foundations, and SQLite

The desktop UI now exposes the first usable MVP flow for the bundled sample pack: start training, view the subject, open the exercise folder in an external IDE, run correction, view PASS/FAIL, open the technical trace, view progress/history, import packs, and start/resume/end a simple exam session.

This is still not a complete exam clone and contains no official 42 exam content, login, backend, API, online updates, XP, badges, or gamification.

## Exercise Definition Contract

External exercises describe themselves through an `exercise.json` file. The app defines the contract; exercise content adapts to it.

```json
{
  "id": "echo_args",
  "name": "Echo Args",
  "subject": "subject.md",
  "submission": {
    "filename": "echo_args.c"
  },
  "execution": {
    "type": "program_output"
  },
  "tests": {
    "generator": "random_arguments",
    "expectation": "echo_arguments"
  },
  "limits": {
    "timeout_seconds": 2
  }
}
```

The JSON loader validates structure and known capability identifiers before producing a typed `ExerciseDefinition`.

Supported execution types:

- `program_output`: compile the submitted C file, run it with generated arguments, compare stdout.
- `function_with_main`: compile a pack-provided `main.c` fixture with the submitted C file, run it, compare stdout.
- `custom`: reserved by the contract, not implemented by the current grader.

Supported generators:

- `random_string`
- `random_integer`
- `random_arguments`
- `random_int_array`

Supported expectations:

- `echo_arguments`
- `sum_integers`

Packs reference these identifiers. They do not provide shell commands, Python code, graders, or arbitrary executable logic.

## Pack Contract

A pack contains a `pack.json` file:

```json
{
  "id": "sample_rank",
  "name": "Sample Rank",
  "version": "1.0.0",
  "levels": [
    { "id": "level0", "path": "level0" },
    { "id": "level1", "path": "level1" }
  ]
}
```

Each level contains exercise directories with an `exercise.json` and a referenced `subject.md`. `function_with_main` exercises must also include the declared fixture, usually `main.c`.

See `examples/packs/sample_rank` for a small public sample pack with original exercises.

## Architecture

The project starts with a small hexagonal architecture:

- `domain`: pure core entities, value objects, and domain services. It does not know about PySide6, JSON, operating systems, files, subprocesses, or storage implementations.
- `application`: use cases and DTOs. This layer orchestrates domain objects through ports, but does not implement UI, persistence, compilation, grading, or editor integration.
- `application/capabilities.py`: registries for known exercise capabilities such as execution types, test generators, and expectations.
- `ports`: interfaces required by the application for external concerns such as configuration, workspace management, packs, progress, grading, compiler access, and editor integration.
- `adapters`: concrete implementations at the edges, currently PySide6 UI, JSON configuration persistence, and local workspace filesystem handling.
- `infrastructure`: dependency composition and platform path selection.

The core does not depend on PySide6, JSON, operating-system details, or concrete storage.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
```

You also need a C compiler available in `PATH`. The app detects, in order:

- `cc`
- `clang`
- `gcc`

If none is found, training can still open subjects/workspaces, but correction and exam mode will show a clear compiler requirement message.

On Linux or macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Run

```bash
exam-trainer
```

Or:

```bash
python -m exam_trainer.main
```

On first run, choose a workspace directory. The app creates and remembers the workspace path. You can later change it from `Configurações`.

## Settings

The `Configurações` screen lets you:

- view and change the workspace;
- set the external editor command, such as `code`, `zed`, or a custom executable;
- see the detected C compiler;
- rerun compiler detection.

## Run Tests

The tests use Python's standard `unittest` runner:

```bash
python -m unittest discover -s tests
```

## Project Structure

```text
src/
└── exam_trainer/
    ├── domain/
    │   ├── entities.py
    │   ├── exercise_definition.py
    │   ├── services.py
    │   ├── value_objects.py
    │   └── workspace.py
    ├── application/
    │   └── use_cases/
    ├── ports/
    ├── adapters/
    │   ├── compiler/
    │   ├── exercise_definition/
    │   ├── grader/
    │   ├── pack/
    │   ├── filesystem/
    │   ├── persistence/
    │   ├── workspace/
    │   └── ui/
    ├── infrastructure/
    └── main.py
tests/
```

## Creating an Exercise

Create a directory containing:

```text
my_exercise/
├── exercise.json
└── subject.md
```

For `function_with_main`, include the fixture:

```text
my_function/
├── exercise.json
├── main.c
└── subject.md
```

Keep `submission.filename` as a simple filename, not a path. Paths in JSON are relative to the exercise directory.

## Creating and Importing a Pack

Create a folder with:

```text
my_pack/
├── pack.json
└── level0/
    └── my_exercise/
        ├── exercise.json
        └── subject.md
```

The importer accepts a folder or ZIP, validates the full pack, and copies it to the app-managed pack directory only if every exercise is valid. In the UI, use `Importar Pack` and select either a `.zip` file or a folder.

## Training Modes

- `Treino por Level`: select one or more levels from a pack.
- `Treino Aleatório`: uses the same selection controls but chooses an exercise randomly.
- Selection options: prioritize uncompleted, only uncompleted, all exercises, and allow repeated.

After an exercise opens, use your external IDE to edit the generated workspace file, then click `Corrigir`.

## Exam Mode

The current exam mode is fail-fast:

- starts at the first level;
- FAIL keeps the same exercise and code;
- PASS advances to the next level automatically;
- score progresses by level;
- 100% completes the exam;
- timeout or manual end saves history and cleans the temporary `.exam` workspace;
- active exams can be resumed after reopening the app.

## Build With PyInstaller

PyInstaller is not a runtime dependency. To build on the current platform:

```bash
python -m pip install pyinstaller
python -m PyInstaller "42 Exam Trainer.spec" --noconfirm
```

The output is created under `dist/`.

Build separately on each target platform:

- Windows: run the command above on Windows to produce `.exe`.
- Linux: run the same command on Linux to produce a Linux binary.
- macOS: run the same command on macOS to produce a macOS app/binary.

Build packaging is intentionally outside the domain/application layers.

## MVP UI Flow

```text
Open app
↓
Configure workspace if needed
↓
Select sample_rank
↓
Select one or more levels
↓
Treino por Level / Treino Aleatório / Modo Prova
↓
Read subject
↓
Open IDE
↓
Write C solution in the workspace file
↓
Corrigir
↓
PASS/FAIL
↓
Ver trace
↓
Histórico
```

## Workspace Flow

```text
start app
    ↓
workspace configured?
    ↓
no → choose location → create → save
    ↓
yes
    ↓
main screen
    ↓
[Treino por Level]
[Treino Aleatório]
[Modo Prova]
```
