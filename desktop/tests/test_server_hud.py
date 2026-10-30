# desktop/tests/test_server_hud.py: Tests for tests.
"""Tests for the standalone PyServer HUD."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from server_hud import (              
    ServerConfig,
    ServerProcess,
    SettingsStore,
    build_command,
    build_launcher,
    default_settings,
    port_is_open,
    validate_config,
    wait_for_port,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _write_dummy_server(path: Path) -> None:
    path.write_text(
        "import sys\n"
        "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
        "\n"
        "class Handler(BaseHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        self.send_response(200)\n"
        "        self.end_headers()\n"
        "        self.wfile.write(b'hud-ok')\n"
        "    def log_message(self, fmt, *args):\n"
        "        print('dummy:', fmt % args, flush=True)\n"
        "\n"
        "HTTPServer(('127.0.0.1', int(sys.argv[1])), Handler).serve_forever()\n",
        encoding="utf-8",
    )


def _start_dummy(tmp_path: Path, script: Path, port: int) -> ServerProcess:
    controller = ServerProcess(tmp_path, show_console=False)
    controller.start_command(
        [sys.executable, "-u", str(script), str(port)],
        tmp_path,
        "dummy",
    )
    return controller


def test_default_settings_target_this_repository():
    settings = default_settings()
    assert settings["django"]["project_dir"].endswith("web")
    assert settings["fastapi"]["project_dir"].endswith("backend")
    assert settings["fastapi"]["asgi_target"] == "app.main:app"


def test_settings_round_trip_and_corrupt_file_falls_back(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = store.load()
    settings["framework"] = "fastapi"
    settings["fastapi"]["python"] = "C:/custom/python.exe"
    store.save(settings)

    loaded = store.load()
    assert loaded["framework"] == "fastapi"
    assert loaded["fastapi"]["python"] == "C:/custom/python.exe"

    path.write_text("{not json", encoding="utf-8")
    assert SettingsStore(path).load()["framework"] == "django"


def test_commands_use_required_ports_and_asgi_target(tmp_path):
    django = ServerConfig("django", tmp_path, Path(sys.executable))
    fastapi = ServerConfig("fastapi", tmp_path, Path(sys.executable), "app.main:app")
    assert build_command(django)[-1] == "127.0.0.1:8000"
    assert "manage.py" in build_command(django)
    assert build_command(fastapi)[-1] == "8001"
    assert "app.main:app" in build_command(fastapi)
    assert django.url == "http://127.0.0.1:8000"
    assert fastapi.url == "http://127.0.0.1:8001"


def test_validation_rejects_missing_project_and_bad_target(tmp_path):
    missing = ServerConfig("django", tmp_path / "missing", Path(sys.executable))
    with pytest.raises(ValueError, match="Project folder"):
        validate_config(missing)

    fastapi = ServerConfig("fastapi", tmp_path, Path(sys.executable), "app")
    with pytest.raises(ValueError, match="module:app"):
        validate_config(fastapi)


def test_launcher_mirrors_errors_to_console_and_log(tmp_path):
    launcher = build_launcher(
        [sys.executable, "-u", "manage.py", "runserver"],
        tmp_path,
        "Django",
        tmp_path / "server.log",
        Path("hud_tee.py"),
    )
    assert "@echo off" in launcher
    assert "2>&1 |" in launcher
    assert "title PyServer HUD - Django" in launcher
    assert "server.log" in launcher


def test_hud_constructs_switches_frameworks_and_persists(tmp_path):
    desktop = Path(__file__).resolve().parents[1]
    settings_path = tmp_path / "settings.json"
    script = tmp_path / "check_hud.py"
    script.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "from server_hud import ServerHud\n"
        "settings_path = Path(sys.argv[1])\n"
        "hud = ServerHud(settings_path=settings_path, show_console=False)\n"
        "hud.withdraw()\n"
        "hud.update_idletasks()\n"
        "assert hud.title() == 'PyServer HUD'\n"
        "assert hud.framework == 'django'\n"
        "assert hud.url_var.get() == 'http://127.0.0.1:8000'\n"
        "assert hud.start_button._enabled\n"
        "assert not hud.stop_button._enabled\n"
        "hud._select_framework('fastapi')\n"
        "assert hud.framework == 'fastapi'\n"
        "assert hud.url_var.get() == 'http://127.0.0.1:8001'\n"
        "assert hud.docs_button.winfo_manager() == 'grid'\n"
        "hud._select_framework('django')\n"
        "assert hud.framework == 'django'\n"
        "assert hud.docs_button.winfo_manager() == ''\n"
        "hud._save_settings()\n"
        "hud.destroy()\n"
        "print(json.dumps({'ok': True}))\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(desktop)
    result = subprocess.run(
        [sys.executable, str(script), str(settings_path)],
        cwd=desktop,
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )
    if result.returncode and "no display" in (result.stderr + result.stdout).lower():
        pytest.skip("No display available for Tkinter tests")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved["framework"] == "django"


def test_tab_switching_keeps_server_states_independent(tmp_path):
    desktop = Path(__file__).resolve().parents[1]
    settings_path = tmp_path / "settings.json"
    script = tmp_path / "check_independent_tabs.py"
    script.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "from server_hud import ServerHud\n"
        "\n"
        "class FakeController:\n"
        "    def __init__(self):\n"
        "        self.running = False\n"
        "        self.process = None\n"
        "        self.log_path = Path('unused.log')\n"
        "\n"
        "hud = ServerHud(settings_path=Path(sys.argv[1]), show_console=False)\n"
        "hud.withdraw()\n"
        "hud.controllers = {'django': FakeController(), 'fastapi': FakeController()}\n"
        "hud.settings['django']['project_dir'] = 'C:/kept/django'\n"
        "hud.settings['fastapi']['project_dir'] = 'C:/kept/fastapi'\n"
        "hud.settings['fastapi']['asgi_target'] = 'kept.asgi:app'\n"
        "hud._load_fields()\n"
        "\n"
        "def view(framework):\n"
        "    hud._select_framework(framework)\n"
        "    hud._update_controls()\n"
        "    return {\n"
        "        'framework': hud.framework,\n"
        "        'start': hud.start_button._enabled,\n"
        "        'stop': hud.stop_button._enabled,\n"
        "        'tabs': (hud.django_tab._enabled, hud.fastapi_tab._enabled),\n"
        "        'fields': hud.project_entry.cget('state'),\n"
        "        'status': hud.status_label.cget('text'),\n"
        "        'url': hud.url_var.get(),\n"
        "        'project': hud.project_var.get(),\n"
        "        'target': hud.target_var.get(),\n"
        "    }\n"
        "\n"
        "# Both stopped: both Start buttons are usable.\n"
        "django_stopped = view('django')\n"
        "fastapi_stopped = view('fastapi')\n"
        "assert django_stopped['start'] and not django_stopped['stop']\n"
        "assert fastapi_stopped['start'] and not fastapi_stopped['stop']\n"
        "assert all(django_stopped['tabs'] + fastapi_stopped['tabs'])\n"
        "assert django_stopped['project'] == 'C:/kept/django'\n"
        "assert fastapi_stopped['project'] == 'C:/kept/fastapi'\n"
        "assert fastapi_stopped['target'] == 'kept.asgi:app'\n"
        "\n"
        "# Django running, FastAPI stopped: only Django's Start is disabled.\n"
        "hud.controllers['django'].running = True\n"
        "django_running = view('django')\n"
        "fastapi_with_django_running = view('fastapi')\n"
        "assert django_running['start'] is False\n"
        "assert django_running['stop'] is True\n"
        "assert fastapi_with_django_running['start'] is True\n"
        "assert fastapi_with_django_running['stop'] is False\n"
        "assert fastapi_with_django_running['fields'] == 'normal'\n"
        "assert fastapi_with_django_running['url'].endswith(':8001')\n"
        "assert hud.controllers['django'].running is True\n"
        "assert hud.controllers['fastapi'].running is False\n"
        "\n"
        "# FastAPI running, Django stopped: only FastAPI's Start is disabled.\n"
        "hud.controllers['django'].running = False\n"
        "hud.controllers['fastapi'].running = True\n"
        "fastapi_running = view('fastapi')\n"
        "django_with_fastapi_running = view('django')\n"
        "assert fastapi_running['start'] is False\n"
        "assert fastapi_running['stop'] is True\n"
        "assert django_with_fastapi_running['start'] is True\n"
        "assert django_with_fastapi_running['stop'] is False\n"
        "assert hud.controllers['django'].running is False\n"
        "assert hud.controllers['fastapi'].running is True\n"
        "\n"
        "# Both running: both Stop buttons stay enabled.\n"
        "hud.controllers['django'].running = True\n"
        "both_django = view('django')\n"
        "both_fastapi = view('fastapi')\n"
        "assert both_django['start'] is False and both_django['stop'] is True\n"
        "assert both_fastapi['start'] is False and both_fastapi['stop'] is True\n"
        "\n"
        "# Switching tabs must not stop either server or reset configuration fields.\n"
        "django_before = hud.settings['django']['project_dir']\n"
        "fastapi_before = hud.settings['fastapi']['project_dir']\n"
        "target_before = hud.settings['fastapi']['asgi_target']\n"
        "view('django')\n"
        "view('fastapi')\n"
        "view('django')\n"
        "assert hud.controllers['django'].running is True\n"
        "assert hud.controllers['fastapi'].running is True\n"
        "assert hud.settings['django']['project_dir'] == django_before\n"
        "assert hud.settings['fastapi']['project_dir'] == fastapi_before\n"
        "assert hud.settings['fastapi']['asgi_target'] == target_before\n"
        "assert django_before == 'C:/kept/django'\n"
        "assert fastapi_before == 'C:/kept/fastapi'\n"
        "assert target_before == 'kept.asgi:app'\n"
        "hud.destroy()\n"
        "print('independent-tabs-ok')\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(desktop)
    result = subprocess.run(
        [sys.executable, str(script), str(settings_path)],
        cwd=desktop,
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )
    if result.returncode and "no display" in (result.stderr + result.stdout).lower():
        pytest.skip("No display available for Tkinter tests")
    assert result.returncode == 0, result.stderr
    assert "independent-tabs-ok" in result.stdout


def test_process_starts_serves_and_stops_with_log(tmp_path):
    port = _free_port()
    script = tmp_path / "dummy_server.py"
    _write_dummy_server(script)
    controller = _start_dummy(tmp_path, script, port)
    try:
        assert wait_for_port(port, timeout=12)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=5) as response:
            assert response.read() == b"hud-ok"
        assert controller.running
    finally:
        controller.stop()

    assert controller.process is None
    deadline = time.monotonic() + 5
    while port_is_open(port) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not port_is_open(port)
    log_text = controller.log_path.read_text(encoding="utf-8")
    assert "PyServer HUD log" in log_text
    assert "dummy:" in log_text


def test_stopping_one_server_leaves_another_running(tmp_path):
    first_port, second_port = _free_port(), _free_port()
    script = tmp_path / "dummy_server.py"
    _write_dummy_server(script)
    first = _start_dummy(tmp_path / "first", script, first_port)
    second = _start_dummy(tmp_path / "second", script, second_port)
    try:
        assert wait_for_port(first_port, timeout=12)
        assert wait_for_port(second_port, timeout=12)
        first.stop()
        assert not port_is_open(first_port)
        assert port_is_open(second_port)
    finally:
        first.stop()
        second.stop()
    assert not port_is_open(second_port)


def test_stderr_traceback_is_captured_in_log(tmp_path):
    script = tmp_path / "fail.py"
    script.write_text("raise RuntimeError('hud-boom')\n", encoding="utf-8")
    controller = ServerProcess(tmp_path, show_console=False)
    try:
        controller.start_command(
            [sys.executable, "-u", str(script)],
            tmp_path,
            "failing",
        )
        deadline = time.monotonic() + 10
        while controller.running and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not controller.running
    finally:
        controller.stop()

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if controller.log_path.exists() and "hud-boom" in controller.log_path.read_text(
            encoding="utf-8", errors="replace"
        ):
            break
        time.sleep(0.1)
    log_text = controller.log_path.read_text(encoding="utf-8", errors="replace")
    assert "Traceback" in log_text
    assert "RuntimeError: hud-boom" in log_text
