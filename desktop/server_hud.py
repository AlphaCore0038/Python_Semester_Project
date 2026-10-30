"""Compact desktop control panel for local Django and FastAPI servers."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog
import tkinter as tk

from app import theme


APP_NAME = "PyServerHUD"
WINDOW_TITLE = "PyServer HUD"
HOST = "127.0.0.1"
PORTS = {"django": 8000, "fastapi": 8001}
DEFAULT_ASGI_TARGET = "main:app"
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_REPO_ROOT = Path(__file__).resolve().parent.parent


def default_data_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    return Path(base) / APP_NAME if base else Path.home() / f".{APP_NAME.lower()}"


def _repo_python(venv: str) -> Path:
    candidate = _REPO_ROOT / venv / "Scripts" / "python.exe"
    return candidate if candidate.is_file() else Path(sys.executable)


def default_settings() -> dict:
    fastapi_target = "app.main:app" if (_REPO_ROOT / "backend" / "app" / "main.py").is_file() else DEFAULT_ASGI_TARGET
    return {
        "framework": "django",
        "django": {
            "project_dir": str(_REPO_ROOT / "web"),
            "python": str(_repo_python("web/.venv")),
        },
        "fastapi": {
            "project_dir": str(_REPO_ROOT / "backend"),
            "python": str(_repo_python("backend/.venv")),
            "asgi_target": fastapi_target,
        },
    }


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else default_data_dir() / "settings.json"

    def load(self) -> dict:
        settings = default_settings()
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return settings
        if not isinstance(saved, dict):
            return settings

        if saved.get("framework") in PORTS:
            settings["framework"] = saved["framework"]
        for framework in PORTS:
            section = saved.get(framework)
            if not isinstance(section, dict):
                continue
            for field in ("project_dir", "python", "asgi_target"):
                value = section.get(field)
                if isinstance(value, str) and value.strip():
                    settings[framework][field] = value
        return settings

    def save(self, settings: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        temporary.replace(self.path)


@dataclass(frozen=True)
class ServerConfig:
    framework: str
    project_dir: Path
    python: Path
    asgi_target: str = ""

    @property
    def label(self) -> str:
        return "Django" if self.framework == "django" else "FastAPI"

    @property
    def port(self) -> int:
        return PORTS[self.framework]

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self.port}"

    @property
    def docs_url(self) -> str:
        return f"{self.url}/docs"


def build_command(config: ServerConfig) -> list[str]:
    if config.framework == "django":
        return [
            str(config.python),
            "-u",
            "manage.py",
            "runserver",
            f"{HOST}:{config.port}",
        ]
    return [
        str(config.python),
        "-u",
        "-m",
        "uvicorn",
        config.asgi_target.strip(),
        "--reload",
        "--host",
        HOST,
        "--port",
        str(config.port),
    ]


def validate_config(config: ServerConfig) -> None:
    if not config.project_dir.is_dir():
        raise ValueError("Project folder not found.")
    if not config.python.is_file():
        raise ValueError("Python interpreter not found.")
    if config.framework == "django":
        if not (config.project_dir / "manage.py").is_file():
            raise ValueError("No manage.py found in the project folder.")
    elif not config.asgi_target.strip() or ":" not in config.asgi_target:
        raise ValueError("ASGI target must look like module:app.")


def port_is_open(port: int, host: str = HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def wait_for_port(port: int, timeout: float = 10.0, host: str = HOST) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_open(port, host):
            return True
        time.sleep(0.1)
    return False


def _cmd_quote(value: object) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _tee_python() -> Path:
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        console_python = executable.with_name("python.exe")
        if console_python.is_file():
            return console_python
    return executable


def build_launcher(
    command: list[str],
    project_dir: Path,
    label: str,
    log_path: Path,
    tee_script: Path,
) -> str:
    server = " ".join(_cmd_quote(part) for part in command)
    tee = " ".join(
        _cmd_quote(part)
        for part in (_tee_python(), "-u", tee_script, log_path)
    )
    lines = [
        "@echo off",
        f"title PyServer HUD - {label}",
        f"cd /d {_cmd_quote(project_dir)}",
        f"{server} 2>&1 | {tee}",
    ]
    return "\r\n".join(lines) + "\r\n"


class ServerProcess:
    def __init__(self, data_dir: Path | None = None, show_console: bool = True):
        self.data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
        self.launcher_path = self.data_dir / "run_server.cmd"
        self.log_path = self.data_dir / "server.log"
        self.show_console = show_console
        self._process: subprocess.Popen | None = None

    @property
    def process(self) -> subprocess.Popen | None:
        return self._process

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self, config: ServerConfig) -> None:
        self.start_command(build_command(config), config.project_dir, config.label)

    def start_command(self, command: list[str], project_dir: Path, label: str = "server") -> None:
        if self.running:
            raise RuntimeError("A server is already running.")
        self._process = None
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.launcher_path.write_text(
            build_launcher(
                command,
                project_dir,
                label,
                self.log_path,
                Path(__file__).with_name("hud_tee.py"),
            ),
            encoding="utf-8",
            newline="",
        )
        flags = CREATE_NEW_CONSOLE if self.show_console else CREATE_NO_WINDOW
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        self._process = subprocess.Popen(
            [comspec, "/c", "call", str(self.launcher_path)],
            cwd=str(project_dir),
            creationflags=flags,
        )

    def stop(self) -> None:
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
                timeout=10,
                check=False,
            )
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        self._process = None


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command,
        *,
        width: int = 96,
        height: int = 34,
        fill: str = theme.SURFACE_2,
        hover: str = theme.SURFACE_3,
        pressed: str = theme.LINE,
        selected_fill: str | None = None,
        selected_text: str | None = None,
        text_color: str = theme.TEXT,
        disabled_fill: str = theme.SURFACE,
        disabled_text: str = theme.FAINT,
        font: tuple | None = None,
        radius: int = 10,
    ):
        parent_bg = parent.cget("bg")
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._text = text
        self._command = command
        self._fill = fill
        self._hover_fill = hover
        self._pressed_fill = pressed
        self._selected_fill = selected_fill
        self._selected_text = selected_text or text_color
        self._text_color = text_color
        self._disabled_fill = disabled_fill
        self._disabled_text = disabled_text
        self._font = font or (theme.FONT, 9, "bold")
        self._radius = radius
        self._enabled = True
        self._selected = False
        self._hovered = False
        self._pressed = False
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.after_idle(self._draw)

    def _draw(self, _event=None) -> None:
        self.delete("all")
        width = self.winfo_width() or int(self.cget("width"))
        height = self.winfo_height() or int(self.cget("height"))
        if not self._enabled:
            fill, text_color = self._disabled_fill, self._disabled_text
        elif self._pressed and self._hovered:
            fill, text_color = self._pressed_fill, self._text_color
        elif self._selected:
            fill, text_color = self._selected_fill or self._fill, self._selected_text
        elif self._hovered:
            fill, text_color = self._hover_fill, self._text_color
        else:
            fill, text_color = self._fill, self._text_color

        radius = min(self._radius, height // 2)
        points = [
            radius, 0, width - radius, 0, width, 0, width, radius,
            width, height - radius, width, height, width - radius, height,
            radius, height, 0, height, 0, height - radius, 0, radius, 0, 0,
        ]
        self.create_polygon(
            points, smooth=True, splinesteps=24, fill=fill, outline=fill
        )
        self.create_text(
            width / 2,
            height / 2,
            text=self._text,
            fill=text_color,
            font=self._font,
        )

    def _on_enter(self, _event) -> None:
        if self._enabled:
            self._hovered = True
            self._draw()

    def _on_leave(self, _event) -> None:
        self._hovered = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event) -> None:
        if self._enabled:
            self._pressed = True
            self._hovered = True
            self._draw()

    def _on_release(self, event) -> None:
        if not self._enabled:
            return
        inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        was_pressed = self._pressed
        self._pressed = False
        self._hovered = inside
        self._draw()
        if was_pressed and inside:
            self._command()

    def invoke(self) -> None:
        if self._enabled:
            self._command()

    def set_enabled(self, enabled: bool) -> None:
        if self._enabled == enabled:
            return
        self._enabled = enabled
        self._hovered = False
        self._pressed = False
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self._draw()


class ServerHud(tk.Tk):
    def __init__(
        self,
        *,
        settings_path: Path | None = None,
        data_dir: Path | None = None,
        show_console: bool = True,
    ):
        super().__init__()
        if data_dir is None and settings_path is not None:
            data_dir = Path(settings_path).parent
        self.data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
        self.store = SettingsStore(settings_path or self.data_dir / "settings.json")
        self.settings = self.store.load()
        self.framework = self.settings["framework"]
        self.controllers = {
            name: ServerProcess(self.data_dir / name, show_console=show_console)
            for name in PORTS
        }
        self._server_ready = {name: False for name in PORTS}
        self._active_state = {name: False for name in PORTS}
        self._statuses = {
            name: ("Server stopped.", "stopped") for name in PORTS
        }
        self._closed = False

        theme.apply_theme(self)
        self.title(WINDOW_TITLE)
        self.geometry("560x360")
        self.resizable(False, False)

        self.project_var = tk.StringVar()
        self.python_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.url_var = tk.StringVar()

        self._build()
        self._load_fields()
        self._update_framework_ui()
        self._update_controls()
        self._render_status()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(250, self._poll)
        self.after_idle(self._center)

    def _build(self) -> None:
        outer = tk.Frame(self, bg=theme.BG, padx=18, pady=14)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=theme.BG)
        header.pack(fill="x")
        title_box = tk.Frame(header, bg=theme.BG)
        title_box.pack(side="left")
        tk.Label(
            title_box,
            text=WINDOW_TITLE,
            bg=theme.BG,
            fg=theme.TEXT,
            font=theme.display(20),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="Local Django + FastAPI servers",
            bg=theme.BG,
            fg=theme.MUTED,
            font=(theme.FONT, 9),
            anchor="w",
        ).pack(anchor="w", pady=(1, 0))

        switch = tk.Frame(header, bg=theme.BG)
        switch.pack(side="right", anchor="n")
        self.django_tab = RoundedButton(
            switch,
            "Django",
            lambda: self._select_framework("django"),
            width=78,
            height=30,
            fill=theme.SURFACE_2,
            hover=theme.SURFACE_3,
            selected_fill=theme.PRIMARY,
            selected_text="#FFFFFF",
            font=(theme.FONT, 9, "bold"),
        )
        self.django_tab.pack(side="left", padx=(0, 4))
        self.fastapi_tab = RoundedButton(
            switch,
            "FastAPI",
            lambda: self._select_framework("fastapi"),
            width=78,
            height=30,
            fill=theme.SURFACE_2,
            hover=theme.SURFACE_3,
            selected_fill=theme.PRIMARY,
            selected_text="#FFFFFF",
            font=(theme.FONT, 9, "bold"),
        )
        self.fastapi_tab.pack(side="left")

        status_card = tk.Frame(
            outer,
            bg=theme.SURFACE,
            highlightthickness=1,
            highlightbackground=theme.LINE,
            padx=14,
            pady=9,
        )
        status_card.pack(fill="x", pady=(13, 10))
        self.status_dot = tk.Canvas(
            status_card, width=10, height=10, bg=theme.SURFACE,
            highlightthickness=0, bd=0,
        )
        self.status_dot.pack(side="left", padx=(0, 8))
        self.dot_id = self.status_dot.create_oval(
            1, 1, 9, 9, fill=theme.FAINT, outline=""
        )
        status_text_box = tk.Frame(status_card, bg=theme.SURFACE)
        status_text_box.pack(side="left", fill="x", expand=True)
        self.status_label = tk.Label(
            status_text_box,
            text="Server stopped.",
            bg=theme.SURFACE,
            fg=theme.TEXT,
            font=(theme.FONT, 10, "bold"),
            anchor="w",
        )
        self.status_label.pack(anchor="w")
        self.url_label = tk.Label(
            status_text_box,
            textvariable=self.url_var,
            bg=theme.SURFACE,
            fg=theme.MUTED,
            font=(theme.MONO, 9),
            anchor="w",
        )
        self.url_label.pack(anchor="w", pady=(1, 0))

        fields = tk.Frame(outer, bg=theme.BG)
        fields.pack(fill="x")
        fields.columnconfigure(1, weight=1)
        entry_options = {
            "bg": theme.FIELD,
            "fg": theme.TEXT,
            "disabledbackground": theme.SURFACE,
            "disabledforeground": theme.FAINT,
            "insertbackground": theme.TEXT,
            "relief": "flat",
            "highlightthickness": 1,
            "highlightbackground": theme.LINE,
            "highlightcolor": theme.PRIMARY,
            "font": (theme.FONT, 9),
        }
        label_options = {
            "bg": theme.BG,
            "fg": theme.MUTED,
            "font": (theme.FONT, 9),
            "anchor": "w",
        }

        tk.Label(fields, text="Project folder", **label_options).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self.project_entry = tk.Entry(fields, textvariable=self.project_var, **entry_options)
        self.project_entry.grid(row=0, column=1, sticky="ew", ipady=4)
        self.browse_button = RoundedButton(
            fields,
            "Browse",
            self._choose_project,
            width=72,
            height=28,
            fill=theme.SURFACE_2,
            hover=theme.SURFACE_3,
            font=(theme.FONT, 8, "bold"),
        )
        self.browse_button.grid(row=0, column=2, padx=(8, 0))

        tk.Label(fields, text="Python", **label_options).grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self.python_entry = tk.Entry(fields, textvariable=self.python_var, **entry_options)
        self.python_entry.grid(row=1, column=1, sticky="ew", ipady=4)
        self.python_button = RoundedButton(
            fields,
            "Choose Python",
            self._choose_python,
            width=112,
            height=28,
            fill=theme.SURFACE_2,
            hover=theme.SURFACE_3,
            font=(theme.FONT, 8, "bold"),
        )
        self.python_button.grid(row=1, column=2, padx=(8, 0))

        self.target_label = tk.Label(fields, text="ASGI target", **label_options)
        self.target_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.target_entry = tk.Entry(fields, textvariable=self.target_var, **entry_options)
        self.target_entry.grid(row=2, column=1, columnspan=2, sticky="ew", ipady=4)

        for entry in (self.project_entry, self.python_entry, self.target_entry):
            entry.bind("<FocusOut>", lambda _event: self._save_settings())

        actions = tk.Frame(outer, bg=theme.BG)
        actions.pack(fill="x", pady=(12, 0))
        self.start_button = RoundedButton(
            actions,
            "Start",
            self._start,
            width=96,
            height=36,
            fill=theme.PRIMARY,
            hover=theme.PRIMARY_HOVER,
            pressed=theme.PRIMARY_DARK,
            text_color="#FFFFFF",
        )
        self.start_button.grid(row=0, column=0, padx=(0, 6))
        self.stop_button = RoundedButton(
            actions,
            "Stop",
            self._stop,
            width=82,
            height=36,
            fill=theme.DANGER_SOFT,
            hover="#3a1a27",
            pressed="#321620",
            text_color="#ffaab0",
        )
        self.stop_button.grid(row=0, column=1, padx=(0, 6))
        self.browser_button = RoundedButton(
            actions,
            "Open Browser",
            self._open_browser,
            width=118,
            height=36,
            fill=theme.SURFACE_2,
            hover=theme.SURFACE_3,
        )
        self.browser_button.grid(row=0, column=2, padx=(0, 6))
        self.docs_button = RoundedButton(
            actions,
            "API Docs",
            self._open_docs,
            width=88,
            height=36,
            fill=theme.SURFACE_2,
            hover=theme.SURFACE_3,
        )
        self.docs_button.grid(row=0, column=3)

        secondary = tk.Frame(outer, bg=theme.BG)
        secondary.pack(fill="x", pady=(8, 0))
        self.project_button = RoundedButton(
            secondary,
            "Project Files",
            self._open_project,
            width=112,
            height=30,
            fill=theme.SURFACE_2,
            hover=theme.SURFACE_3,
            font=(theme.FONT, 8, "bold"),
        )
        self.project_button.pack(side="left")
        self.log_button = RoundedButton(
            secondary,
            "View Log",
            self._open_log,
            width=90,
            height=30,
            fill=theme.SURFACE_2,
            hover=theme.SURFACE_3,
            font=(theme.FONT, 8, "bold"),
        )
        self.log_button.pack(side="left", padx=(8, 0))

    def _center(self) -> None:
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _load_fields(self) -> None:
        section = self.settings[self.framework]
        self.project_var.set(section.get("project_dir", ""))
        self.python_var.set(section.get("python", ""))
        self.target_var.set(section.get("asgi_target", DEFAULT_ASGI_TARGET))

    def _capture_fields(self) -> None:
        section = self.settings[self.framework]
        section["project_dir"] = self.project_var.get().strip()
        section["python"] = self.python_var.get().strip()
        if self.framework == "fastapi":
            section["asgi_target"] = self.target_var.get().strip()

    def _save_settings(self) -> None:
        self._capture_fields()
        self.settings["framework"] = self.framework
        try:
            self.store.save(self.settings)
        except OSError as exc:
            self._set_status(f"Could not save settings: {exc}", "error")

    def _select_framework(self, framework: str) -> None:
        if framework == self.framework:
            return
        self._capture_fields()
        self.framework = framework
        self.settings["framework"] = framework
        self._load_fields()
        self._save_settings()
        self._update_framework_ui()
        self._update_controls()
        self._render_status()

    def _update_framework_ui(self) -> None:
        self.django_tab.set_selected(self.framework == "django")
        self.fastapi_tab.set_selected(self.framework == "fastapi")
        if self.framework == "fastapi":
            self.target_label.grid()
            self.target_entry.grid()
            self.docs_button.grid()
        else:
            self.target_label.grid_remove()
            self.target_entry.grid_remove()
            self.docs_button.grid_remove()
        config = self._current_config(validate=False)
        self.url_var.set(config.url)

    def _config_for(self, framework: str, validate: bool = True) -> ServerConfig:
        section = self.settings[framework]
        config = ServerConfig(
            framework=framework,
            project_dir=Path(section.get("project_dir", "").strip()),
            python=Path(section.get("python", "").strip()),
            asgi_target=section.get("asgi_target", ""),
        )
        if validate:
            validate_config(config)
        return config

    def _current_config(self, validate: bool = True) -> ServerConfig:
        return self._config_for(self.framework, validate=validate)

    def _update_controls(self) -> None:
        active = self.controllers[self.framework].running
        self.start_button.set_enabled(not active)
        self.stop_button.set_enabled(active)
        self.django_tab.set_enabled(True)
        self.fastapi_tab.set_enabled(True)
        state = "disabled" if active else "normal"
        for entry in (self.project_entry, self.python_entry, self.target_entry):
            entry.configure(state=state)
        for button in (self.browse_button, self.python_button):
            button.set_enabled(not active)
        self._active_state[self.framework] = active

    def _render_status(self) -> None:
        colors = {
            "stopped": theme.FAINT,
            "starting": theme.WARNING,
            "running": theme.SUCCESS,
            "error": theme.DANGER,
        }
        message, kind = self._statuses[self.framework]
        self.status_label.configure(text=message)
        self.status_dot.itemconfigure(self.dot_id, fill=colors.get(kind, theme.FAINT))

    def _set_status(self, message: str, kind: str, framework: str | None = None) -> None:
        target = framework or self.framework
        self._statuses[target] = (message, kind)
        if target == self.framework:
            self._render_status()

    def _start(self) -> None:
        controller = self.controllers[self.framework]
        if controller.running:
            return
        self._save_settings()
        try:
            config = self._current_config()
        except ValueError as exc:
            self._set_status(str(exc), "error")
            return
        if port_is_open(config.port):
            self._set_status(f"Port {config.port} is already in use.", "error")
            return
        try:
            controller.start(config)
        except (OSError, RuntimeError) as exc:
            self._set_status(f"Could not start server: {exc}", "error")
            return
        self._server_ready[self.framework] = False
        self._set_status(f"Starting {config.label}...", "starting")
        self._update_controls()

    def _stop(self) -> None:
        controller = self.controllers[self.framework]
        if not controller.running:
            self._set_status("Server stopped.", "stopped")
            self._update_controls()
            return
        self._set_status("Stopping...", "starting")
        try:
            controller.stop()
        except (OSError, subprocess.SubprocessError) as exc:
            self._set_status(f"Could not stop server: {exc}", "error")
            return
        self._server_ready[self.framework] = False
        self._set_status("Server stopped.", "stopped")
        self._update_controls()

    def _open_browser(self) -> None:
        webbrowser.open(self._current_config(validate=False).url)

    def _open_docs(self) -> None:
        webbrowser.open(self._current_config(validate=False).docs_url)

    def _open_project(self) -> None:
        path = Path(self.project_var.get().strip())
        if not path.is_dir():
            self._set_status("Project folder not found.", "error")
            return
        try:
            os.startfile(path)
        except OSError as exc:
            self._set_status(f"Could not open folder: {exc}", "error")

    def _open_log(self) -> None:
        controller = self.controllers[self.framework]
        if not controller.log_path.exists():
            self._set_status("No server log yet.", "error")
            return
        try:
            os.startfile(controller.log_path)
        except OSError as exc:
            self._set_status(f"Could not open log: {exc}", "error")

    def _choose_project(self) -> None:
        selected = filedialog.askdirectory(
            title="Choose project folder",
            initialdir=self.project_var.get().strip() or str(_REPO_ROOT),
        )
        if selected:
            self.project_var.set(selected)
            self._save_settings()

    def _choose_python(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose Python interpreter",
            initialdir=str(Path(self.python_var.get()).parent),
            filetypes=[("Python executable", "python.exe"), ("All files", "*.*")],
        )
        if selected:
            self.python_var.set(selected)
            self._save_settings()

    def _poll(self) -> None:
        if self._closed:
            return
        for framework, controller in self.controllers.items():
            config = self._config_for(framework, validate=False)
            process = controller.process
            active = process is not None and process.poll() is None
            if process is not None and not active:
                code = process.poll()
                self._server_ready[framework] = False
                if code == 0:
                    self._set_status("Server stopped.", "stopped", framework)
                else:
                    self._set_status(
                        f"Server exited with code {code}.", "error", framework
                    )
            elif (
                active
                and not self._server_ready[framework]
                and port_is_open(config.port)
            ):
                self._server_ready[framework] = True
                self._set_status(
                    f"{config.label} is running.", "running", framework
                )
            if active != self._active_state[framework]:
                self._active_state[framework] = active
                if framework == self.framework:
                    self._update_controls()
        self.after(300, self._poll)

    def _on_close(self) -> None:
        for controller in self.controllers.values():
            if controller.running:
                try:
                    controller.stop()
                except (OSError, subprocess.SubprocessError):
                    pass
        self._save_settings()
        self._closed = True
        self.destroy()


def main() -> None:
    ServerHud().mainloop()


if __name__ == "__main__":
    main()
