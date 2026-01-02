"""Market history screen UI component - wrapper around EVEMarketApp"""
import flet as ft
from src.app import EVEMarketApp


class MarketHistoryScreen:
    """Screen for viewing market history"""

    def __init__(self, page: ft.Page, on_back_callback):
        self.page = page
        self.on_back_callback = on_back_callback

        # Back button
        self.back_button = ft.TextButton(
            "← Back to Menu",
            on_click=lambda e: self.handle_back()
        )

        # Placeholder for market app content
        self.content_container = ft.Container(expand=True)

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Row([
                    self.back_button
                ], alignment=ft.MainAxisAlignment.START),
                self.content_container
            ], spacing=0),
            padding=ft.Padding.only(top=10, left=10, right=10),
            expand=True
        )

        # Initialize market app
        self.market_app = None

    def handle_back(self):
        """Handle back button - stop file monitoring and return to menu"""
        if self.market_app:
            self.market_app.stop_file_monitoring()
        self.on_back_callback()

    def initialize_market_app(self):
        """Initialize and display market app"""
        if not self.market_app:
            # Create a temporary page-like container for the market app
            self.market_app = EVEMarketApp(self.page)
            # We'll need to extract the UI from the market app
            # For now, just trigger page rebuild

    def build(self):
        """Build and return the UI container"""
        return self.container
