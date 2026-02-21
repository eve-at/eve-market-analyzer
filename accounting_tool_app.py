"""Standalone Accounting Tool Window - runs as a separate process"""
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
from src.ui import AccountingToolScreen

LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", ".accounting_tool.lock")
WINDOW_TITLE = "EVE Accounting Tool"


def remove_lock():
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def accounting_main(page: ft.Page):
    page.title = WINDOW_TITLE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 600
    page.window.height = 750

    screen = AccountingToolScreen(
        page=page,
        on_back_callback=lambda: page.window.close()
    )

    page.add(screen.build())
    page.update()
    screen.start_file_monitoring()

    def on_window_event(e):
        if e.data == "close":
            screen.stop_file_monitoring()
            remove_lock()

    page.window.on_event = on_window_event


if __name__ == "__main__":
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        ft.run(accounting_main)
    finally:
        remove_lock()
