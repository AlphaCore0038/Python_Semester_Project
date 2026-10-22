"""UI construction smoke tests - widgets only, no network, no mainloop."""
import time
from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")

try:
    _root = tk.Tk()
    _root.withdraw()
except Exception:  # pragma: no cover - headless environments
    pytest.skip("No display available for Tkinter tests", allow_module_level=True)

from app.api_client import ApiClient, ApiError  # noqa: E402
from app.session import Session, SessionStore  # noqa: E402
from app.tasks import TaskRunner  # noqa: E402
from app.views import AIDialog, LoginView, MainView, format_size, format_timestamp  # noqa: E402


@pytest.fixture
def root():
    yield _root


@pytest.fixture
def runner(root):
    task_runner = TaskRunner(root.after)
    yield task_runner
    task_runner.shutdown()


def test_login_view_constructs(root, runner, tmp_path):
    view = LoginView(root, ApiClient("http://127.0.0.1:9"),
                     SessionStore(tmp_path / "s.json"), runner,
                     on_authenticated=lambda s: None)
    root.update_idletasks()
    assert view.submit_btn.winfo_exists()
    view.destroy()


def test_main_view_constructs(root, runner, tmp_path):
    """Constructing must not touch the network (refresh is deferred via after)."""
    session = Session("token", "ana@example.com", time.time() + 3600)
    view = MainView(root, ApiClient("http://127.0.0.1:9"),
                    SessionStore(tmp_path / "s.json"), runner, session,
                    on_logged_out=lambda m=None: None)
    root.update()
    assert view.tree.winfo_exists()
    view.destroy()


def test_logout_revokes_remotely_and_always_clears_locally():
    calls = []

    class FailingClient:
        def logout(self, token):
            calls.append(token)
            raise ApiError(0, "backend unreachable")

    logged_out = []
    view = SimpleNamespace(
        client=FailingClient(),
        session=Session("token", "ana@example.com", time.time() + 3600),
        on_logged_out=lambda message=None: logged_out.append(message),
    )
    MainView._logout(view)
    assert calls == ["token"]
    assert logged_out == [None]


def test_format_helpers():
    assert format_size(0) == "0 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(524288000) == "500.0 MB"
    assert format_timestamp("2026-10-20T10:30:00Z") == "2026-10-20 10:30 UTC"


def test_ai_dialog_constructs_with_local_placeholder(root, runner, tmp_path):
    session = Session("token", "ana@example.com", time.time() + 3600)
    main = MainView(root, ApiClient("http://127.0.0.1:9"),
                    SessionStore(tmp_path / "s.json"), runner, session,
                    on_logged_out=lambda m=None: None)
    dialog = AIDialog(main, ApiClient("http://127.0.0.1:9"),
                      SessionStore(tmp_path / "s.json"), runner, session)
    root.update_idletasks()
    assert dialog.send_btn.winfo_exists()
    assert dialog.apply_btn.instate(["disabled"])  # proposals require an explicit request
    # Local AI is a visibly disabled placeholder, never a selectable mode.
    assert dialog.mode_var.get() == "ask"
    dialog.destroy()
    main.destroy()


def test_ai_suggestion_apply_confirm_cancel_and_refresh(root, runner, tmp_path, monkeypatch):
    """Regression: on_renamed must be a callable (was a Tk after-id string),
    confirming must go through client.rename, cancelling must not."""
    from app import views as views_module

    session = Session("token", "ana@example.com", time.time() + 3600)
    main = MainView(root, ApiClient("http://127.0.0.1:9"),
                    SessionStore(tmp_path / "s.json"), runner, session,
                    on_logged_out=lambda m=None: None)
    root.update()

    dialog = main._open_ai()
    assert dialog is not None
    assert callable(dialog.on_renamed)  # the exact Phase 8 bug: was "after#N"

    class SyncRunner:
        busy = False

        def submit(self, fn, on_success=None, on_error=None, on_done=None):
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                if on_error:
                    on_error(exc)
            else:
                if on_success:
                    on_success(result)
            if on_done:
                on_done()
            return True

    rename_calls = []

    class FakeClient:
        def rename(self, token, document_id, filename):
            rename_calls.append((token, document_id, filename))
            return {"id": document_id, "filename": filename}

    refreshed = []
    monkeypatch.setattr(main, "refresh", lambda: refreshed.append(True))
    dialog.client = FakeClient()
    dialog.runner = SyncRunner()

    # Confirm path: rename invoked; success callback schedules refresh (no TypeError).
    monkeypatch.setattr(views_module.messagebox, "askyesno", lambda *a, **k: True)
    dialog._suggestion = {"doc_id": "d1", "data": {"suggested_filename": "better.txt"}}
    dialog._apply_suggestion()  # ok() calls on_renamed() synchronously via SyncRunner
    assert rename_calls == [("token", "d1", "better.txt")]
    assert dialog._suggestion is None
    root.update()  # flush the after_idle-scheduled main.refresh
    assert refreshed == [True]

    # Cancel path: nothing renamed, suggestion kept for another try.
    monkeypatch.setattr(views_module.messagebox, "askyesno", lambda *a, **k: False)
    dialog._suggestion = {"doc_id": "d1", "data": {"suggested_filename": "other.txt"}}
    dialog._apply_suggestion()
    assert rename_calls == [("token", "d1", "better.txt")]  # unchanged
    assert dialog._suggestion is not None

    dialog.destroy()
    main.destroy()
