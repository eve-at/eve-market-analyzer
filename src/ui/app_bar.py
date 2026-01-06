"""Application top bar component"""
import flet as ft
from src.database.models import get_current_character_id, get_character


class AppBar:
    """Top application bar with character info"""

    def __init__(self, page: ft.Page, on_settings_click, on_title_click=None, show_back_button=False, on_back_click=None):
        self.page = page
        self.on_settings_click = on_settings_click
        self.on_title_click = on_title_click
        self.show_back_button = show_back_button
        self.on_back_click = on_back_click
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
            # Not logged in: show default avatar and "Settings"
            character_button = ft.Container(
                content=ft.Row([
                    ft.Image(
                        src='static/img/default_avatar.svg',
                        width=16,
                        height=16,
                        fit=ft.BoxFit.COVER
                    ),
                    ft.Text(
                        "Settings",
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

        # Title container (clickable if callback provided)
        title_widget = ft.Text(
            "EVE Online Accounting Tool",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE,
            text_align=ft.TextAlign.CENTER
        )

        if self.on_title_click:
            title_container = ft.Container(
                content=title_widget,
                on_click=lambda e: self.on_title_click(),
                ink=True,
                border_radius=5,
                padding=ft.padding.symmetric(horizontal=10, vertical=5)
            )
        else:
            title_container = title_widget

        # Build app bar row content
        row_controls = []

        # Back button (if enabled)
        if self.show_back_button and self.on_back_click:
            back_button = ft.TextButton(
                "< Back",
                on_click=lambda e: self.on_back_click(),
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE
                )
            )
            row_controls.append(back_button)
        else:
            # Empty container for spacing
            row_controls.append(ft.Container(width=80))

        # Title (centered)
        row_controls.append(ft.Container(expand=True))
        row_controls.append(title_container)
        row_controls.append(ft.Container(expand=True))

        # Character button
        row_controls.append(character_button)

        # App bar container
        app_bar = ft.Container(
            content=ft.Row(
                row_controls,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
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
