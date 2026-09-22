# 42 Exam Trainer

42 Exam Trainer is a Python/PySide6 desktop app for practicing C exam workflows inspired by the 42 ecosystem.

This public repository contains the generic app engine: workspace management, pack validation, C compilation, grading, trace output, training mode, exam mode, SQLite progress/history, and a compact desktop UI.

It does not contain official 42 exam content, official subjects, official solutions, or any official Rank 02 original pack.

## Current MVP

The current MVP supports:

- external workspace selection;
- compact PySide6 UI;
- local JSON configuration;
- external editor/IDE integration;
- compatible C compiler detection;
- generic C grader for `program_output`, `function_with_main`, and validated pack capabilities;
- deterministic generators and internal expectations;
- technical traces for compile/runtime/output/timeout failures;
- SQLite attempts, progress, exam sessions, and history;
- pack import from folder or ZIP;
- training by level and random training;
- exam mode with fail-fast correction, resume, score, timeout, and cleanup.

## Navigation

The home screen intentionally stays small:

- `Treinar`
- `Modo Prova`
- `Histórico`
- `Configurações`

Training setup lives on its own screen. Choose `Treino por Level` or `Treino Aleatório`, then select pack/rank and options.

Exam setup lives on its own screen. If an exam session is active, `Continuar Prova` and `Encerrar Prova` appear there.

Settings centralizes:

- workspace;
- editor/IDE;
- compiler;
- packs.

## Requirements

- Python 3.12+
- PySide6
- A compatible C compiler

On Windows, the compiler must be MinGW/LLVM-MinGW compatible with POSIX-style exercise code. The detector validates candidates by compiling, linking, and running a console C program using:

```c
#include <unistd.h>

int main(void)
{
    write(1, "OK\n", 3);
    return (0);
}
```

with:

```text
-Wall -Wextra -Werror
```

The app does not adapt exercises to MSVC and does not remove `unistd.h`.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
```

On Linux/macOS:

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

On first launch, choose a workspace. You can change it later in `Configurações > Workspace`.

## Workspace Layout

Training and exam files are kept separate:

```text
workspace/
├── training/
│   └── <exercise>/
│       ├── subject.txt
│       └── <expected_file>.c
└── exam/
    └── <session_id>/
        └── <exercise>/
            ├── subject.txt
            └── <expected_file>.c
```

Training work remains saved. Starting a new implementation only clears that training exercise. Exam cleanup removes only the finished session directory under `exam/<session_id>/`.

## Editor/IDE

Settings supports known editors:

- VS Code
- Zed
- Cursor
- custom executable

The stored value is always a real filesystem path or command, never a `file:///` URI. Directories are rejected as editor executables. The editor is launched without `shell=True` using:

```python
[editor_executable, exercise_directory]
```

## Packs

Packs are managed from `Configurações > Packs`.

You can import:

- a folder;
- a `.zip`.

The importer validates the pack before copying it into the app-managed pack directory.

## Exercise Contract

An exercise declares itself with `exercise.json`:

```json
{
  "id": "steady_echo",
  "name": "Steady Echo",
  "subject": "subject.md",
  "submission": {
    "filename": "steady_echo.c"
  },
  "execution": {
    "type": "program_output"
  },
  "tests": {
    "generator": "random_arguments",
    "expectation": "echo_arguments"
  },
  "limits": {
    "timeout_seconds": 1
  }
}
```

Subjects should use the exam-style plain text format:

```text
Assignment name  : steady_echo
Expected files   : steady_echo.c
Allowed functions: write
--------------------------------------------------------------------------------

Write a program...

Examples:

$> ./steady_echo hello world | cat -e
hello world$
$>
```

The UI renders subjects as plain monospaced text to preserve whitespace and line breaks.

## Pack Contract

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

Each level contains exercise folders with `exercise.json` and `subject.md`. Function exercises may declare fixtures such as `main.c`.

## Training

Training supports:

- level-based selection;
- random selection;
- prioritizing uncompleted exercises;
- only uncompleted exercises;
- all exercises;
- allowing or disallowing repeats.

On FAIL, training shows a small failure dialog with actions to view the trace, reopen the editor, or return to fix the code. The app does not provide solution hints.

## Exam Mode

Exam mode keeps the existing rules:

- fail-fast correction;
- FAIL keeps the same exercise and workspace code;
- PASS advances automatically;
- 100% completes the exam;
- timeout saves partial score;
- closing/reopening can resume the active session;
- finishing removes only `workspace/exam/<session_id>/`.

## Trace

Trace output is technical and factual. It includes:

- collected file;
- compiler command;
- compiler output;
- test cases;
- expected output;
- actual output;
- stderr;
- timeout flag;
- final result.

## Tests

```bash
python -m unittest discover -s tests
python -m compileall -q src tests
```

## Build With PyInstaller

```bash
python -m pip install pyinstaller
python -m PyInstaller "42 Exam Trainer.spec" --noconfirm
```

Build on each target platform separately:

- Windows: produces a Windows executable.
- Linux: produces a Linux binary.
- macOS: produces a macOS app/binary.

Packaging stays outside the domain and application layers.
