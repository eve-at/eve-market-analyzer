"""Trade opportunities screen UI component"""
import flet as ft
from .autocomplete_field import AutoCompleteField


class TradeOpportunitiesScreen:
    """Screen for finding trade opportunities"""

    def __init__(self, page: ft.Page, regions_data, on_back_callback):
        self.page = page
        self.regions_data = regions_data
        self.on_back_callback = on_back_callback

        # Region selection field
        self.region_field = AutoCompleteField(
            label="Region",
            hint_text="Start typing region name...",
            default_value="",
            data_dict=self.regions_data,
            on_select_callback=lambda name, id: print(f"Selected region: {name} (ID: {id})"),
            on_validation_change=None
        )

        # Buttons
        self.update_orders_button = ft.ElevatedButton(
            "Update Orders",
            on_click=self.on_update_orders,
            disabled=True,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(20, 10, 20, 10)
            )
        )

        self.find_opportunities_button = ft.ElevatedButton(
            "Find Opportunities",
            on_click=self.on_find_opportunities,
            disabled=True,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN,
                color=ft.Colors.WHITE,
                padding=ft.Padding(20, 10, 20, 10)
            )
        )

        self.back_button = ft.TextButton(
            "← Back to Menu",
            on_click=lambda e: self.on_back_callback()
        )

        # Status text
        self.status_text = ft.Text("", size=14)

        # Results placeholder
        self.results_container = ft.Container(
            content=ft.Text(
                "Select a region and click 'Find Opportunities' to search for profitable trades",
                size=14,
                color=ft.Colors.GREY_600,
                text_align=ft.TextAlign.CENTER
            ),
            padding=20,
            expand=True
        )

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Row([
                    self.back_button
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=10),
                ft.Text(
                    "Trade Opportunities Finder",
                    size=28,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(height=10),
                ft.Text(
                    "Find profitable trading opportunities in EVE Online",
                    size=14,
                    color=ft.Colors.GREY_700
                ),
                ft.Container(height=20),
                ft.Row([
                    self.region_field.container,
                ], spacing=20),
                ft.Container(height=15),
                ft.Row([
                    self.update_orders_button,
                    self.find_opportunities_button
                ], spacing=15),
                ft.Container(height=10),
                self.status_text,
                ft.Divider(),
                self.results_container
            ], spacing=5),
            padding=20,
            expand=True
        )

    def on_update_orders(self, e):
        """Handle update orders button click"""
        # TODO: Implement update orders functionality
        self.status_text.value = "Update orders functionality - coming soon"
        self.status_text.color = ft.Colors.ORANGE
        self.page.update()

    def on_find_opportunities(self, e):
        """Handle find opportunities button click"""
        # TODO: Implement find opportunities functionality
        self.status_text.value = "Find opportunities functionality - coming soon"
        self.status_text.color = ft.Colors.ORANGE
        self.page.update()

    def build(self):
        """Build and return the UI container"""
        return self.container
