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

## Development Setup (official)

Always work inside a **project-local virtual environment** (`.venv` at the repository root). Never install the project into the global Python: an old editable install of another copy of this repository (for example `Documents\...\exam_simullator`) will silently win the `import exam_trainer` and you will run or test the wrong code.

Windows (PowerShell):

```powershell
git clone https://github.com/reginaldojr-dev/exam_simulator_app.git exam_simullator
cd exam_simullator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[build]"
```

If PowerShell refuses to run `Activate.ps1`, allow scripts for your user once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[build]"
```

The distribution name is `42-exam-trainer` (see `pyproject.toml`); the import package is `exam_trainer` under `src/`. The `build` extra installs PyInstaller in the same environment.

Check that the import comes from this checkout:

```bash
python -c "import exam_trainer, inspect; print(inspect.getfile(exam_trainer))"
```

It must print `<this repository>/src/exam_trainer/__init__.py`. `tests/test_environment.py` checks the same thing.

## Run

With the `.venv` active:

```bash
python -m exam_trainer.main
```

Or the console script `exam-trainer`.

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

## Creating Your Own Pack

42 Exam Trainer is not limited to Rank 02. Any rank, practice track, school list, or personal collection can be added as a pack as long as it follows the app contract and uses capabilities supported by the engine.

The program defines the contract; exercises adapt to the program. Packs cannot provide arbitrary shell commands, Python code, custom graders, or hidden executable logic.

### Minimal Directory Layout

```text
my_pack/
├── pack.json
└── level0/
    └── steady_echo/
        ├── exercise.json
        └── subject.md
```

A function exercise that needs a generated `main.c` can include a fixture:

```text
my_pack/
└── level1/
    └── sum_values/
        ├── exercise.json
        ├── subject.md
        └── fixtures/
            └── main.c
```

Fixture paths are relative to the exercise directory. They may prepare the test harness, but they must not contain the user's solution.

### pack.json

```json
{
  "id": "my_rank",
  "name": "My Rank",
  "version": "1.0.0",
  "levels": [
    { "id": "level0", "path": "level0" },
    { "id": "level1", "path": "level1" }
  ]
}
```

Keep `id` stable and filesystem-friendly. The `path` for each level is relative to the pack root.

### exercise.json for a Program

Use `program_output` when the user submits a complete C program. The grader compiles the expected file, runs it with generated/fixed arguments, captures stdout/stderr, and compares stdout with the expected value.

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
    "timeout_seconds": 2
  }
}
```

### exercise.json for a Function

Use `function_with_main` when the user submits a C function and the pack provides a `main.c` fixture to call it.

```json
{
  "id": "sum_values",
  "name": "Sum Values",
  "subject": "subject.md",
  "submission": {
    "filename": "sum_values.c"
  },
  "execution": {
    "type": "function_with_main",
    "fixture": "fixtures/main.c"
  },
  "tests": {
    "generator": "random_int_array",
    "expectation": "sum_integers"
  },
  "limits": {
    "timeout_seconds": 2
  }
}
```

If `execution.fixture` or `support_files` is declared, the referenced files must exist inside the exercise folder.

### subject.md

Subjects should be plain text or Markdown that preserves the exam-style shape. The UI renders subjects in a monospaced view and keeps whitespace intact.

```text
Assignment name  : steady_echo
Expected files   : steady_echo.c
Allowed functions: write
--------------------------------------------------------------------------------

Write a program that displays all command-line arguments on a single line,
separated by exactly one space, followed by a newline.

If no argument is provided, simply display a newline.

Examples:

$> ./steady_echo hello world | cat -e
hello world$
$> ./steady_echo | cat -e
$
$>
```

The `Expected files` line should match `submission.filename`.

### Supported Capabilities

Execution types currently recognized by the loader:

- `program_output`
- `function_with_main`
- `reference_compare`
- `custom`

`program_output` and `function_with_main` are the normal generic C grading paths. Other execution types are reserved/validated capabilities for supported project content; do not rely on them for new packs unless the app has an implementation for your workflow.

Generators currently available:

- `fixed_cases`
- `random_arguments`
- `random_int_array`
- `random_integer`
- `random_string`

Expectations currently available:

- `echo_arguments`
- `literal`
- `reference_output`
- `sum_integers`

For `fixed_cases`, include `tests.cases` in `exercise.json`. A simple fixed case can look like:

```json
{
  "args": ["hello", "world"],
  "stdin": "",
  "expected": "hello world\n"
}
```

### Validate and Import

1. Create the pack folder or a `.zip` containing it.
2. Open `Configurações > Packs`.
3. Click `Como criar um pack` for the in-app quick reference, or `Importar Pack` to import.
4. Select the folder or `.zip`.
5. The app validates `pack.json`, every `exercise.json`, referenced subjects, fixtures, support files, execution types, generators, and expectations.
6. If anything is invalid, the whole pack is rejected and nothing is copied.
7. If validation passes, the pack is copied into the app-managed pack directory and appears in training/exam setup.

Use the sample pack as a small working reference, but keep public packs free of official 42 subjects, official solutions, and copied exam content.

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

## Themes

The UI look lives in `src/exam_trainer/adapters/ui/qt/theme/` and is independent from screens, grader, packs and history.

- `tokens.py`: `ThemeTokens` (background, surface, accent, text_primary, text_secondary, success, fail, warning, border, hover_background, selected_background, fonts, radius, cursor behaviour).
- `themes.py`: built-in themes (`terminal` default, `minimal`, `amber`, `gameboy`, `neon`, `paper`).
- `qss.py`: builds the single application stylesheet from tokens.
- `manager.py`: `ThemeManager` applies the stylesheet and notifies screens when the theme changes.

Screens never write colors or QSS. They create widgets through `adapters/ui/qt/components/widgets.py` and set a role (`variant="primary"`, `role="title"`, `status="fail"`...). The blinking cursor is centralized in `components/cursor.py` (one `QTimer` for the whole window).

To add a theme, create a new `ThemeTokens` in `themes.py` and register it in `THEMES`. It appears in `Configurações > Tema` and is saved in the local config file. Rule for every theme: the accent color is never the background of a button, row, tab or selected item.

## Tests

With the `.venv` active, from the repository root:

```bash
python -m unittest discover -s tests
python -m compileall -q src tests
```

Tests that need the private `packs/rank02-original` fail when that folder is absent.

## Build With PyInstaller

Build from the project `.venv`. PyInstaller bundles the dependencies of the interpreter that runs it, so building from the global Python can ship the wrong PySide6 or pick up another copy of the project. `build.py` prints a warning when it is not running inside `.venv`.

```bash
python build.py            # build
python build.py --run      # rebuild only if sources changed, then open the executable
python build.py --force    # always rebuild
```

`python build.py --run` exits with code `3` when the build is fine but the operating system refused to open the executable. On Windows this is usually Smart App Control / App Control (`WinError 4551`) blocking an unsigned executable. The build is not broken: run from source with `python -m exam_trainer.main`. Public releases will need signed builds.

Build on each target platform separately:

- Windows: produces a Windows executable.
- Linux: produces a Linux binary.
- macOS: produces a macOS app/binary.

Packaging stays outside the domain and application layers.

## Troubleshooting

**`ModuleNotFoundError: No module named 'exam_trainer.adapters...'` or a traceback pointing to another folder.** Another copy of the project is installed in the Python you are using. Check with `python -m pip show 42-exam-trainer` (look at `Editable project location`). Fix: activate this repository's `.venv` and run `python -m pip install -e ".[build]"`. If the old copy is installed in the global Python, remove it there with `python -m pip uninstall 42-exam-trainer`.

**`WinError 4551` when opening the executable.** Windows App Control blocked an unsigned executable. See "Build With PyInstaller".
