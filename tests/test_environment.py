"""Garante que `exam_trainer` vem DESTE repositório.

Pega o caso de uma instalação editable de outra cópia do projeto
(ex.: Documents/ChatGPT/exam_simullator) sequestrando o import.
Roda num processo novo, a partir da raiz do projeto, como o usuário faria.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class EnvironmentTest(unittest.TestCase):
    def test_exam_trainer_is_imported_from_this_checkout(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-c", "import exam_trainer, inspect; print(inspect.getfile(exam_trainer))"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            "exam_trainer não é importável. Rode: python -m pip install -e . (dentro da .venv)\n" + completed.stderr,
        )
        origin = Path(completed.stdout.strip()).resolve()
        expected = (ROOT / "src" / "exam_trainer").resolve()
        self.assertEqual(
            origin.parent,
            expected,
            f"exam_trainer vem de {origin}, não de {expected}. "
            "Há outra cópia instalada: veja README > Troubleshooting.",
        )


if __name__ == "__main__":
    unittest.main()
