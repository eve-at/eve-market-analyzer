"""EVE Online Market Helper - Main Entry Point"""
import flet as ft
from src.ui import InitScreen
from src.app import EVEMarketApp


class MainApp:
    """Main application controller"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "EVE Online Market Helper"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window.width = 1000
        self.page.window.height = 800

        self.init_screen = None
        self.market_app = None

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
        # Clear page and show main application
        self.page.controls.clear()
        self.page.update()

        # Initialize main market app
        self.market_app = EVEMarketApp(self.page)


def main(page: ft.Page):
    """Main entry point for the application"""
    MainApp(page)


if __name__ == "__main__":
    ft.run(main)
