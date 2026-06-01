"""Application top bar component"""
import flet as ft
from src.database.models import get_current_character_id, get_character


class AppBar:
    """Top application bar with character info"""

    def __init__(self, page: ft.Page, on_character_click, on_settings_click, on_title_click=None, show_back_button=False, on_back_click=None):
        self.page = page
        self.on_character_click = on_character_click
        self.on_settings_click = on_settings_click
        self.on_title_click = on_title_click
        self.show_back_button = show_back_button
        self.on_back_click = on_back_click
        self.current_character = None

        # Persistent status widget — survives app bar rebuilds
        self.sync_status_text = ft.Text(
            "",
            size=11,
            color=ft.Colors.with_opacity(0.7, ft.Colors.WHITE),
            italic=True,
        )

        self.load_character()
        self.app_bar = self.build_app_bar()

    def load_character(self):
        """Load current character from database"""
        character_id = get_current_character_id()
        if character_id:
            self.current_character = get_character(character_id)
        else:
            self.current_character = None

    def build_app_bar(self):
        """Build the app bar UI"""
        if self.current_character:
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
                on_click=lambda _: self.on_character_click(),
                ink=True
            )
        else:
            character_button = ft.Container(
                content=ft.Text(
                    "Log In",
                    size=12,
                    weight=ft.FontWeight.W_500,
                    color=ft.Colors.GREY_700
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=3),
                border_radius=20,
                bgcolor=ft.Colors.WHITE,
                on_click=lambda _: self.on_character_click(),
                ink=True
            )

        settings_button = ft.IconButton(
            icon=ft.Icons.SETTINGS,
            icon_size=20,
            icon_color=ft.Colors.WHITE,
            tooltip="Settings",
            on_click=lambda _: self.on_settings_click()
        )

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
                on_click=lambda _: self.on_title_click(),
                ink=True,
                border_radius=5,
                padding=ft.padding.symmetric(horizontal=10, vertical=5)
            )
        else:
            title_container = title_widget

        row_controls = []

        if self.show_back_button and self.on_back_click:
            back_button = ft.TextButton(
                "< Home",
                on_click=lambda _: self.on_back_click(),
                style=ft.ButtonStyle(color=ft.Colors.WHITE)
            )
            row_controls.append(back_button)
        else:
            row_controls.append(ft.Container(width=80))

        # Title centered
        row_controls.append(ft.Container(expand=True))
        row_controls.append(title_container)
        row_controls.append(ft.Container(expand=True))

        # Sync status — shown only when character is logged in
        if self.current_character:
            row_controls.append(self.sync_status_text)
            row_controls.append(ft.Container(width=12))

        row_controls.append(character_button)
        row_controls.append(ft.Container(width=5))
        row_controls.append(settings_button)

        return ft.Container(
            content=ft.Row(row_controls, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.symmetric(horizontal=20, vertical=3),
            bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.ON_SURFACE),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT))
        )

    def set_sync_status(self, text):
        """Update the sync status text in-place (no full rebuild needed)."""
        self.sync_status_text.value = text

    def refresh(self):
        """Reload character and rebuild app bar (e.g. after login/logout)."""
        self.load_character()
        self.app_bar = self.build_app_bar()

    def get(self):
        """Return the app bar container."""
        return self.app_bar
