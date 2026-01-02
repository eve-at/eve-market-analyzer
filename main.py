"""EVE Online Market Helper - Main Entry Point"""
import flet as ft
from src.ui import (
    InitScreen,
    WelcomeScreen,
    MainMenu,
    TradeOpportunitiesScreen,
    SettingsScreen
)
from src.app import EVEMarketApp
from src.database import load_regions_and_items
from settings import MARKETLOGS_DIR


class MainApp:
    """Main application controller"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "EVE Online Market Helper"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window.width = 1000
        self.page.window.height = 800

        # Screens
        self.init_screen = None
        self.welcome_screen = None
        self.main_menu = None
        self.market_app = None
        self.trade_opportunities_screen = None
        self.settings_screen = None
        self.update_data_screen = None

        # Data
        self.regions_data = {}
        self.items_data = {}

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
        # Load data from database
        self.regions_data, self.items_data = load_regions_and_items()

        # Show welcome screen
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
        self.page.controls.clear()

        self.main_menu = MainMenu(
            page=self.page,
            on_menu_select=self.on_menu_select
        )

        self.page.add(self.main_menu.build())
        self.page.update()

    def on_menu_select(self, menu_key):
        """Handle menu selection"""
        if menu_key == "update_data":
            self.show_update_data_screen()
        elif menu_key == "market_history":
            self.show_market_history()
        elif menu_key == "trade_opportunities":
            self.show_trade_opportunities()
        elif menu_key == "settings":
            self.show_settings()

    def show_update_data_screen(self):
        """Show update static data screen"""
        self.page.controls.clear()

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

        # Add back button
        back_button = ft.TextButton(
            "← Back to Menu",
            on_click=lambda e: self.show_main_menu()
        )

        container = ft.Container(
            content=ft.Column([
                ft.Row([back_button], alignment=ft.MainAxisAlignment.START, spacing=10),
                self.update_data_screen.build()
            ]),
            expand=True
        )

        self.page.add(container)
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

        # Create back button
        back_button = ft.TextButton(
            "← Back to Menu",
            on_click=lambda e: self.on_market_history_back()
        )

        # Create container for market app with back button
        container = ft.Container(
            content=ft.Column([
                ft.Row([back_button], alignment=ft.MainAxisAlignment.START, spacing=10),
                ft.Container(height=10)
            ]),
            expand=False
        )

        self.page.add(container)

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

        self.trade_opportunities_screen = TradeOpportunitiesScreen(
            page=self.page,
            regions_data=self.regions_data,
            on_back_callback=self.show_main_menu
        )

        self.page.add(self.trade_opportunities_screen.build())
        self.page.update()

    def show_settings(self):
        """Show settings screen"""
        self.page.controls.clear()

        self.settings_screen = SettingsScreen(
            page=self.page,
            on_back_callback=self.show_main_menu,
            marketlogs_dir=MARKETLOGS_DIR
        )

        self.page.add(self.settings_screen.build())
        self.page.update()


def main(page: ft.Page):
    """Main entry point for the application"""
    MainApp(page)


if __name__ == "__main__":
    ft.run(main)
