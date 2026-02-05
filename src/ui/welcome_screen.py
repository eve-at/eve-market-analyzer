"""Welcome/Info screen UI component"""
import flet as ft


class WelcomeScreen:
    """Welcome screen with application description"""

    def __init__(self, page: ft.Page, on_continue_callback):
        self.page = page
        self.on_continue_callback = on_continue_callback

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Container(height=50),
                ft.Text(
                    "EVE Online Market Helper",
                    size=36,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Container(height=20),
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "Welcome to EVE Online Market Helper!",
                            size=18,
                            weight=ft.FontWeight.W_500,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Container(height=20),
                        ft.Text(
                            "This application provides tools for EVE Online traders:",
                            size=14,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Container(height=15),
                        ft.Row([
                            ft.Column([
                                ft.Row([
                                    ft.Icon(ft.Icons.HISTORY, color=ft.Colors.BLUE),
                                    ft.Text("View historical market data for any item and region", size=13)
                                ], spacing=10),
                                ft.Row([
                                    ft.Icon(ft.Icons.TRENDING_UP, color=ft.Colors.GREEN),
                                    ft.Text("Find profitable trade opportunities", size=13)
                                ], spacing=10),
                                ft.Row([
                                    ft.Icon(ft.Icons.AUTO_MODE, color=ft.Colors.ORANGE),
                                    ft.Text("Automatic market log monitoring", size=13)
                                ], spacing=10),
                                ft.Row([
                                    ft.Icon(ft.Icons.SETTINGS, color=ft.Colors.GREY),
                                    ft.Text("Customize settings for your trading style", size=13)
                                ], spacing=10),
                            ], spacing=12),
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Container(height=25),
                        ft.Text(
                            "Database is ready with static data loaded.",
                            size=13,
                            color=ft.Colors.GREEN_700,
                            text_align=ft.TextAlign.CENTER
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    width=600,
                ),
                ft.Container(height=30),
                ft.ElevatedButton(
                    "Continue",
                    on_click=lambda e: self.on_continue_callback(),
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.BLUE,
                        color=ft.Colors.WHITE,
                        padding=ft.Padding(40, 15, 40, 15)
                    )
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment.CENTER,
            expand=True
        )

    def build(self):
        """Build and return the UI container"""
        return self.container
