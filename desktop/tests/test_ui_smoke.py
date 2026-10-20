"""UI construction smoke tests - widgets only, no network, no mainloop."""
import time

import pytest

tk = pytest.importorskip("tkinter")

try:
    _root = tk.Tk()
    _root.withdraw()
except Exception:  # pragma: no cover - headless environments
    pytest.skip("No display available for Tkinter tests", allow_module_level=True)

from app.api_client import ApiClient  # noqa: E402
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
