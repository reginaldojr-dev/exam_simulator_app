"""Heavy work execution outside the UI thread.

Everything that spawns external processes or does heavier disk work (grading,
importing/validating packs, detecting/validating compilers) goes through here.
Success/error callbacks are always delivered on the UI thread through queued Qt
signals, so they may safely touch widgets.

Rules:
- a key can have only one in-flight task: `start` returns False if another is
  already running, which prevents duplicate submissions;
- the worker function MUST NOT touch widgets;
- exceptions become `on_error(exc)` and never rise as traceback to the user.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QCoreApplication, QDeadlineTimer, QObject, QRunnable, QThreadPool, Signal, Slot


class _Relay(QObject):
    """Lives on the UI thread; worker-emitted signals arrive queued."""

    finished = Signal(str, object)
    failed = Signal(str, object)


class _Job(QRunnable):
    def __init__(self, key: str, work: Callable[[], Any], relay: _Relay) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._key = key
        self._work = work
        self._relay = relay

    def run(self) -> None:  # thread da pool
        try:
            result = self._work()
        except BaseException as error:  # noqa: BLE001 - everything becomes on_error
            self._relay.failed.emit(self._key, error)
            return
        self._relay.finished.emit(self._key, result)


class TaskRunner(QObject):
    def __init__(self, parent: QObject | None = None, pool: QThreadPool | None = None) -> None:
        super().__init__(parent)
        self._pool = pool or QThreadPool.globalInstance()
        self._relay = _Relay(self)
        self._relay.finished.connect(self._on_finished)
        self._relay.failed.connect(self._on_failed)
        self._callbacks: dict[str, tuple[Callable[[Any], None], Callable[[BaseException], None]]] = {}

    def is_busy(self, key: str | None = None) -> bool:
        return bool(self._callbacks) if key is None else key in self._callbacks

    def start(
        self,
        key: str,
        work: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
    ) -> bool:
        if key in self._callbacks:
            return False
        self._callbacks[key] = (on_done, on_error)
        self._pool.start(_Job(key, work, self._relay))
        return True

    def wait(self, timeout_ms: int = 30_000) -> bool:
        """For tests/shutdown: wait for tasks and deliver callbacks."""
        deadline = QDeadlineTimer(timeout_ms)
        while self._callbacks and not deadline.hasExpired():
            self._pool.waitForDone(50)
            QCoreApplication.processEvents()
        return not self._callbacks

    @Slot(str, object)
    def _on_finished(self, key: str, result: object) -> None:
        callbacks = self._callbacks.pop(key, None)
        if callbacks is not None:
            callbacks[0](result)

    @Slot(str, object)
    def _on_failed(self, key: str, error: object) -> None:
        callbacks = self._callbacks.pop(key, None)
        if callbacks is not None:
            callbacks[1](error)  # type: ignore[arg-type]
