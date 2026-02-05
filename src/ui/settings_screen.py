"""Settings screen UI component"""
import flet as ft
from src.database.models import (
    save_setting, get_setting
)


class SettingsScreen:
    """Application settings screen"""

    def __init__(self, page: ft.Page, on_back_callback, marketlogs_dir=""):
        self.page = page
        self.on_back_callback = on_back_callback

        # Load marketlogs directory from database or use provided default
        saved_marketlogs = get_setting('marketlogs_dir', marketlogs_dir)

        # Load CSV export path from database or use default
        saved_csv_export_path = get_setting('csv_export_path', 'data')

        self.marketlogs_dir_field = ft.TextField(
            label="Market Logs Directory",
            value=saved_marketlogs,
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

        # Status text
        self.status_text = ft.Text("", size=14)

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Settings",
                    size=28,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(height=10),

                # Application settings section
                self.marketlogs_dir_field,

                # Save button
                ft.Row([
                    self.save_button
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=10),
                self.status_text
            ], spacing=5, scroll=ft.ScrollMode.AUTO),
            padding=20,
            expand=True
        )

    def on_save(self, e):
        """Handle save button click"""
        try:
            # Save marketlogs directory to global settings
            save_setting('marketlogs_dir', self.marketlogs_dir_field.value)

            self.status_text.value = "Settings saved successfully!"
            self.status_text.color = ft.Colors.GREEN

        except Exception as e:
            self.status_text.value = f"Error saving settings: {str(e)}"
            self.status_text.color = ft.Colors.RED

        self.page.update()

    def build(self):
        """Build and return the UI container"""
        return self.container
