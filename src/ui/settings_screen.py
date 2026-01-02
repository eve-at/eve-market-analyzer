"""Settings screen UI component"""
import flet as ft


class SettingsScreen:
    """Application settings screen"""

    def __init__(self, page: ft.Page, on_back_callback, marketlogs_dir=""):
        self.page = page
        self.on_back_callback = on_back_callback

        # Settings fields
        self.broker_fee_field = ft.TextField(
            label="Broker Fee, %",
            value="3.00",
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.sales_tax_field = ft.TextField(
            label="Sales Tax, %",
            value="7.50",
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.marketlogs_dir_field = ft.TextField(
            label="Market Logs Directory",
            value=marketlogs_dir,
            width=500,
            hint_text="Path to EVE Online market logs folder"
        )

        # Buttons
        self.save_button = ft.ElevatedButton(
            "Save",
            on_click=self.on_save,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(30, 10, 30, 10)
            )
        )

        self.back_button = ft.TextButton(
            "← Back to Menu",
            on_click=lambda e: self.on_back_callback()
        )

        # Status text
        self.status_text = ft.Text("", size=14)

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Row([
                    self.back_button
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=10),
                ft.Text(
                    "Settings",
                    size=28,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(height=10),
                ft.Text(
                    "Configure application settings",
                    size=14,
                    color=ft.Colors.GREY_700
                ),
                ft.Container(height=30),

                # Trading settings section
                ft.Text(
                    "Trading Settings",
                    size=18,
                    weight=ft.FontWeight.W_500
                ),
                ft.Container(height=10),
                ft.Row([
                    self.broker_fee_field,
                    self.sales_tax_field
                ], spacing=20),
                ft.Container(height=30),

                # Application settings section
                ft.Text(
                    "Application Settings",
                    size=18,
                    weight=ft.FontWeight.W_500
                ),
                ft.Container(height=10),
                self.marketlogs_dir_field,
                ft.Container(height=30),

                # Save button
                ft.Row([
                    self.save_button
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=10),
                self.status_text
            ], spacing=5),
            padding=20,
            expand=True
        )

    def on_save(self, e):
        """Handle save button click"""
        # TODO: Implement settings save functionality
        self.status_text.value = "Settings save functionality - coming soon"
        self.status_text.color = ft.Colors.ORANGE
        self.page.update()

    def build(self):
        """Build and return the UI container"""
        return self.container
