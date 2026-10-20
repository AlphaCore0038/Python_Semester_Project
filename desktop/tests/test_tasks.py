"""Background-task runner tests with a fake scheduler (no Tk, no threads UI)."""
import threading

from app.tasks import TaskRunner


class FakeScheduler:
    """Stands in for Tk root.after: records callbacks, test runs them."""

    def __init__(self):
        self.calls = []

    def __call__(self, delay_ms, callback):
        self.calls.append(callback)

    def run_pending(self):
        pending, self.calls = self.calls, []
        for callback in pending:
            callback()


def wait_for(event: threading.Event):
    assert event.wait(timeout=5), "worker did not finish"


def test_success_callback_delivered_by_pump_on_main_thread():
    scheduler = FakeScheduler()
    runner = TaskRunner(scheduler)
    finished = threading.Event()
    seen = {}

    def work():
        finished.set()
        return 42

    def on_success(value):
        seen["value"] = value

    assert runner.submit(work, on_success=on_success) is True
    wait_for(finished)
    scheduler.run_pending()
    assert seen["value"] == 42
    assert runner.busy is False
    runner.shutdown()


def test_error_callback_receives_exception_and_done_always_runs():
    scheduler = FakeScheduler()
    runner = TaskRunner(scheduler)
    finished = threading.Event()
    seen = {}

    def work():
        finished.set()
        raise ValueError("kaboom")

    assert runner.submit(
        work,
        on_error=lambda exc: seen.setdefault("error", exc),
        on_done=lambda: seen.setdefault("done", True),
    )
    wait_for(finished)
    scheduler.run_pending()
    assert isinstance(seen["error"], ValueError)
    assert seen["done"] is True
    assert runner.busy is False
    runner.shutdown()


def test_single_in_flight_rejects_overlapping_submissions():
    scheduler = FakeScheduler()
    runner = TaskRunner(scheduler)
    release = threading.Event()
    finished = threading.Event()

    def slow():
        release.wait(timeout=5)
        finished.set()

    assert runner.submit(slow) is True
    assert runner.submit(slow) is None  # rejected while busy
    release.set()
    wait_for(finished)
    scheduler.run_pending()
    assert runner.busy is False
    # Accepts a new task after the previous one completed.
    done2 = threading.Event()
    assert runner.submit(lambda: done2.set()) is True
    wait_for(done2)
    scheduler.run_pending()
    runner.shutdown()


def test_shutdown_rejects_new_work():
    scheduler = FakeScheduler()
    runner = TaskRunner(scheduler)
    runner.shutdown()
    assert runner.submit(lambda: None) is None


def test_pump_reschedules_while_worker_running():
    scheduler = FakeScheduler()
    runner = TaskRunner(scheduler)
    finished = threading.Event()

    def work():
        finished.set()
        return "ok"

    runner.submit(work)
    assert scheduler.calls  # initial pump scheduled
    scheduler.run_pending()  # worker may not be done; pump must reschedule
    wait_for(finished)
    scheduler.run_pending()  # delivers the result
    assert runner.busy is False
    runner.shutdown()
