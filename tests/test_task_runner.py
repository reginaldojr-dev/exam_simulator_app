from __future__ import annotations

import os
import threading
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from exam_trainer.adapters.ui.qt.task_runner import TaskRunner


class TaskRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_result_is_delivered_on_the_ui_thread(self) -> None:
        runner = TaskRunner()
        ui_thread = threading.get_ident()
        seen: dict[str, int] = {}

        def work() -> int:
            seen["work"] = threading.get_ident()
            return 42

        results: list[int] = []

        def done(value: int) -> None:
            seen["done"] = threading.get_ident()
            results.append(value)

        self.assertTrue(runner.start("k", work, done, self.fail))
        self.assertTrue(runner.wait())
        self.assertEqual(results, [42])
        self.assertNotEqual(seen["work"], ui_thread)
        self.assertEqual(seen["done"], ui_thread)

    def test_same_key_cannot_run_twice(self) -> None:
        runner = TaskRunner()
        gate = threading.Event()
        self.assertTrue(runner.start("k", gate.wait, lambda _: None, self.fail))
        self.assertTrue(runner.is_busy("k"))
        self.assertFalse(runner.start("k", lambda: None, lambda _: None, self.fail))
        gate.set()
        self.assertTrue(runner.wait())
        self.assertFalse(runner.is_busy())

    def test_exception_goes_to_on_error(self) -> None:
        runner = TaskRunner()
        errors: list[BaseException] = []

        def boom() -> None:
            raise ValueError("pack inválido")

        runner.start("k", boom, lambda _: self.fail("não deveria concluir"), errors.append)
        self.assertTrue(runner.wait())
        self.assertEqual([str(error) for error in errors], ["pack inválido"])


if __name__ == "__main__":
    unittest.main()
