"""Background operations for Tkinter.

Network and blocking file work runs in a small thread pool; results are
delivered to the main thread through a queue that a pump function drains
using the caller-supplied scheduler (root.after in the real app, a fake in
tests). ALL Tkinter widget updates happen inside the main-thread pump.

Single in-flight operation by design: submit() returns None while busy,
so the UI can disable action buttons and never overlap uploads/downloads.
"""
from __future__ import annotations

import queue
from concurrent.futures import ThreadPoolExecutor
from typing import Callable


class TaskRunner:
    def __init__(self, schedule_after: Callable[[int, Callable[[], None]], object],
                 poll_ms: int = 50):
        self._schedule = schedule_after
        self._poll_ms = poll_ms
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="locker-task")
        self._busy = False
        self._inflight = 0
        self._pump_scheduled = False
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._busy

    def submit(self, fn, on_success=None, on_error=None, on_done=None):
        """Runs fn() in a worker thread. Callbacks run on the main thread.
        Returns True if accepted, None if busy/closed (single-in-flight)."""
        if self._busy or self._closed:
            return None
        self._busy = True
        self._inflight += 1

        def work():
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001 - mapped by the UI layer
                self._queue.put(("error", on_error, exc, on_done))
            else:
                self._queue.put(("success", on_success, result, on_done))

        self._executor.submit(work)
        self._ensure_pump()
        return True

    def _ensure_pump(self):
        if not self._pump_scheduled and not self._closed:
            self._pump_scheduled = True
            self._schedule(self._poll_ms, self._pump)

    def _pump(self):
        self._pump_scheduled = False
        while True:
            try:
                kind, callback, payload, on_done = self._queue.get_nowait()
            except queue.Empty:
                break
            self._inflight = max(0, self._inflight - 1)
            self._busy = self._inflight > 0
            try:
                if callback is not None:
                    callback(payload)
            finally:
                if on_done is not None:
                    on_done()
        if self._inflight > 0 and not self._closed:
            self._ensure_pump()

    def shutdown(self) -> None:
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
