"""Tkinter views: login and the documents workspace.

Views own widgets and user-facing messages only; HTTP lives in
api_client, sessions in session, offline paths in offline, and threading
in tasks. Every widget update here runs on the Tk main thread (delivered
by TaskRunner's pump). Raw exceptions, session tokens, and internal details
are never displayed.
"""
from __future__ import annotations

import re
import time
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import offline
from . import theme
from .api_client import ApiError, describe_api_error
from .session import Session

SORTS = {
    "Uploaded": "created_at",
    "Name": "filename",
    "Size": "file_size_bytes",
    "Date": "created_at",
}
ORDERS = {"Newest first": "desc", "Oldest first": "asc"}
MIME_RE = re.compile(r"^[\w.+-]+/[\w.+-]+$")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def format_size(value: int | float) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_type(mime: str | None) -> str:
    if not mime:
        return "\u2014"
    if mime == "application/pdf":
        return "PDF"
    if "wordprocessingml" in mime:
        return "Word"
    if "spreadsheetml" in mime:
        return "Excel"
    if "presentationml" in mime:
        return "PowerPoint"
    for prefix, label in (("image/", "Image"), ("text/", "Text"),
                          ("audio/", "Audio"), ("video/", "Video")):
        if mime.startswith(prefix):
            return label
    return mime.split("/")[-1][:24].upper()


def format_timestamp(value: str | None) -> str:
    if not value:
        return "\u2014"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return "\u2014"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _label(parent, text: str = "", *, bg: str = theme.BG,
           fg: str = theme.TEXT_2, font=None, **kwargs) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        bg=bg,
        fg=fg,
        font=font or (theme.FONT, 10),
        bd=0,
        **kwargs,
    )


def _center_on_parent(window: tk.Toplevel, parent: tk.Misc, width: int,
                      height: int) -> None:
    parent.update_idletasks()
    x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
    y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------

class LoginView(tk.Frame):
    def __init__(self, parent, client, store, runner, on_authenticated):
        super().__init__(parent, bg=theme.BG)
        self.client = client
        self.store = store
        self.runner = runner
        self.on_authenticated = on_authenticated
        self._mode = "login"
        self._gradient_photo = None
        self._logo_photo = None

        self._build()

    def _build(self):
        self.columnconfigure(0, minsize=430)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_visual()
        self._build_panel()

    def _build_visual(self):
        visual = tk.Frame(self, bg="#03080f")
        visual.grid(row=0, column=0, sticky="nsew")

        try:
            self._gradient_photo = tk.PhotoImage(
                file=str(theme.asset("gradient_auth.png"))
            )
            backdrop = tk.Label(visual, image=self._gradient_photo, bd=0,
                                bg="#03080f")
            backdrop.place(x=0, y=0)
        except tk.TclError:
            self._gradient_photo = None

        brand = tk.Frame(visual, bg="#050d1c")
        brand.place(x=0, y=0, relwidth=1)
        brand_inner = tk.Frame(brand, bg="#050d1c")
        brand_inner.pack(anchor="w", padx=26, pady=16)
        self._logo_photo = theme.load_logo(34)
        logo = tk.Label(brand_inner, image=self._logo_photo, bg="#050d1c", bd=0)
        logo.pack(side="left")
        logo.image = self._logo_photo
        _label(brand_inner, "AI Digital Locker", bg="#050d1c", fg=theme.TEXT,
               font=theme.display(12, "bold")).pack(side="left", padx=(10, 0))

        copy = tk.Frame(visual, bg="#050d1c")
        copy.place(x=0, rely=0.50, relwidth=1, relheight=0.50)
        inner = tk.Frame(copy, bg="#050d1c")
        inner.pack(fill="both", expand=True, padx=26, pady=20)

        _label(inner, "PRIVATE DOCUMENT VAULT", bg="#050d1c", fg=theme.ICE,
               font=(theme.FONT, 8, "bold"), anchor="w").pack(anchor="w")
        _label(inner, "Every document,\nbeautifully organized.",
               bg="#050d1c", fg="#ffffff", font=theme.display(20, "bold"),
               justify="left", anchor="w", wraplength=360).pack(
            anchor="w", pady=(6, 6)
        )
        _label(inner, "Secure storage, instant search, and an AI assistant\n"
                      "for the tedious filing.",
               bg="#050d1c", fg="#a9b8d1", font=(theme.FONT, 9),
               justify="left", anchor="w", wraplength=350).pack(anchor="w")
        for line in (
            "Private, session-protected storage",
            "Fast search, sorting, and filters",
            "AI-assisted filing and summaries",
        ):
            _label(inner, f"\u00b7  {line}", bg="#050d1c", fg="#c6d6ee",
                   font=(theme.FONT, 8), anchor="w", wraplength=340).pack(
                anchor="w", pady=(5, 0)
            )

    def _build_panel(self):
        right = tk.Frame(self, bg=theme.BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        center = tk.Frame(right, bg=theme.BG)
        center.grid(row=0, column=0)

        self._logo_photo = theme.load_logo(46)
        tk.Label(center, image=self._logo_photo, bg=theme.BG, bd=0).pack(
            anchor="w", pady=(0, 18)
        )
        _label(center, "Welcome back", bg=theme.BG, fg=theme.TEXT,
               font=theme.display(24, "bold")).pack(anchor="w")
        _label(center, "Sign in to open your locker.", bg=theme.BG,
               fg=theme.MUTED).pack(anchor="w", pady=(4, 22))

        frame = tk.Frame(center, bg=theme.BG)
        frame.pack(fill="x")

        _label(frame, "EMAIL", bg=theme.BG, fg=theme.TEXT_2,
               font=(theme.FONT, 8, "bold")).pack(anchor="w", pady=(0, 5))
        self.email_var = tk.StringVar()
        self.email_entry = ttk.Entry(frame, textvariable=self.email_var,
                                     width=38, font=(theme.FONT, 10))
        self.email_entry.pack(fill="x", pady=(0, 13))

        _label(frame, "PASSWORD", bg=theme.BG, fg=theme.TEXT_2,
               font=(theme.FONT, 8, "bold")).pack(anchor="w", pady=(0, 5))
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(frame, textvariable=self.password_var,
                                        show="\u2022", width=38,
                                        font=(theme.FONT, 10))
        self.password_entry.pack(fill="x", pady=(0, 18))

        self.submit_btn = ttk.Button(frame, text="Sign in", command=self._submit,
                                     style="Primary.TButton")
        self.submit_btn.pack(fill="x", pady=(0, 8), ipady=3)

        self.switch_btn = ttk.Button(frame, text="Need an account? Register",
                                     command=self._switch_mode,
                                     style="Link.TButton")
        self.switch_btn.pack(fill="x")

        self.status = _label(center, "", bg=theme.BG, fg=theme.DANGER,
                             font=(theme.FONT, 9), wraplength=330,
                             justify="left")
        self.status.pack(anchor="w", pady=(14, 0))

        self.email_entry.focus_set()

    def _switch_mode(self):
        self._mode = "register" if self._mode == "login" else "login"
        self.submit_btn.config(
            text="Create account" if self._mode == "register" else "Sign in"
        )
        self.switch_btn.config(
            text="Have an account? Sign in" if self._mode == "register"
            else "Need an account? Register"
        )
        self._status("")

    def _status(self, text: str, error: bool = False):
        self.status.config(text=text, fg=theme.DANGER if error else theme.MUTED)

    def _submit(self):
        if self.runner.busy:
            return
        email = self.email_var.get().strip().lower()
        password = self.password_var.get()
        if not email or len(password) < 8:
            self._status("Enter an email and a password (at least 8 characters).",
                         error=True)
            return
        mode = self._mode
        self._set_buttons(False)

        def work():
            if mode == "register":
                self.client.register(email, password)
            return self.client.login(email, password)

        def ok(data):
            self.store.save(
                Session(data["access_token"], email,
                        time.time() + data["expires_in"])
            )
            self.on_authenticated(self.store.load())

        def err(exc: Exception):
            if mode == "login" and isinstance(exc, ApiError) and exc.status_code == 401:
                self._status("Incorrect email or password.", error=True)
            elif mode == "register" and isinstance(exc, ApiError) and exc.status_code == 422:
                self._status("Please check your email and password.", error=True)
            else:
                self._status(describe_api_error(exc), error=True)

        self.runner.submit(work, on_success=ok, on_error=err,
                           on_done=lambda: self._set_buttons(True))

    def _set_buttons(self, enabled: bool):
        state = "!disabled" if enabled else "disabled"
        self.submit_btn.state([state])
        self.switch_btn.state([state])


# --------------------------------------------------------------------------
# Workspace
# --------------------------------------------------------------------------

class MainView(tk.Frame):
    def __init__(self, parent, client, store, runner, session: Session,
                 on_logged_out):
        super().__init__(parent, bg=theme.BG)
        self.client = client
        self.store = store
        self.runner = runner
        self.session = session
        self.on_logged_out = on_logged_out
        self._docs: list[dict] = []
        self._logo_photo = None
        self._nav_buttons: dict[str, tk.Button] = {}

        self.columnconfigure(0, minsize=236)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_workspace()
        self.after(100, self.refresh)

    # ---- sidebar ------------------------------------------------------

    def _build_sidebar(self):
        sidebar = tk.Frame(self, bg=theme.SIDEBAR, width=236)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        brand = tk.Frame(sidebar, bg=theme.SIDEBAR)
        brand.pack(fill="x", padx=16, pady=(20, 16))
        self._logo_photo = theme.load_logo(32)
        logo = tk.Label(brand, image=self._logo_photo, bg=theme.SIDEBAR, bd=0)
        logo.pack(side="left")
        logo.image = self._logo_photo
        text = tk.Frame(brand, bg=theme.SIDEBAR)
        text.pack(side="left", padx=(9, 0))
        _label(text, "AI Digital Locker", bg=theme.SIDEBAR, fg=theme.TEXT,
               font=theme.display(11, "bold")).pack(anchor="w")
        _label(text, "Private document vault", bg=theme.SIDEBAR,
               fg=theme.FAINT, font=(theme.FONT, 8)).pack(anchor="w")

        nav = tk.Frame(sidebar, bg=theme.SIDEBAR)
        nav.pack(fill="x", padx=10, pady=(2, 0))
        _label(nav, "WORKSPACE", bg=theme.SIDEBAR, fg=theme.FAINT,
               font=(theme.FONT, 7, "bold")).pack(anchor="w", padx=10, pady=(4, 6))
        self._nav_buttons["documents"] = self._nav_button(
            nav, "Documents", active=True, command=self.refresh
        )
        self._nav_buttons["ai"] = self._nav_button(
            nav, "AI Assistant", command=self._open_ai
        )

        spacer = tk.Frame(sidebar, bg=theme.SIDEBAR)
        spacer.pack(fill="both", expand=True)

        storage = tk.Frame(sidebar, bg=theme.SURFACE, highlightbackground=theme.LINE,
                           highlightthickness=1)
        storage.pack(fill="x", padx=12, pady=(0, 10))
        inner = tk.Frame(storage, bg=theme.SURFACE)
        inner.pack(fill="x", padx=12, pady=11)
        _label(inner, "STORAGE", bg=theme.SURFACE, fg=theme.FAINT,
               font=(theme.FONT, 7, "bold")).pack(anchor="w")
        self.usage_var = tk.StringVar(value="Loading usage\u2026")
        _label(inner, textvariable=self.usage_var, bg=theme.SURFACE,
               fg=theme.TEXT_2, font=(theme.FONT, 9), wraplength=180,
               justify="left").pack(anchor="w", pady=(4, 7))
        self.usage_bar = ttk.Progressbar(inner, maximum=100,
                                         style="TProgressbar", length=180)
        self.usage_bar.pack(fill="x")

        account = tk.Frame(sidebar, bg=theme.SIDEBAR)
        account.pack(fill="x", padx=12, pady=(0, 14))
        avatar = tk.Label(account, text=self.session.email[:1].upper(),
                          bg=theme.PRIMARY, fg="#ffffff",
                          font=(theme.FONT, 10, "bold"), width=3, height=1, bd=0)
        avatar.pack(side="left")
        meta = tk.Frame(account, bg=theme.SIDEBAR)
        meta.pack(side="left", padx=(8, 0), fill="x", expand=True)
        _label(meta, self.session.email, bg=theme.SIDEBAR, fg=theme.TEXT_2,
               font=(theme.FONT, 8), anchor="w", wraplength=140).pack(
            anchor="w", fill="x"
        )
        self.logout_btn = ttk.Button(meta, text="Log out", command=self._logout,
                                     style="Ghost.TButton")
        self.logout_btn.pack(anchor="w")

    def _nav_button(self, parent, text: str, *, active: bool = False,
                    command=None) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            anchor="w",
            padx=12,
            pady=8,
            bd=0,
            relief="flat",
            highlightthickness=0,
            cursor="hand2",
            bg=theme.SURFACE_2 if active else theme.SIDEBAR,
            fg=theme.TEXT if active else theme.MUTED,
            activebackground=theme.SURFACE_2,
            activeforeground=theme.TEXT,
            font=(theme.FONT, 9, "bold" if active else "normal"),
            command=command,
        )
        button.pack(fill="x", pady=1)
        return button

    # ---- workspace ----------------------------------------------------

    def _build_workspace(self):
        work = tk.Frame(self, bg=theme.BG)
        work.grid(row=0, column=1, sticky="nsew")
        work.columnconfigure(0, weight=1)
        work.rowconfigure(2, weight=1)

        header = tk.Frame(work, bg=theme.BG)
        header.grid(row=0, column=0, sticky="ew", padx=26, pady=(22, 14))
        header.columnconfigure(0, weight=1)
        titles = tk.Frame(header, bg=theme.BG)
        titles.grid(row=0, column=0, sticky="w")
        _label(titles, "Documents", bg=theme.BG, fg=theme.TEXT,
               font=theme.display(21, "bold")).pack(anchor="w")
        _label(titles, "Your private document library.", bg=theme.BG,
               fg=theme.MUTED, font=(theme.FONT, 10)).pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(header, bg=theme.BG)
        actions.grid(row=0, column=1, sticky="e")
        self.refresh_btn = ttk.Button(actions, text="Refresh",
                                      command=self.refresh,
                                      style="Secondary.TButton")
        self.refresh_btn.pack(side="left", padx=(0, 8))
        self.upload_btn = ttk.Button(actions, text="Upload document",
                                     command=self._upload,
                                     style="Primary.TButton")
        self.upload_btn.pack(side="left")

        self._build_filters(work)
        self._build_table(work)
        self._build_action_bar(work)
        self._build_status(work)

    def _build_filters(self, work):
        card = tk.Frame(work, bg=theme.SURFACE,
                        highlightbackground=theme.LINE, highlightthickness=1)
        card.grid(row=1, column=0, sticky="ew", padx=26, pady=(0, 12))
        card.columnconfigure(0, weight=1)
        inner = tk.Frame(card, bg=theme.SURFACE)
        inner.grid(row=0, column=0, sticky="ew", padx=14, pady=12)
        inner.columnconfigure(3, weight=1)

        search = tk.Frame(inner, bg=theme.SURFACE)
        search.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 9))
        _label(search, "SEARCH", bg=theme.SURFACE, fg=theme.FAINT,
               font=(theme.FONT, 7, "bold")).pack(anchor="w", pady=(0, 4))
        self.search_var = tk.StringVar()
        ttk.Entry(search, textvariable=self.search_var).pack(fill="x")

        def group(column, label, factory, padx=(0, 10)):
            frame = tk.Frame(inner, bg=theme.SURFACE)
            frame.grid(row=1, column=column, sticky="ew", padx=padx)
            _label(frame, label, bg=theme.SURFACE, fg=theme.FAINT,
                   font=(theme.FONT, 7, "bold")).pack(anchor="w", pady=(0, 4))
            widget = factory(frame)
            widget.pack(fill="x")
            return widget

        self.sort_var = tk.StringVar(value="Uploaded")
        group(0, "SORT",
              lambda p: ttk.Combobox(p, textvariable=self.sort_var,
                                     values=list(SORTS), state="readonly",
                                     width=10))

        self.order_var = tk.StringVar(value="Newest first")
        group(1, "ORDER",
              lambda p: ttk.Combobox(p, textvariable=self.order_var,
                                     values=list(ORDERS), state="readonly",
                                     width=12))

        self.type_var = tk.StringVar()
        group(2, "TYPE (MIME)",
              lambda p: ttk.Entry(p, textvariable=self.type_var, width=14))

        buttons = tk.Frame(inner, bg=theme.SURFACE)
        buttons.grid(row=1, column=4, sticky="se")
        ttk.Button(buttons, text="Apply", command=self.refresh, width=7,
                   style="Secondary.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Clear", command=self._clear_filters, width=7,
                   style="Ghost.TButton").pack(side="left")

    def _build_table(self, work):
        card = tk.Frame(work, bg=theme.SURFACE,
                        highlightbackground=theme.LINE, highlightthickness=1)
        card.grid(row=2, column=0, sticky="nsew", padx=26)
        card.rowconfigure(1, weight=1)
        card.columnconfigure(0, weight=1)

        head = tk.Frame(card, bg=theme.SURFACE)
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        _label(head, "All documents", bg=theme.SURFACE, fg=theme.TEXT,
               font=theme.display(12, "bold")).pack(side="left")
        self.count_var = tk.StringVar(value="")
        _label(head, textvariable=self.count_var, bg=theme.SURFACE,
               fg=theme.FAINT, font=(theme.FONT, 9)).pack(side="left", padx=(9, 0))

        tree_frame = tk.Frame(card, bg=theme.SURFACE)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 12))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        columns = ("name", "type", "size", "uploaded", "offline")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                 selectmode="browse", style="Treeview")
        headings = {
            "name": ("Name", 210),
            "type": ("Type", 100),
            "size": ("Size", 75),
            "uploaded": ("Uploaded", 180),
            "offline": ("Offline", 62),
        }
        for column, (label, width) in headings.items():
            self.tree.heading(column, text=label,
                              command=lambda c=column: self._header_click(c))
            self.tree.column(column, width=width, anchor="w",
                             stretch=column == "name")
        scroll = ttk.Scrollbar(tree_frame, orient="vertical",
                               command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.tag_configure("even", background="#0c1830")
        self.tree.tag_configure("odd", background=theme.SURFACE)

        self.empty_label = tk.Label(
            tree_frame,
            text="No documents yet.\nUpload a file to get started.",
            bg=theme.SURFACE,
            fg=theme.FAINT,
            font=(theme.FONT, 10),
            justify="center",
        )
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

    def _build_action_bar(self, work):
        bar = tk.Frame(work, bg=theme.BG)
        bar.grid(row=3, column=0, sticky="ew", padx=26, pady=(12, 0))
        self.download_btn = ttk.Button(bar, text="Download\u2026",
                                       command=self._download,
                                       style="Secondary.TButton")
        self.offline_btn = ttk.Button(bar, text="Save offline copy",
                                      command=self._save_offline,
                                      style="Secondary.TButton")
        self.rename_btn = ttk.Button(bar, text="Rename\u2026",
                                     command=self._rename,
                                     style="Secondary.TButton")
        self.delete_btn = ttk.Button(bar, text="Delete", command=self._delete,
                                     style="Danger.TButton")
        self.ai_btn = ttk.Button(bar, text="AI Assistant",
                                 command=self._open_ai,
                                 style="Secondary.TButton")
        for button in (self.download_btn, self.offline_btn, self.rename_btn,
                       self.delete_btn):
            button.pack(side="left", padx=(0, 7))
        self.ai_btn.pack(side="right")

    def _build_status(self, work):
        bar = tk.Frame(work, bg=theme.BG)
        bar.grid(row=4, column=0, sticky="ew", padx=26, pady=(10, 16))
        self.progress = ttk.Progressbar(bar, mode="determinate", length=110,
                                        maximum=100, value=0,
                                        style="TProgressbar")
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = _label(bar, textvariable=self.status_var,
                                   bg=theme.BG, fg=theme.MUTED,
                                   font=(theme.FONT, 9))
        self.status_label.pack(side="left")

    # ---- helpers ------------------------------------------------------

    def _set_nav_active(self, active: str):
        for key, button in self._nav_buttons.items():
            is_active = key == active
            try:
                button.config(
                    bg=theme.SURFACE_2 if is_active else theme.SIDEBAR,
                    fg=theme.TEXT if is_active else theme.MUTED,
                    font=(theme.FONT, 9, "bold" if is_active else "normal"),
                )
            except tk.TclError:
                pass

    def _status(self, text: str, error: bool = False):
        self.status_var.set(text)
        self.status_label.config(fg=theme.DANGER if error else theme.MUTED)

    def _action_buttons(self, enabled: bool):
        state = "!disabled" if enabled else "disabled"
        for button in (self.upload_btn, self.download_btn, self.offline_btn,
                       self.rename_btn, self.delete_btn, self.refresh_btn,
                       self.logout_btn, self.ai_btn):
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
        self.order_var.set("Oldest first" if current == "Newest first"
                           else "Newest first")
        self.refresh()

    def _logout(self):
        try:
            self.client.logout(self.session.access_token)
        except ApiError:
            pass
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

        self._begin("Loading\u2026")
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
        for index, doc in enumerate(docs):
            offline_mark = "\u25cf" if offline.has_copy(doc["id"]) else ""
            self.tree.insert(
                "", "end", iid=doc["id"],
                values=(doc["filename"], format_type(doc["file_type"]),
                        format_size(doc["file_size_bytes"]),
                        format_timestamp(doc["created_at"]), offline_mark),
                tags=("even" if index % 2 else "odd",),
            )
        if docs:
            self.empty_label.place_forget()
        else:
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.count_var.set(
            f"{len(docs)} file{'' if len(docs) == 1 else 's'}"
        )
        used = usage["used_bytes"]
        quota = usage["quota_bytes"]
        count = usage["document_count"]
        self.usage_var.set(
            f"{format_size(used)} of {format_size(quota)} used\n"
            f"{count} file{'' if count == 1 else 's'}"
        )
        self.usage_bar["value"] = min(100.0, (used / quota * 100) if quota else 0)
        self._status(f"Loaded {len(docs)} document{'' if len(docs) == 1 else 's'}.")

    def _begin(self, message: str):
        self._action_buttons(False)
        self._status(message)
        self.progress.pack(side="left", padx=(0, 10),
                           before=self.status_label)
        self.progress.config(mode="indeterminate")
        self.progress.start(12)

    def _end(self):
        self.progress.stop()
        self.progress.config(mode="determinate", value=0)
        self.progress.pack_forget()
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

        self._begin("Uploading\u2026")
        self.runner.submit(work, on_success=ok, on_error=self._handle_error,
                           on_done=self._end)

    def _ask_keep_offline(self) -> bool | None:
        """Spec section 11: optional local offline copy at upload time."""
        dialog = tk.Toplevel(self)
        dialog.title("Upload")
        dialog.configure(bg=theme.BG)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)
        _center_on_parent(dialog, self.winfo_toplevel(), 420, 210)

        _label(dialog, "Upload document", bg=theme.BG, fg=theme.TEXT,
               font=theme.display(14, "bold")).pack(anchor="w", padx=22,
                                                    pady=(18, 4))
        _label(dialog, "Keep an offline copy of this file on this computer?",
               bg=theme.BG, fg=theme.MUTED, font=(theme.FONT, 9)).pack(
            anchor="w", padx=22, pady=(0, 10)
        )
        keep_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog, text="Keep offline copy", variable=keep_var).pack(
            anchor="w", padx=22
        )
        result: dict = {"closed": True}

        def accept():
            result["closed"] = False
            result["keep"] = bool(keep_var.get())
            dialog.destroy()

        def cancel():
            dialog.destroy()

        buttons = tk.Frame(dialog, bg=theme.BG)
        buttons.pack(side="bottom", fill="x", padx=22, pady=(14, 18))
        ttk.Button(buttons, text="Cancel", command=cancel,
                   style="Ghost.TButton").pack(side="right")
        ttk.Button(buttons, text="Upload", command=accept,
                   style="Primary.TButton").pack(side="right", padx=(0, 8))

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

        self._begin("Downloading\u2026")
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

        self._begin("Saving offline copy\u2026")
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

        self._begin("Renaming\u2026")
        self.runner.submit(work, on_success=ok, on_error=self._handle_error,
                           on_done=self._end)

    def _ask_filename(self, current: str) -> str | None:
        """Local validation mirrors the API rule (reject, never rewrite)."""
        dialog = tk.Toplevel(self)
        dialog.title("Rename document")
        dialog.configure(bg=theme.BG)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)
        _center_on_parent(dialog, self.winfo_toplevel(), 460, 260)

        _label(dialog, "Rename document", bg=theme.BG, fg=theme.TEXT,
               font=theme.display(14, "bold")).pack(anchor="w", padx=22,
                                                    pady=(18, 4))
        _label(dialog, "Choose a clearer name. The file itself stays the same.",
               bg=theme.BG, fg=theme.MUTED, font=(theme.FONT, 9)).pack(
            anchor="w", padx=22, pady=(0, 10)
        )
        _label(dialog, "NEW FILENAME", bg=theme.BG, fg=theme.TEXT_2,
               font=(theme.FONT, 8, "bold")).pack(anchor="w", padx=22)
        var = tk.StringVar(value=current)
        entry = ttk.Entry(dialog, textvariable=var, width=44)
        entry.pack(fill="x", padx=22, pady=(5, 0))
        entry.select_range(0, "end")
        entry.focus_set()
        error_var = tk.StringVar(value="")
        _label(dialog, textvariable=error_var, bg=theme.BG, fg=theme.DANGER,
               font=(theme.FONT, 8)).pack(anchor="w", padx=22, pady=(5, 0))
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

        buttons = tk.Frame(dialog, bg=theme.BG)
        buttons.pack(side="bottom", fill="x", padx=22, pady=(12, 18))
        ttk.Button(buttons, text="Cancel", command=cancel,
                   style="Ghost.TButton").pack(side="right")
        ttk.Button(buttons, text="Rename", command=accept,
                   style="Primary.TButton").pack(side="right", padx=(0, 8))

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

        self._begin("Deleting\u2026")
        self.runner.submit(work, on_success=ok, on_error=self._handle_error,
                           on_done=self._end)

    # ---- AI assistant --------------------------------------------------

    def _open_ai(self):
        if self.runner.busy:
            return None
        self._set_nav_active("ai")
        dialog = AIDialog(self, self.client, self.store, self.runner, self.session,
                          on_renamed=lambda: self.after_idle(self.refresh))

        def reset_nav(event):
            if event.widget is dialog:
                self._set_nav_active("documents")

        dialog.bind("<Destroy>", reset_nav, add="+")
        return dialog


class AIDialog(tk.Toplevel):
    """Compact AI window. Local AI is a visibly disabled placeholder;
    suggestions are proposals applied via the existing client.rename path
    after a confirmation prompt."""

    def __init__(self, parent, client, store, runner, session: Session,
                 on_renamed=None):
        super().__init__(parent)
        self.title("AI Assistant")
        self.configure(bg=theme.BG)
        self.transient(parent)
        self.minsize(600, 560)
        _center_on_parent(self, parent, 680, 700)
        self.client = client
        self.store = store
        self.runner = runner
        self.session = session
        self.on_renamed = on_renamed
        self._docs: list[dict] = []
        self._suggestion: dict | None = None
        self._selected_doc_id: str | None = None
        self._loading = False

        self._build()

    def _build(self):
        header = tk.Frame(self, bg=theme.BG)
        header.pack(fill="x", padx=20, pady=(16, 8))
        _label(header, "AI Assistant", bg=theme.BG, fg=theme.TEXT,
               font=theme.display(17, "bold")).pack(anchor="w")
        _label(header, "Cloud AI via OpenRouter \u00b7 Local AI unavailable (planned)",
               bg=theme.BG, fg=theme.MUTED, font=(theme.FONT, 9)).pack(
            anchor="w", pady=(2, 0)
        )
        self.status_var = tk.StringVar(value="Loading AI status\u2026")
        _label(header, textvariable=self.status_var, bg=theme.BG,
               fg=theme.WARNING, font=(theme.FONT, 8)).pack(anchor="w",
                                                            pady=(5, 0))

        modes = tk.Frame(self, bg=theme.BG)
        modes.pack(fill="x", padx=20, pady=(4, 0))
        self.mode_var = tk.StringVar(value="ask")
        ttk.Radiobutton(modes, text="Ask a question", variable=self.mode_var,
                        value="ask", command=self._sync_mode).pack(side="left")
        ttk.Radiobutton(modes, text="Summarize", variable=self.mode_var,
                        value="summarize", command=self._sync_mode).pack(
            side="left", padx=(12, 0)
        )
        ttk.Radiobutton(modes, text="Suggest a name", variable=self.mode_var,
                        value="suggest", command=self._sync_mode).pack(
            side="left", padx=(12, 0)
        )
        local_var = tk.StringVar(value="")
        local_radio = ttk.Radiobutton(
            modes, text="Local AI", variable=local_var,
            value="local", state="disabled",
        )
        local_radio.pack(side="right")

        ask_frame = tk.Frame(self, bg=theme.BG)
        ask_frame.pack(fill="x", padx=20, pady=(10, 0))
        _label(ask_frame, "YOUR QUESTION", bg=theme.BG, fg=theme.TEXT_2,
               font=(theme.FONT, 8, "bold")).pack(anchor="w")
        self.question_var = tk.StringVar()
        self.question_entry = ttk.Entry(ask_frame, textvariable=self.question_var)
        self.question_entry.pack(fill="x", pady=(4, 0))

        doc_frame = tk.Frame(self, bg=theme.BG)
        doc_frame.pack(fill="x", padx=20, pady=(8, 0))
        _label(doc_frame, "SELECTED DOCUMENT", bg=theme.BG, fg=theme.TEXT_2,
               font=(theme.FONT, 8, "bold")).pack(anchor="w")
        self.doc_label = _label(
            doc_frame,
            "Select a document in the table behind this window",
            bg=theme.BG, fg=theme.MUTED, font=(theme.FONT, 9),
        )
        self.doc_label.pack(anchor="w", pady=(3, 0))

        self.send_btn = ttk.Button(self, text="Send", command=self._send,
                                   style="Primary.TButton")
        self.send_btn.pack(anchor="e", padx=20, pady=(10, 0))

        result_wrap = tk.Frame(self, bg=theme.SURFACE,
                               highlightbackground=theme.LINE,
                               highlightthickness=1)
        result_wrap.pack(fill="both", expand=True, padx=20, pady=(10, 0))
        result_wrap.rowconfigure(0, weight=1)
        result_wrap.columnconfigure(0, weight=1)
        self.result_text = tk.Text(
            result_wrap,
            height=8,
            wrap="word",
            state="disabled",
            bg=theme.SURFACE,
            fg=theme.TEXT_2,
            insertbackground=theme.TEXT,
            relief="flat",
            bd=0,
            padx=14,
            pady=12,
            font=(theme.FONT, 10),
            selectbackground=theme.PRIMARY,
            selectforeground="#ffffff",
        )
        self.result_text.grid(row=0, column=0, sticky="nsew")
        result_scroll = ttk.Scrollbar(result_wrap, orient="vertical",
                                      command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=result_scroll.set)
        result_scroll.grid(row=0, column=1, sticky="ns")
        self.result_text.config(state="normal")
        self.result_text.insert(
            "1.0",
            "Ask a question, summarize a document, or request a filename "
            "suggestion.\n\nResponses appear here with their sources.",
        )
        self.result_text.config(state="disabled")

        self.sources_label = _label(self, "", bg=theme.BG, fg=theme.FAINT,
                                    font=(theme.FONT, 8), anchor="w",
                                    wraplength=600)
        self.sources_label.pack(fill="x", padx=20, pady=(6, 0))

        self.apply_btn = ttk.Button(self, text="Apply filename suggestion\u2026",
                                    command=self._apply_suggestion,
                                    style="Secondary.TButton")
        self.apply_btn.pack(anchor="e", padx=20, pady=(8, 16))
        self.apply_btn.state(["disabled"])

        self._sync_mode()
        self.after(50, self._load)

    def _sync_mode(self):
        ask = self.mode_var.get() == "ask"
        self.question_entry.state(["!disabled" if ask else "disabled"])

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
                    f'Cloud AI ready \u00b7 model {data.get("model", "unknown")}'
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
