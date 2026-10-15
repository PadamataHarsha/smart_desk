"""Reusable controls for the SmartDesk desktop interface."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

import ttkbootstrap as tb

from smart_desk.ui.styles import COLOR_TEXT, FONT_FAMILY


class Tooltip:
    """Display concise help after the pointer pauses over a control."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.window: tk.Toplevel | None = None
        self.pending_id: str | None = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, _event: tk.Event[Any] | None = None) -> None:
        self._hide()
        self.pending_id = self.widget.after(450, self._show)

    def _show(self) -> None:
        self.pending_id = None
        if self.window or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 7
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.window,
            text=self.text,
            bg="#303B43",
            fg=COLOR_TEXT,
            padx=9,
            pady=6,
            font=(FONT_FAMILY, 9),
        ).pack()

    def _hide(self, _event: tk.Event[Any] | None = None) -> None:
        if self.pending_id:
            try:
                self.widget.after_cancel(self.pending_id)
            except tk.TclError:
                pass
            self.pending_id = None
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None


class Toast:
    """Show a short-lived, non-modal success or status message."""

    def __init__(self, parent: tk.Misc, message: str, duration_ms: int = 2600) -> None:
        self.parent = parent
        parent.update_idletasks()
        self.window = tk.Toplevel(parent)
        self.window.wm_overrideredirect(True)
        self.window.configure(bg="#26342F")
        x = parent.winfo_rootx() + max(20, parent.winfo_width() - 340)
        y = parent.winfo_rooty() + max(20, parent.winfo_height() - 88)
        self.window.geometry(f"300x44+{x}+{y}")
        tk.Label(
            self.window,
            text=message,
            bg="#26342F",
            fg="#D9F5E8",
            padx=14,
            pady=10,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill="both", expand=True)
        self.window.after(duration_ms, self.dismiss)

    def dismiss(self) -> None:
        """Close the toast if its parent is still alive."""
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except tk.TclError:
            pass


def create_button(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None],
    style: str,
    tooltip: str,
) -> tb.Button:
    """Create a themed button with a tooltip."""
    button = tb.Button(parent, text=text, command=command, bootstyle=style)
    Tooltip(button, tooltip)
    return button
