"""Canonical module entry point for SmartDesk AI."""

from smart_desk.ui.app import SmartDeskApp


def main() -> None:
    """Start the SmartDesk desktop application."""
    SmartDeskApp().run()


if __name__ == "__main__":
    main()
