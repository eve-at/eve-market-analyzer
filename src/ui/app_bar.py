"""Application top bar component"""
import flet as ft
from src.database.models import get_current_character_id, get_character


class AppBar:
    """Top application bar with character info"""

    def __init__(self, page: ft.Page, on_settings_click):
        self.page = page
        self.on_settings_click = on_settings_click
        self.current_character = None

        # Load current character
        self.load_character()

        # Create app bar
        self.app_bar = self.build_app_bar()

    def load_character(self):
        """Load current character from database"""
        character_id = get_current_character_id()
        if character_id:
            self.current_character = get_character(character_id)

    def build_app_bar(self):
        """Build the app bar UI"""
        # Character info or login prompt
        if self.current_character:
            # Logged in: show avatar and name
            character_button = ft.Container(
                content=ft.Row([
                    ft.Image(
                        src=self.current_character.get('character_portrait_url', 'static/img/default_avatar.svg'),
                        width=16,
                        height=16,
                        border_radius=16,
                        fit=ft.BoxFit.COVER
                    ),
                    ft.Text(
                        self.current_character.get('character_name', 'Unknown'),
                        size=12,
                        weight=ft.FontWeight.W_500
                    )
                ], spacing=8),
                padding=ft.padding.symmetric(horizontal=12, vertical=3),
                border_radius=20,
                bgcolor=ft.Colors.WHITE,
                on_click=lambda e: self.on_settings_click(),
                ink=True
            )
        else:
            # Not logged in: show default avatar and "Log in"
            character_button = ft.Container(
                content=ft.Row([
                    ft.Image(
                        src='static/img/default_avatar.svg',
                        width=16,
                        height=16,
                        fit=ft.BoxFit.COVER
                    ),
                    ft.Text(
                        "Log in",
                        size=12,
                        weight=ft.FontWeight.W_500,
                        color=ft.Colors.GREY_700
                    )
                ], spacing=8),
                padding=ft.padding.symmetric(horizontal=12, vertical=3),
                border_radius=20,
                bgcolor=ft.Colors.WHITE,
                on_click=lambda e: self.on_settings_click(),
                ink=True
            )

        # App bar container
        app_bar = ft.Container(
            content=ft.Row([
                ft.Text(
                    "EVE Online Market Helper",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE
                ),
                ft.Container(expand=True),  # Spacer
                character_button
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.symmetric(horizontal=20, vertical=3),
            bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.ON_SURFACE),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT))
        )

        return app_bar

    def refresh(self):
        """Refresh character info"""
        self.load_character()
        self.app_bar = self.build_app_bar()

    def get(self):
        """Get the app bar component"""
        return self.app_bar
