"""Suggestion item UI component"""
import flet as ft


class SuggestionItem:
    """Class for suggestion item with its own handler"""
    def __init__(self, name, item_id, callback):
        self.name = name
        self.item_id = item_id
        self.callback = callback

    def on_click(self, e):
        """Click handler"""
        self.callback(self.name, self.item_id)

    def build(self):
        """Create UI element"""
        btn = ft.Button(
            content=ft.Container(
                content=ft.Text(self.name, size=13),
                alignment=ft.Alignment.CENTER_LEFT
            ),
            width=300,
            style=ft.ButtonStyle(
                padding=ft.Padding(10, 10, 10, 10),
                bgcolor=ft.Colors.WHITE,
                side=ft.BorderSide(1, ft.Colors.GREY_300)
            ),
        )
        btn.on_click = self.on_click
        return btn
