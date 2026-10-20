"""Tkinter views: login/register and the documents dashboard.

Views own widgets and user-facing messages only; HTTP lives in
api_client, sessions in session, offline paths in offline, and threading
in tasks. Every widget update here runs on the Tk main thread (delivered
by TaskRunner's pump). Raw exceptions, JWTs, and internal details are
never displayed.
"""
from __future__ import annotations

import re
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import offline
from .api_client import ApiError, describe_api_error
from .session import Session

MIME_RE = re.compile(r"^[\w.+-]+/[\w.+-]+$")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # UI pre-check only; backend is authoritative

SORTS = {"Uploaded": "created_at", "Name": "filename", "Size": "file_size_bytes"}
ORDERS = {"Newest first": "desc", "Oldest first": "asc"}


def format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def format_timestamp(iso_value: str) -> str:
    return iso_value.replace("T", " ")[:16] + " UTC"


# --------------------------------------------------------------------------
# Login / register
# --------------------------------------------------------------------------

class LoginView(tk.Frame):
    def __init__(self, parent, client, store, runner, on_authenticated):
        super().__init__(parent, padx=40, pady=40)
        self.client = client
        self.store = store
        self.runner = runner
        self.on_authenticated = on_authenticated
        self._mode = "login"

        ttk.Label(self, text="AI Digital Locker", font=("", 14, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 16)
        )
        ttk.Label(self, text="Email").grid(row=1, column=0, sticky="w")
        self.email_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.email_var, width=36).grid(
            row=1, column=1, sticky="ew", pady=4
        )
        ttk.Label(self, text="Password").grid(row=2, column=0, sticky="w")
        self.password_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.password_var, show="*", width=36).grid(
            row=2, column=1, sticky="ew", pady=4
        )
        self.submit_btn = ttk.Button(self, text="Sign in", command=self._submit)
        self.submit_btn.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 4))
        self.switch_btn = ttk.Button(self, text="Need an account? Register",
                                     command=self._switch_mode)
        self.switch_btn.grid(row=4, column=0, columnspan=2, sticky="ew")
        self.status = ttk.Label(self, text="", foreground="#a4262c")
        self.status.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.columnconfigure(1, weight=1)

    def _switch_mode(self):
        self._mode = "register" if self._mode == "login" else "login"
        self.submit_btn.config(text="Create account" if self._mode == "register" else "Sign in")
        self.switch_btn.config(
            text="Have an account? Sign in" if self._mode == "register"
            else "Need an account? Register"
        )
        self._status("")

    def _status(self, text: str):
        self.status.config(text=text)

    def _submit(self):
        if self.runner.busy:
            return
        email = self.email_var.get().strip().lower()
        password = self.password_var.get()
        if not email or len(password) < 8:
            self._status("Enter an email and a password (at least 8 characters).")
            return
        mode = self._mode
        self._set_buttons(False)

        def work():
            if mode == "register":
                self.client.register(email, password)
            return self.client.login(email, password)

        def ok(data):
            self.store.save(
                Session(data["access_token"], email, time.time() + data["expires_in"])
            )
            self.on_authenticated(self.store.load())

        def err(exc: Exception):
            if mode == "login" and isinstance(exc, ApiError) and exc.status_code == 401:
                self._status("Incorrect email or password.")
            elif mode == "register" and isinstance(exc, ApiError) and exc.status_code == 422:
                self._status("Please check your email and password.")
            else:
                self._status(describe_api_error(exc))

        self.runner.submit(work, on_success=ok, on_error=err,
                           on_done=lambda: self._set_buttons(True))

    def _set_buttons(self, enabled: bool):
        state = "!disabled" if enabled else "disabled"
        self.submit_btn.state([state])
        self.switch_btn.state([state])


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

class MainView(tk.Frame):
    def __init__(self, parent, client, store, runner, session: Session,
                 on_logged_out):
        super().__init__(parent)
        self.client = client
        self.store = store
        self.runner = runner
        self.session = session
        self.on_logged_out = on_logged_out
        self._docs: list[dict] = []

        self._build_toolbar(parent)
        self._build_usage()
        self._build_filters()
        self._build_table()
        self._build_actions()
        self._build_status()
        self.after(100, self.refresh)

    # ---- layout -------------------------------------------------------

    def _build_toolbar(self, parent):
        bar = ttk.Frame(self, padding=(8, 8, 8, 0))
        bar.pack(fill="x")
        ttk.Label(bar, text=self.session.email).pack(side="left")
        self.refresh_btn = ttk.Button(bar, text="Refresh", command=self.refresh)
        self.refresh_btn.pack(side="right", padx=(6, 0))
        self.logout_btn = ttk.Button(bar, text="Logout", command=self._logout)
        self.logout_btn.pack(side="right")

    def _build_usage(self):
        frame = ttk.Frame(self, padding=(8, 8, 8, 0))
        frame.pack(fill="x")
        self.usage_var = tk.StringVar(value="Loading usage…")
        ttk.Label(frame, textvariable=self.usage_var).pack(anchor="w")
        self.usage_bar = ttk.Progressbar(frame, maximum=100)
        self.usage_bar.pack(fill="x", pady=(2, 0))

    def _build_filters(self):
        frame = ttk.Frame(self, padding=(8, 8, 8, 0))
        frame.pack(fill="x")
        ttk.Label(frame, text="Search").pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.search_var, width=20).pack(side="left", padx=(2, 8))
        ttk.Label(frame, text="Sort").pack(side="left")
        self.sort_var = tk.StringVar(value="Uploaded")
        ttk.Combobox(frame, textvariable=self.sort_var, values=list(SORTS),
                     state="readonly", width=10).pack(side="left", padx=(2, 8))
        ttk.Label(frame, text="Order").pack(side="left")
        self.order_var = tk.StringVar(value="Newest first")
        ttk.Combobox(frame, textvariable=self.order_var, values=list(ORDERS),
                     state="readonly", width=12).pack(side="left", padx=(2, 8))
        ttk.Label(frame, text="Type (MIME)").pack(side="left")
        self.type_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.type_var, width=18).pack(side="left", padx=(2, 8))
        ttk.Button(frame, text="Apply", command=self.refresh).pack(side="left")
        ttk.Button(frame, text="Clear", command=self._clear_filters).pack(side="left", padx=(4, 0))

    def _build_table(self):
        frame = ttk.Frame(self, padding=8)
        frame.pack(fill="both", expand=True)
        columns = ("name", "type", "size", "uploaded", "offline")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        headings = {"name": ("Name", 240), "type": ("Type", 130), "size": ("Size", 80),
                    "uploaded": ("Uploaded", 140), "offline": ("Offline", 60)}
        for column, (label, width) in headings.items():
            self.tree.heading(column, text=label,
                              command=lambda c=column: self._header_click(c))
            self.tree.column(column, width=width, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _build_actions(self):
        frame = ttk.Frame(self, padding=(8, 0, 8, 8))
        frame.pack(fill="x")
        self.upload_btn = ttk.Button(frame, text="Upload…", command=self._upload)
        self.download_btn = ttk.Button(frame, text="Download…", command=self._download)
        self.offline_btn = ttk.Button(frame, text="Save offline copy",
                                      command=self._save_offline)
        self.rename_btn = ttk.Button(frame, text="Rename…", command=self._rename)
        self.delete_btn = ttk.Button(frame, text="Delete", command=self._delete)
        self.ai_btn = ttk.Button(frame, text="AI Assistant", command=self._open_ai)
        for button in (self.upload_btn, self.download_btn, self.offline_btn,
                       self.rename_btn, self.delete_btn, self.ai_btn):
            button.pack(side="left", padx=(0, 6))

    def _build_status(self):
        frame = ttk.Frame(self, padding=(8, 0, 8, 8))
        frame.pack(fill="x", side="bottom")
        self.progress = ttk.Progressbar(frame, mode="indeterminate", length=120)
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(frame, textvariable=self.status_var)
        self.status_label.pack(side="left")

    # ---- helpers ------------------------------------------------------

    def _status(self, text: str, error: bool = False):
        self.status_var.set(text)
        self.status_label.config(foreground="#a4262c" if error else "")

    def _action_buttons(self, enabled: bool):
        state = "!disabled" if enabled else "disabled"
        for button in (self.upload_btn, self.download_btn, self.offline_btn,
                       self.rename_btn, self.delete_btn, self.refresh_btn,
                       self.logout_btn):
            button.state([state])

    def _selected_doc(self) -> dict | None:
        selection = self.tree.selection()
        if not selection:
            return None
        doc_id = selection[0]
        for doc in self._docs:
            if doc["id"] == doc_id:
                return doc
        return None

    def _clear_filters(self):
        self.search_var.set("")
        self.type_var.set("")
        self.sort_var.set("Uploaded")
        self.order_var.set("Newest first")
        self.refresh()

    def _header_click(self, column: str):
        if column == "name":
            key = "Name"
        elif column == "size":
            key = "Size"
        else:
            key = "Uploaded"
        self.sort_var.set(key)
        current = self.order_var.get()
        self.order_var.set("Oldest first" if current == "Newest first" else "Newest first")
        self.refresh()

    def _logout(self):
        self.on_logged_out()

    def _handle_error(self, exc: Exception):
        if isinstance(exc, ApiError) and exc.status_code == 401:
            self.on_logged_out("Your session has expired. Please log in again.")
            return
        self._status(describe_api_error(exc), error=True)

    # ---- data loading -------------------------------------------------

    def refresh(self):
        if self.runner.busy:
            return
        file_type = self.type_var.get().strip()
        if file_type and not MIME_RE.match(file_type):
            self._status("Type filter must look like: application/pdf", error=True)
            return
        token = self.session.access_token
        search = self.search_var.get().strip()
        sort = SORTS.get(self.sort_var.get(), "created_at")
        order = ORDERS.get(self.order_var.get(), "desc")

        def work():
            docs = self.client.list_documents(
                token, search=search, sort=sort, order=order, file_type=file_type
            )
            usage = self.client.usage(token)
            return docs, usage

        self._begin("Loading…")
        self.runner.submit(
            work,
            on_success=self._on_loaded,
            on_error=self._handle_error,
            on_done=self._end,
        )

    def _on_loaded(self, result):
        docs, usage = result
        self._docs = docs
        self.tree.delete(*self.tree.get_children())
        for doc in docs:
            offline_mark = "●" if offline.has_copy(doc["id"]) else ""
            self.tree.insert(
                "", "end", iid=doc["id"],
                values=(doc["filename"], doc["file_type"],
                        format_size(doc["file_size_bytes"]),
                        format_timestamp(doc["created_at"]), offline_mark),
            )
        used, quota, count = usage["used_bytes"], usage["quota_bytes"], usage["document_count"]
        self.usage_var.set(
            f"{format_size(used)} of {format_size(quota)} used · {count} file"
            f"{'' if count == 1 else 's'}"
        )
        self.usage_bar["value"] = min(100.0, (used / quota * 100) if quota else 0)
        self._status(f"Loaded {len(docs)} document{'' if len(docs) == 1 else 's'}.")

    def _begin(self, message: str):
        self._action_buttons(False)
        self._status(message)
        self.progress.start(12)

    def _end(self):
        self.progress.stop()
        self._action_buttons(True)

    # ---- operations ---------------------------------------------------

    def _upload(self):
        if self.runner.busy:
            return
        chosen = filedialog.askopenfilename(title="Choose a file to upload")
        if not chosen:
            return
        path = Path(chosen)
        if path.stat().st_size > MAX_UPLOAD_BYTES:
            self._status("That file is larger than the 50 MiB limit.", error=True)
            return
        keep = self._ask_keep_offline()
        if keep is None:
            return
        token = self.session.access_token

        def work():
            doc = self.client.upload(token, path)
            if keep:
                self.client.download_to_file(
                    token, doc["id"], offline.copy_path(doc["id"], doc["filename"])
                )
            return doc

        def ok(doc):
            suffix = " (offline copy kept)" if keep else ""
            self._status(f'Uploaded "{doc["filename"]}"{suffix}.')
            self.after_idle(self.refresh)

        self._begin("Uploading…")
        self.runner.submit(work, on_success=ok, on_error=self._handle_error,
                           on_done=self._end)

    def _ask_keep_offline(self) -> bool | None:
        """Spec section 11: optional local offline copy at upload time."""
        dialog = tk.Toplevel(self)
        dialog.title("Upload")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        keep_var = tk.BooleanVar(value=False)
        ttk.Label(dialog, text="Keep an offline copy of this file on this computer?").pack(
            padx=20, pady=(16, 6)
        )
        ttk.Checkbutton(dialog, text="Keep Offline Copy", variable=keep_var).pack(
            padx=20, anchor="w"
        )
        result: dict = {"closed": True}

        def accept():
            result["closed"] = False
            result["keep"] = bool(keep_var.get())
            dialog.destroy()

        def cancel():
            dialog.destroy()

        ttk.Button(dialog, text="Upload", command=accept).pack(
            side="left", fill="x", expand=True, padx=(20, 4), pady=(8, 16)
        )
        ttk.Button(dialog, text="Cancel", command=cancel).pack(
            side="left", fill="x", expand=True, padx=(4, 20), pady=(8, 16)
        )
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.wait_window(dialog)
        if result["closed"]:
            return None
        return result["keep"]

    def _download(self):
        if self.runner.busy:
            return
        doc = self._selected_doc()
        if doc is None:
            self._status("Select a document first.", error=True)
            return
        dest = filedialog.asksaveasfilename(title="Save document",
                                            initialfile=doc["filename"])
        if not dest:
            return
        token = self.session.access_token

        def work():
            self.client.download_to_file(token, doc["id"], Path(dest))

        def ok(_):
            self._status(f'Saved "{doc["filename"]}".')

        self._begin("Downloading…")
        self.runner.submit(work, on_success=ok, on_error=self._handle_error,
                           on_done=self._end)

    def _save_offline(self):
        if self.runner.busy:
            return
        doc = self._selected_doc()
        if doc is None:
            self._status("Select a document first.", error=True)
            return
        token = self.session.access_token

        def work():
            self.client.download_to_file(
                token, doc["id"], offline.copy_path(doc["id"], doc["filename"])
            )

        def ok(_):
            self._status(f'Offline copy saved to desktop/offline/{doc["id"]}/.')
            self.after_idle(self.refresh)

        self._begin("Saving offline copy…")
        self.runner.submit(work, on_success=ok, on_error=self._handle_error,
                           on_done=self._end)

    def _rename(self):
        if self.runner.busy:
            return
        doc = self._selected_doc()
        if doc is None:
            self._status("Select a document first.", error=True)
            return
        new_name = self._ask_filename(doc["filename"])
        if new_name is None or new_name == doc["filename"]:
            return
        token = self.session.access_token

        def work():
            self.client.rename(token, doc["id"], new_name)

        def ok(_):
            self._status("Document renamed.")
            self.after_idle(self.refresh)

        self._begin("Renaming…")
        self.runner.submit(work, on_success=ok, on_error=self._handle_error,
                           on_done=self._end)

    def _ask_filename(self, current: str) -> str | None:
        """Local validation mirrors the API rule (reject, never rewrite)."""
        dialog = tk.Toplevel(self)
        dialog.title("Rename document")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ttk.Label(dialog, text="New filename").pack(padx=20, pady=(16, 2))
        var = tk.StringVar(value=current)
        entry = ttk.Entry(dialog, textvariable=var, width=40)
        entry.pack(padx=20, pady=2)
        entry.select_range(0, "end")
        error_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=error_var, foreground="#a4262c").pack(
            padx=20, anchor="w"
        )
        result: dict = {"closed": True}

        def accept():
            name = var.get()
            if not 1 <= len(name) <= 255:
                error_var.set("Name must be 1-255 characters.")
                return
            if "/" in name or "\\" in name:
                error_var.set("Name cannot contain path separators.")
                return
            if any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
                error_var.set("Name cannot contain control characters.")
                return
            if name.strip(". ") == "":
                error_var.set("Enter a valid file name.")
                return
            result["closed"] = False
            result["name"] = name
            dialog.destroy()

        def cancel():
            dialog.destroy()

        ttk.Button(dialog, text="Rename", command=accept).pack(
            side="left", fill="x", expand=True, padx=(20, 4), pady=(8, 16)
        )
        ttk.Button(dialog, text="Cancel", command=cancel).pack(
            side="left", fill="x", expand=True, padx=(4, 20), pady=(8, 16)
        )
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.wait_window(dialog)
        if result["closed"]:
            return None
        return result["name"]

    def _delete(self):
        if self.runner.busy:
            return
        doc = self._selected_doc()
        if doc is None:
            self._status("Select a document first.", error=True)
            return
        if not messagebox.askyesno(
            "Delete document",
            f'Delete "{doc["filename"]}"? This cannot be undone.',
            parent=self,
        ):
            return
        token = self.session.access_token

        def work():
            self.client.delete(token, doc["id"])

        def ok(_):
            self._status(f'Deleted "{doc["filename"]}". Offline copies, if any, are kept.')
            self.after_idle(self.refresh)

        self._begin("Deleting…")
        self.runner.submit(work, on_success=ok, on_error=self._handle_error,
                           on_done=self._end)

    # ---- AI assistant --------------------------------------------------

    def _open_ai(self):
        if self.runner.busy:
            return None
        return AIDialog(self, self.client, self.store, self.runner, self.session,
                        on_renamed=lambda: self.after_idle(self.refresh))


class AIDialog(tk.Toplevel):
    """Compact AI chat window (spec 13). Local AI is a visibly disabled
    placeholder; suggestions are proposals applied via the existing
    client.rename path after a confirmation prompt."""

    def __init__(self, parent, client, store, runner, session: Session,
                 on_renamed=None):
        super().__init__(parent)
        self.title("AI Assistant")
        self.geometry("560x520")
        self.transient(parent)
        self.client = client
        self.store = store
        self.runner = runner
        self.session = session
        self.on_renamed = on_renamed
        self._docs: list[dict] = []

        self._build()

    def _build(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Cloud AI (OpenRouter)").pack(anchor="w")
        local_var = tk.StringVar(value="Local AI - unavailable (planned)")
        local_radio = ttk.Radiobutton(
            top, text="Local AI", variable=local_var,
            value="Local AI - unavailable (planned)", state="disabled",
        )
        local_radio.pack(anchor="w")
        self.status_var = tk.StringVar(value="Loading AI status…")
        ttk.Label(top, textvariable=self.status_var, foreground="#a4262c").pack(
            anchor="w"
        )

        mode_frame = ttk.Frame(self, padding=(8, 0, 8, 0))
        mode_frame.pack(fill="x")
        self.mode_var = tk.StringVar(value="ask")
        ttk.Radiobutton(mode_frame, text="Ask a question", variable=self.mode_var,
                        value="ask", command=self._sync_mode).pack(side="left")
        ttk.Radiobutton(mode_frame, text="Summarize selected document",
                        variable=self.mode_var, value="summarize",
                        command=self._sync_mode).pack(side="left", padx=(8, 0))
        ttk.Radiobutton(mode_frame, text="Suggest filename for selected document",
                        variable=self.mode_var, value="suggest",
                        command=self._sync_mode).pack(side="left", padx=(8, 0))

        ask_frame = ttk.Frame(self, padding=(8, 4, 8, 0))
        ask_frame.pack(fill="x")
        ttk.Label(ask_frame, text="Question").pack(anchor="w")
        self.question_var = tk.StringVar()
        self.question_entry = ttk.Entry(ask_frame, textvariable=self.question_var)
        self.question_entry.pack(fill="x")

        doc_frame = ttk.Frame(self, padding=(8, 4, 8, 0))
        doc_frame.pack(fill="x")
        ttk.Label(doc_frame, text="Selected document").pack(anchor="w")
        self.doc_label = ttk.Label(doc_frame, text="(select a document in the table behind this window)")
        self.doc_label.pack(anchor="w")

        self.send_btn = ttk.Button(self, text="Send", command=self._send)
        self.send_btn.pack(pady=(6, 0))

        self.result_text = tk.Text(self, height=12, wrap="word", state="disabled")
        self.result_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.sources_label = ttk.Label(self, text="", padding=(8, 0, 8, 4))
        self.sources_label.pack(fill="x")
        self.apply_btn = ttk.Button(self, text="Apply filename suggestion…",
                                    command=self._apply_suggestion)
        self.apply_btn.pack(pady=(0, 8))
        self._suggestion: dict | None = None
        self._selected_doc_id: str | None = None
        self.apply_btn.state(["disabled"])
        self._sync_mode()
        self.after(50, self._load)

    def _sync_mode(self):
        ask = self.mode_var.get() == "ask"
        state = "!disabled" if ask else "disabled"
        self.question_entry.state([state])

    def _selected_doc(self):
        parent = self.master
        return parent._selected_doc() if hasattr(parent, "_selected_doc") else None

    def _load(self):
        doc = self._selected_doc()
        if doc:
            self._selected_doc_id = doc["id"]
            self.doc_label.config(text=doc["filename"])
        token = self.session.access_token

        def work():
            return self.client.ai_status(token)

        def ok(data):
            if data.get("configured"):
                self.status_var.set(
                    f'Cloud AI ready - model {data.get("model", "unknown")}'
                )
            else:
                self.status_var.set("Cloud AI is not configured on this server yet.")

        def err(exc):
            self.status_var.set(describe_api_error(exc))

        self.runner.submit(work, on_success=ok, on_error=err)

    def _show_result(self, text: str, sources: list[dict]):
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
        self.result_text.config(state="disabled")
        names = ", ".join(s["filename"] for s in sources) if sources else "none"
        self.sources_label.config(text=f"Sources: {names}")

    def _send(self):
        if self.runner.busy:
            return
        mode = self.mode_var.get()
        token = self.session.access_token
        doc = self._selected_doc()
        question = self.question_var.get().strip()
        if mode == "ask" and not question:
            self._show_result("Type a question first.", [])
            return
        if mode in ("summarize", "suggest") and doc is None:
            self._show_result("Select a document first.", [])
            return
        self._suggestion = None
        self.apply_btn.state(["disabled"])

        def work():
            if mode == "ask":
                return self.client.ai_ask(token, question)
            if mode == "summarize":
                return self.client.ai_summarize(token, doc["id"])
            return self.client.ai_suggest_filename(token, doc["id"])

        def ok(data):
            if mode == "ask":
                self._show_result(data.get("answer", ""), data.get("sources", []))
            elif mode == "summarize":
                self._show_result(data.get("summary", ""), data.get("sources", []))
            else:
                self._suggestion = {"doc_id": doc["id"], "data": data}
                self.apply_btn.state(["!disabled"])
                self._show_result(
                    f'Suggested: {data.get("suggested_filename", "")}\n'
                    f'Current:  {data.get("current_filename", "")}\n\n'
                    f'{data.get("reason", "")}',
                    [],
                )

        def err(exc):
            self._show_result(describe_api_error(exc), [])

        self.runner.submit(work, on_success=ok, on_error=err)

    def _apply_suggestion(self):
        """Proposal only: confirm, then reuse the existing validated rename."""
        if not self._suggestion:
            return
        doc_id = self._suggestion["doc_id"]
        new_name = self._suggestion["data"].get("suggested_filename", "")
        if not messagebox.askyesno(
            "Apply filename suggestion",
            f'Rename this document to "{new_name}"?',
            parent=self,
        ):
            return
        token = self.session.access_token

        def work():
            return self.client.rename(token, doc_id, new_name)

        def ok(_):
            self._show_result(f'Renamed to "{new_name}".', [])
            self._suggestion = None
            self.apply_btn.state(["disabled"])
            if self.on_renamed:
                self.on_renamed()

        def err(exc):
            self._show_result(describe_api_error(exc), [])

        self.runner.submit(work, on_success=ok, on_error=err)
