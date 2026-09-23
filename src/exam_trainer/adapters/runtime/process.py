"""Execução de processo compartilhada pelos runtimes: sem shell, com timeout."""

from __future__ import annotations

import subprocess
from pathlib import Path

from exam_trainer.ports.runtime_port import ProcessOutcome


def run_process(
    argv: list[str],
    stdin: str,
    timeout_seconds: int,
    cwd: Path | None = None,
) -> ProcessOutcome:
    try:
        completed = subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            cwd=None if cwd is None else str(cwd),
        )
    except subprocess.TimeoutExpired as error:
        return ProcessOutcome(
            stdout=error.stdout if isinstance(error.stdout, str) else "",
            stderr=error.stderr if isinstance(error.stderr, str) else "",
            timed_out=True,
        )
    except OSError as error:
        return ProcessOutcome(stderr=f"could not start process: {error}", exit_code=None)
    return ProcessOutcome(
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
    )
