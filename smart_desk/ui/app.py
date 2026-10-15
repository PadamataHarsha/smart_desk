"""Package entry class for the SmartDesk desktop window."""

from ui.main_window import SmartDeskApp as _SmartDeskApp


class SmartDeskApp(_SmartDeskApp):
	"""Expose the established window through the canonical package API."""


__all__ = ["SmartDeskApp"]
