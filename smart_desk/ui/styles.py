"""Shared SmartDesk color, typography, and sizing tokens."""

from tkinter import ttk

APP_NAME = "SmartDesk AI"
WINDOW_TITLE = "SmartDesk AI - Local File Assistant"
WINDOW_SIZE = "1440x900"
MIN_WINDOW_SIZE = (1040, 680)
STATUS_CHECK_INTERVAL_MS = 15000
EVENT_POLL_INTERVAL_MS = 100
PREVIEW_CHARACTER_LIMIT = 120_000

COLOR_BG = "#11161B"
COLOR_SIDEBAR = "#171D23"
COLOR_PANEL = "#1D252C"
COLOR_PANEL_LIGHT = "#252F37"
COLOR_TEXT = "#EEF3F5"
COLOR_MUTED = "#9BA8AF"
COLOR_ACCENT = "#55D6BE"
COLOR_USER = "#183F3B"
COLOR_ASSISTANT = "#222B32"
COLOR_BORDER = "#2B373F"
COLOR_GREEN = "#59D9A5"
COLOR_RED = "#FF7777"
COLOR_AMBER = "#F3BF68"
FONT_FAMILY = "Segoe UI"
DOCUMENT_FONT_FAMILY = "Georgia"


def configure_styles(style: ttk.Style) -> None:
    """Apply consistent typography and spacing to ttk controls."""
    style.configure("TButton", font=(FONT_FAMILY, 9), padding=(10, 6))
    style.configure("TScrollbar", arrowsize=11)
