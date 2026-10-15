"""Parent-aware dialog helpers for consistent desktop error handling."""

import tkinter as tk
from tkinter import messagebox


def show_error(title: str, message: str, parent: tk.Misc | None = None) -> None:
    """Present a blocking error dialog attached to the application window."""
    messagebox.showerror(title, message, parent=parent)


def show_warning(title: str, message: str, parent: tk.Misc | None = None) -> None:
    """Present a blocking warning dialog attached to the application window."""
    messagebox.showwarning(title, message, parent=parent)


def show_info(title: str, message: str, parent: tk.Misc | None = None) -> None:
    """Present a blocking informational dialog attached to the application window."""
    messagebox.showinfo(title, message, parent=parent)


def confirm(title: str, message: str, parent: tk.Misc | None = None) -> bool:
    """Return whether the user confirmed a potentially destructive action."""
    return bool(messagebox.askyesno(title, message, parent=parent))
