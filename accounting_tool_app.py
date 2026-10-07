"""Standalone Accounting Tool Window - runs as a separate process"""
import asyncio
import asyncio.proactor_events
import sys
import os
import ctypes
import ctypes.wintypes

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _patch_proactor_shutdown():
    _orig = asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost

    def _patched(self, exc):
        try:
            _orig(self, exc)
        except (ConnectionResetError, OSError):
            pass

    asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost = _patched


_patch_proactor_shutdown()

import flet as ft
from src.ui import AccountingToolScreen
from src.database import get_setting, save_setting


def _window_position_on_screen(left, top):
    try:
        user32 = ctypes.windll.user32
        vx = user32.GetSystemMetrics(76)
        vy = user32.GetSystemMetrics(77)
        vw = user32.GetSystemMetrics(78)
        vh = user32.GetSystemMetrics(79)
        return vx <= left < vx + vw and vy <= top < vy + vh
    except Exception:
        return False

LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", ".accounting_tool.lock")
WINDOW_TITLE = "EVE Accounting Tool"


def remove_lock():
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def _win32_get_window_rect(title):
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return None
        rect = ctypes.wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        pass
    return None



def accounting_main(page: ft.Page):
    import threading
    import time

    page.title = WINDOW_TITLE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = int(get_setting('window_accounting_width', '600'))
    page.window.height = int(get_setting('window_accounting_height', '750'))

    screen = AccountingToolScreen(
        page=page,
        on_back_callback=lambda: page.window.close()
    )

    page.add(screen.build())
    page.update()
    screen.start_file_monitoring()

    # --- Position monitor: caches rect every second so save-on-close always has fresh data ---
    _cached = {'rect': None}
    _stop_monitor = threading.Event()

    def _position_monitor():
        while not _stop_monitor.is_set():
            rect = _win32_get_window_rect(WINDOW_TITLE)
            if rect and rect != _cached['rect']:
                _cached['rect'] = rect
                save_setting('window_accounting_left', str(rect[0]))
                save_setting('window_accounting_top', str(rect[1]))
                save_setting('window_accounting_width', str(rect[2]))
                save_setting('window_accounting_height', str(rect[3]))
                screen.update_window_coords(rect[0], rect[1])
            time.sleep(1.0)

    threading.Thread(target=_position_monitor, daemon=True).start()

    # --- Restore saved position: retry until window handle appears (up to 3s) ---
    saved_left = get_setting('window_accounting_left', None)
    saved_top = get_setting('window_accounting_top', None)
    saved_width = get_setting('window_accounting_width', '600')
    saved_height = get_setting('window_accounting_height', '750')

    if saved_left is not None and saved_top is not None:
        t_left = int(float(saved_left))
        t_top = int(float(saved_top))
        t_width = int(float(saved_width))
        t_height = int(float(saved_height))

        if _window_position_on_screen(t_left, t_top):
            def _restore():
                for _ in range(30):          # up to 3 s
                    time.sleep(0.1)
                    hwnd = ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)
                    if hwnd:
                        SWP_NOZORDER = 0x0004
                        ctypes.windll.user32.SetWindowPos(
                            hwnd, 0, t_left, t_top, t_width, t_height, SWP_NOZORDER
                        )
                        return
            threading.Thread(target=_restore, daemon=True).start()

    def on_window_event(e):
        if e.data == "close":
            _stop_monitor.set()
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
