# desktop/app/theme.py: Visual theme, fonts, and shared Tkinter styling.
"""Shared visual tokens and ttk styling for the desktop client."""
from __future__ import annotations

import base64
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from app.resource import asset_path, find_asset

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS = REPO_ROOT / "assets"

                                        
BG = "#050a16"
BG_ALT = "#070f1f"
SIDEBAR = "#070e1d"
SURFACE = "#0a1426"
SURFACE_2 = "#0d1a31"
SURFACE_3 = "#122140"
FIELD = "#060e1e"
LINE = "#1b2a45"
LINE_SOFT = "#14203a"
TEXT = "#eaf0fb"
TEXT_2 = "#c3cfe4"
MUTED = "#8797b1"
FAINT = "#63718c"
PRIMARY = "#2f6bff"
PRIMARY_HOVER = "#437cff"
PRIMARY_DARK = "#1c4fd0"
ICE = "#8fd3ff"
SUCCESS = "#3ddc97"
WARNING = "#f5b95f"
DANGER = "#f2707a"
DANGER_SOFT = "#2a1420"

FONT = "Segoe UI"
MONO = "Cascadia Code"

_DISPLAY_FAMILY = FONT


def display(size: int, weight: str = "bold"):
    """Heading font tuple that uses Segoe UI Variable when available."""
    return (_DISPLAY_FAMILY, size, weight)


def asset(name: str) -> Path:
    """Resolve an asset name for source or packaged PyInstaller runs."""
    return asset_path(name)


def apply_theme(root: tk.Tk) -> None:
    global _DISPLAY_FAMILY

    families = set(tkfont.families(root))
    for candidate in ("Segoe UI Variable Display", "Segoe UI Semibold"):
        if candidate in families:
            _DISPLAY_FAMILY = candidate
            break

    root.configure(bg=BG)
    root.option_add("*TCombobox*Listbox.background", SURFACE_2)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", PRIMARY)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        ".",
        background=BG,
        foreground=TEXT,
        fieldbackground=FIELD,
        bordercolor=LINE,
        lightcolor=LINE,
        darkcolor=LINE,
        focuscolor=PRIMARY,
        font=(FONT, 10),
    )
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("TEntry", padding=6)
    style.configure("TButton", font=(FONT, 10))

    style.configure(
        "Primary.TButton",
        background=PRIMARY,
        foreground="#ffffff",
        bordercolor=PRIMARY,
        lightcolor=PRIMARY,
        darkcolor=PRIMARY_DARK,
        focuscolor=PRIMARY,
        padding=(14, 8),
        font=(FONT, 10, "bold"),
    )
    style.map(
        "Primary.TButton",
        background=[("pressed", PRIMARY_DARK), ("active", PRIMARY_HOVER), ("disabled", SURFACE_3)],
        foreground=[("disabled", FAINT)],
        bordercolor=[("active", PRIMARY_HOVER)],
        lightcolor=[("active", PRIMARY_HOVER)],
    )

    style.configure(
        "Secondary.TButton",
        background=SURFACE_2,
        foreground=TEXT_2,
        bordercolor=LINE,
        lightcolor=LINE,
        darkcolor=LINE,
        padding=(12, 7),
    )
    style.map(
        "Secondary.TButton",
        background=[("pressed", SURFACE), ("active", SURFACE_3), ("disabled", SURFACE)],
        foreground=[("active", TEXT), ("disabled", FAINT)],
        bordercolor=[("active", "#2a3f66")],
        lightcolor=[("active", "#2a3f66")],
    )

    style.configure(
        "Ghost.TButton",
        background=SIDEBAR,
        foreground=MUTED,
        bordercolor=SIDEBAR,
        lightcolor=SIDEBAR,
        darkcolor=SIDEBAR,
        padding=(10, 6),
    )
    style.map(
        "Ghost.TButton",
        background=[("active", SURFACE_2), ("pressed", SURFACE_2)],
        foreground=[("active", TEXT)],
    )

    style.configure(
        "Danger.TButton",
        background=DANGER_SOFT,
        foreground="#ffaab0",
        bordercolor="#542430",
        lightcolor="#542430",
        darkcolor="#3a1a23",
        padding=(12, 7),
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#3a1a27"), ("pressed", "#321620"), ("disabled", SURFACE)],
        foreground=[("active", "#ffc4c8"), ("disabled", FAINT)],
    )

    style.configure(
        "Link.TButton",
        background=BG,
        foreground=ICE,
        bordercolor=BG,
        lightcolor=BG,
        darkcolor=BG,
        padding=(6, 4),
    )
    style.map(
        "Link.TButton",
        background=[("active", BG)],
        foreground=[("active", "#c2e6ff"), ("disabled", FAINT)],
    )

    style.configure(
        "TEntry",
        fieldbackground=FIELD,
        foreground=TEXT,
        insertcolor=TEXT,
        bordercolor=LINE,
        lightcolor=LINE,
        darkcolor=LINE,
        padding=7,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", PRIMARY)],
        lightcolor=[("focus", PRIMARY)],
        darkcolor=[("focus", PRIMARY)],
        fieldbackground=[("disabled", SURFACE)],
        foreground=[("disabled", FAINT)],
    )

    style.configure(
        "TCombobox",
        fieldbackground=FIELD,
        background=SURFACE_2,
        foreground=TEXT,
        arrowcolor=MUTED,
        bordercolor=LINE,
        lightcolor=LINE,
        darkcolor=LINE,
        padding=5,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", FIELD), ("disabled", SURFACE)],
        foreground=[("readonly", TEXT), ("disabled", FAINT)],
        bordercolor=[("focus", PRIMARY)],
        lightcolor=[("focus", PRIMARY)],
        darkcolor=[("focus", PRIMARY)],
    )

    style.configure(
        "Treeview",
        background=SURFACE,
        fieldbackground=SURFACE,
        foreground=TEXT_2,
        bordercolor=SURFACE,
        lightcolor=SURFACE,
        darkcolor=SURFACE,
        rowheight=34,
        borderwidth=0,
        font=(FONT, 10),
    )
    style.configure(
        "Treeview.Heading",
        background=BG_ALT,
        foreground=FAINT,
        bordercolor=BG_ALT,
        lightcolor=BG_ALT,
        darkcolor=BG_ALT,
        relief="flat",
        padding=(8, 7),
        font=(FONT, 8, "bold"),
    )
    style.map(
        "Treeview",
        background=[("selected", "#16305e")],
        foreground=[("selected", "#ffffff")],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", SURFACE_2)],
        foreground=[("active", TEXT_2)],
    )

    style.configure(
        "Vertical.TScrollbar",
        background=SURFACE_2,
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=MUTED,
        gripcount=0,
        arrowsize=11,
    )
    style.map("Vertical.TScrollbar", background=[("active", SURFACE_3)])

    style.configure(
        "TProgressbar",
        background=PRIMARY,
        troughcolor=SURFACE_3,
        bordercolor=SURFACE_3,
        lightcolor=PRIMARY,
        darkcolor=PRIMARY,
        thickness=7,
    )

    style.configure("TCheckbutton", background=BG, foreground=TEXT_2)
    style.map("TCheckbutton", background=[("active", BG)], foreground=[("active", TEXT)])
    style.configure("TRadiobutton", background=BG, foreground=TEXT_2)
    style.map(
        "TRadiobutton",
        background=[("active", BG)],
        foreground=[("active", TEXT), ("disabled", FAINT)],
    )


def load_logo(height: int) -> tk.PhotoImage:
    """Load the transparent PNG mark, scaled by integer subsampling."""
    png = base64.b64encode(asset_path("document_lock_logo.png").read_bytes()).decode("ascii")
    image = tk.PhotoImage(data=png)
    factor = max(1, round(image.height() / height))
    if factor > 1:
        image = image.subsample(factor, factor)
    return image


def apply_window_icon(root: tk.Tk) -> None:
    """Set the Windows window/taskbar icon from the supplied logo."""
    icon_path = find_asset("document_lock_logo.ico")
    if icon_path is not None:
        try:
            root.iconbitmap(default=str(icon_path))
        except tk.TclError:
            pass
    try:
        image = load_logo(48)
        root.iconphoto(True, image)
        root._app_icon = image                          
    except tk.TclError:
        pass
