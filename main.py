"""EVE Online Market Helper - Main Entry Point"""
import flet as ft
import subprocess
import sys
import os
import ctypes
from src.ui import (
    InitScreen,
    WelcomeScreen,
    MainMenu,
    TradeOpportunitiesScreen,
    SettingsScreen,
    CharacterScreen,
    AppBar,
    CourierPathFinderScreen,
    RestockingScreen,
)
from src.app import EVEMarketApp
from src.database import load_regions_and_items, create_tables, get_setting
from src.database.models import get_current_character_id, get_character
from src.services import WalletAutoSync
from settings import MARKETLOGS_DIR

ACCOUNTING_TOOL_LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", ".accounting_tool.lock")
ACCOUNTING_TOOL_WINDOW_TITLE = "EVE Accounting Tool"


class MainApp:
    """Main application controller"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "EVE Online Market Helper"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window.width = 1000
        self.page.window.height = 800

        # Auto-sync service (runs for the lifetime of the app)
        self.wallet_auto_sync = WalletAutoSync()

        # Screens
        self.init_screen = None
        self.welcome_screen = None
        self.main_menu = None
        self.market_app = None
        self.trade_opportunities_screen = None
        self.settings_screen = None
        self.character_screen = None
        self.update_data_screen = None
        self.accounting_tool_process = None
        self.courier_path_finder_screen = None
        self.restocking_screen = None

        # App bar
        self.app_bar = None

        # Data
        self.regions_data = {}
        self.items_data = {}

        # Intercept window close to shut down Accounting Tool
        self.page.window.prevent_close = True
        self.page.window.on_event = self._on_window_event

        # Show initialization screen
        self.show_init_screen()

    def show_init_screen(self):
        """Show initialization screen to check database"""
        self.page.controls.clear()

        self.init_screen = InitScreen(
            page=self.page,
            on_complete_callback=self.on_init_complete
        )

        self.page.add(self.init_screen.build())
        self.page.update()

        # Start database check
        self.init_screen.check_database()

    def on_init_complete(self):
        """Called when initialization is complete and database is ready"""
        create_tables()
        self.regions_data, self.items_data = load_regions_and_items()

        # Start auto-sync if a character is already logged in
        character_id = get_current_character_id()
        if character_id:
            character = get_character(character_id)
            if character:
                self.wallet_auto_sync.start(character, self.page)

        self.show_welcome_screen()

    def show_welcome_screen(self):
        """Show welcome/info screen"""
        self.page.controls.clear()

        self.welcome_screen = WelcomeScreen(
            page=self.page,
            on_continue_callback=self.show_main_menu
        )

        self.page.add(self.welcome_screen.build())
        self.page.update()

    def show_main_menu(self):
        """Show main menu"""
        self._stop_restocking_monitoring()
        self.page.controls.clear()

        # Create app bar (main menu doesn't show back button)
        self.app_bar = AppBar(
            self.page,
            on_character_click=self.show_character,
            on_settings_click=self.show_settings,
            on_title_click=self.show_main_menu,
            show_back_button=False
        )
        self._connect_sync_to_appbar()

        self.main_menu = MainMenu(
            page=self.page,
            on_menu_select=self.on_menu_select
        )

        self.page.add(
            ft.Column([
                self.app_bar.get(),
                ft.Container(content=self.main_menu.build(), expand=True)
            ], spacing=0, expand=True)
        )
        self.page.update()

    def on_menu_select(self, menu_key):
        """Handle menu selection"""
        if menu_key == "update_data":
            self.show_update_data_screen()
        elif menu_key == "market_history":
            self.show_market_history()
        elif menu_key == "trade_opportunities":
            self.show_trade_opportunities()
        elif menu_key == "accounting_tool":
            self.show_accounting_tool()
        elif menu_key == "courier_path_finder":
            self.show_courier_path_finder()
        elif menu_key == "restocking_list":
            self.show_restocking()

    def show_update_data_screen(self):
        """Show update static data screen"""
        self.page.controls.clear()

        # Create app bar with back button
        self.app_bar = AppBar(
            self.page,
            on_character_click=self.show_character,
            on_settings_click=self.show_settings,
            on_title_click=self.show_main_menu,
            show_back_button=True,
            on_back_click=self.show_main_menu
        )
        self._connect_sync_to_appbar()

        # Reuse InitScreen for data import
        self.update_data_screen = InitScreen(
            page=self.page,
            on_complete_callback=self.on_update_complete
        )

        # Customize the screen for update mode
        self.update_data_screen.status_text.value = "Click 'Fill static data' to update"
        self.update_data_screen.import_button.visible = True
        self.update_data_screen.import_button.text = "Update Static Data"
        self.update_data_screen.progress_ring.visible = False

        container = ft.Container(
            content=self.update_data_screen.build(),
            expand=True
        )

        self.page.add(
            ft.Column([
                self.app_bar.get(),
                container
            ], spacing=0, expand=True)
        )
        self.page.update()

    def on_update_complete(self):
        """Called when data update is complete"""
        # Reload data
        self.regions_data, self.items_data = load_regions_and_items()
        # Return to menu
        self.show_main_menu()

    def show_market_history(self):
        """Show market history screen"""
        self.page.controls.clear()

        # Create app bar with back button
        self.app_bar = AppBar(
            self.page,
            on_character_click=self.show_character,
            on_settings_click=self.show_settings,
            on_title_click=self.show_main_menu,
            show_back_button=True,
            on_back_click=self.on_market_history_back
        )
        self._connect_sync_to_appbar()

        # Add app bar
        self.page.add(
            ft.Column([
                self.app_bar.get()
            ], spacing=0, expand=False)
        )

        # Initialize market app (it will add its own content to the page)
        if self.market_app:
            self.market_app.stop_file_monitoring()
        self.market_app = EVEMarketApp(self.page)

    def on_market_history_back(self):
        """Handle back from market history"""
        if self.market_app:
            self.market_app.stop_file_monitoring()
        self.show_main_menu()

    def show_trade_opportunities(self):
        """Show trade opportunities screen"""
        self.page.controls.clear()

        # Create app bar with back button
        self.app_bar = AppBar(
            self.page,
            on_character_click=self.show_character,
            on_settings_click=self.show_settings,
            on_title_click=self.show_main_menu,
            show_back_button=True,
            on_back_click=self.show_main_menu
        )
        self._connect_sync_to_appbar()

        self.trade_opportunities_screen = TradeOpportunitiesScreen(
            page=self.page,
            regions_data=self.regions_data,
            on_back_callback=self.show_main_menu
        )

        self.page.add(
            ft.Column([
                self.app_bar.get(),
                ft.Container(content=self.trade_opportunities_screen.build(), expand=True)
            ], spacing=0, expand=True)
        )
        self.page.update()

    def show_settings(self):
        """Show settings screen"""
        self._stop_restocking_monitoring()
        self.page.controls.clear()

        # Create app bar with back button
        self.app_bar = AppBar(
            self.page,
            on_character_click=self.show_character,
            on_settings_click=self.show_settings,
            on_title_click=self.show_main_menu,
            show_back_button=True,
            on_back_click=self.show_main_menu
        )
        self._connect_sync_to_appbar()

        # Load marketlogs_dir from database or use default from settings.py
        marketlogs_dir = get_setting('marketlogs_dir', MARKETLOGS_DIR)

        self.settings_screen = SettingsScreen(
            page=self.page,
            on_back_callback=self.show_main_menu,
            marketlogs_dir=marketlogs_dir
        )

        self.page.add(
            ft.Column([
                self.app_bar.get(),
                ft.Container(content=self.settings_screen.build(), expand=True)
            ], spacing=0, expand=True)
        )
        self.page.update()

    def show_character(self):
        """Show character screen"""
        self._stop_restocking_monitoring()
        self.page.controls.clear()

        # Create app bar with back button
        self.app_bar = AppBar(
            self.page,
            on_character_click=self.show_character,
            on_settings_click=self.show_settings,
            on_title_click=self.show_main_menu,
            show_back_button=True,
            on_back_click=self.show_main_menu
        )
        self._connect_sync_to_appbar()

        self.character_screen = CharacterScreen(
            page=self.page,
            on_back_callback=self.show_main_menu,
            on_logout_callback=self.on_logout,
            on_login_callback=self.on_login,
        )

        self.page.add(
            ft.Column([
                self.app_bar.get(),
                ft.Container(content=self.character_screen.build(), expand=True)
            ], spacing=0, expand=True)
        )
        self.page.update()

    def show_accounting_tool(self):
        """Open accounting tool in a separate window"""
        if self._is_accounting_tool_running():
            self._focus_accounting_tool_window()
            return

        # Launch as a separate process
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounting_tool_app.py")
        self.accounting_tool_process = subprocess.Popen(
            [sys.executable, script_path],
            creationflags=subprocess.DETACHED_PROCESS
        )

    def _focus_accounting_tool_window(self):
        """Find and focus the existing Accounting Tool window"""
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, ACCOUNTING_TOOL_WINDOW_TITLE)

        if hwnd:
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            # Simulate Alt key press to bypass Windows foreground restrictions
            user32.keybd_event(0x12, 0, 0, 0)
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(0x12, 0, 2, 0)

    def show_courier_path_finder(self):
        """Show courier path finder screen"""
        self.page.controls.clear()

        # Create app bar with back button
        self.app_bar = AppBar(
            self.page,
            on_character_click=self.show_character,
            on_settings_click=self.show_settings,
            on_title_click=self.show_main_menu,
            show_back_button=True,
            on_back_click=self.show_main_menu
        )
        self._connect_sync_to_appbar()

        self.courier_path_finder_screen = CourierPathFinderScreen(
            page=self.page,
            on_back_callback=self.show_main_menu
        )

        self.page.add(
            ft.Column([
                self.app_bar.get(),
                ft.Container(content=self.courier_path_finder_screen.build(), expand=True)
            ], spacing=0, expand=True)
        )
        self.page.update()

    def _stop_restocking_monitoring(self):
        """Stop file monitoring if the restocking screen is active."""
        if self.restocking_screen:
            self.restocking_screen.stop_file_monitoring()

    def show_restocking(self):
        """Show restocking list screen"""
        self.page.controls.clear()

        self.app_bar = AppBar(
            self.page,
            on_character_click=self.show_character,
            on_settings_click=self.show_settings,
            on_title_click=self.show_main_menu,
            show_back_button=True,
            on_back_click=self._back_from_restocking
        )
        self._connect_sync_to_appbar()

        self.restocking_screen = RestockingScreen(
            page=self.page,
            regions_data=self.regions_data,
            on_back_callback=self._back_from_restocking
        )

        self.page.add(
            ft.Column([
                self.app_bar.get(),
                ft.Container(content=self.restocking_screen.build(), expand=True)
            ], spacing=0, expand=True)
        )
        self.page.update()
        self.restocking_screen.start_auto_load()
        self.restocking_screen.start_file_monitoring()

    def _back_from_restocking(self):
        """Navigate back from restocking screen, stopping file monitoring first."""
        self._stop_restocking_monitoring()
        self.show_main_menu()

    def on_login(self, character_data):
        """Called after successful EVE SSO login."""
        self.wallet_auto_sync.start(character_data, self.page)
        if self.app_bar:
            self.app_bar.refresh()
            self._connect_sync_to_appbar()
            self.page.update()

    def on_logout(self):
        """Handle logout - stop auto-sync and refresh app bar."""
        self.wallet_auto_sync.stop()
        if self.app_bar:
            self.app_bar.refresh()
            self.page.update()

    def _connect_sync_to_appbar(self):
        """Wire WalletAutoSync status updates into the current AppBar."""
        if self.app_bar:
            self.wallet_auto_sync.set_status_callback(self.app_bar.set_sync_status)

    def _on_window_event(self, e):
        if e.data == "close":
            try:
                if self.accounting_tool_process and self.accounting_tool_process.poll() is None:
                    self.accounting_tool_process.kill()
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, ACCOUNTING_TOOL_WINDOW_TITLE)
                if hwnd:
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)
                # kill() skips the process finally-block — remove lock file manually
                try:
                    os.remove(ACCOUNTING_TOOL_LOCK_FILE)
                except OSError:
                    pass
            except Exception as ex:
                print(f"Error closing accounting tool: {ex}")
            finally:
                self.page.window.destroy()

    def _is_accounting_tool_running(self):
        """Check if the accounting tool process is still alive."""
        if not os.path.exists(ACCOUNTING_TOOL_LOCK_FILE):
            return False
        try:
            with open(ACCOUNTING_TOOL_LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong(0)
            kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            return exit_code.value == STILL_ACTIVE
        except (ValueError, OSError):
            return False


def main(page: ft.Page):
    """Main entry point for the application"""
    MainApp(page)


if __name__ == "__main__":
    ft.run(main)
