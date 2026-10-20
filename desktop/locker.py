"""AI Digital Locker - Windows Tkinter desktop client.

Launch (from desktop/):  py locker.py

Talks only to the FastAPI backend (FASTAPI_BASE_URL env var, repo-root
.env, or http://127.0.0.1:8000). No Supabase or OpenRouter credentials
ever reach this application.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app import config, offline
from app.api_client import ApiClient
from app.session import SessionStore
from app.tasks import TaskRunner
from app.views import LoginView, MainView


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("AI Digital Locker")
        root.minsize(760, 480)
        self.client = ApiClient(config.base_url())
        self.store = SessionStore()
        self.runner = TaskRunner(root.after)
        self.container = ttk.Frame(root)
        self.container.pack(fill="both", expand=True)
        self._view = None
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        session = self.store.load()
        if session is not None:
            self.show_main(session)
        else:
            self.show_login()

    def _swap(self, view_factory):
        if self._view is not None:
            self._view.destroy()
            self._view = None
        self._view = view_factory(self.container)
        self._view.pack(fill="both", expand=True)

    def show_login(self, message: str | None = None):
        def build(parent):
            view = LoginView(parent, self.client, self.store, self.runner,
                             on_authenticated=self.show_main)
            if message:
                view._status(message)
            return view

        self._swap(build)

    def show_main(self, session):
        if session is None:  # defensive: expired/cleared between save and load
            self.show_login()
            return
        self._swap(
            lambda parent: MainView(
                parent, self.client, self.store, self.runner, session,
                on_logged_out=self.on_logout,
            )
        )

    def on_logout(self, message: str | None = None):
        """Clears the persisted session. Local offline copies are kept."""
        self.store.clear()
        self.show_login(message or "You have been logged out.")

    def on_close(self):
        self.runner.shutdown()
        self.client.close()
        self.root.destroy()


def main():
    offline.offline_root().mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
