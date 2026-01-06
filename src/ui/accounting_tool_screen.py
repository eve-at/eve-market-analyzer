"""Accounting Tool screen UI component"""
import flet as ft


class AccountingToolScreen:
    """Screen for accounting tool"""

    def __init__(self, page: ft.Page, on_back_callback):
        self.page = page
        self.on_back_callback = on_back_callback

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Accounting Tool",
                    size=28,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(height=10),
                ft.Text(
                    "Track transactions and calculate profits",
                    size=14,
                    color=ft.Colors.GREY_700
                ),
                ft.Container(height=30),
                ft.Text(
                    "This feature is under development",
                    size=16,
                    color=ft.Colors.GREY_600,
                    text_align=ft.TextAlign.CENTER
                )
            ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
            expand=True
        )

    def build(self):
        """Build and return the UI container"""
        return self.container
