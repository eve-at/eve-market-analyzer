"""Main menu UI component"""
import flet as ft


class MainMenu:
    """Main application menu"""

    def __init__(self, page: ft.Page, on_menu_select):
        self.page = page
        self.on_menu_select = on_menu_select

        # Menu items
        menu_items = [
            {
                "title": "Update Static Data",
                "icon": ft.Icons.CLOUD_DOWNLOAD,
                "description": "Download and import latest EVE Online data",
                "key": "update_data"
            },
            {
                "title": "Market History",
                "icon": ft.Icons.SHOW_CHART,
                "description": "View historical prices for items and regions",
                "key": "market_history"
            },
            {
                "title": "Trade Opportunities",
                "icon": ft.Icons.TRENDING_UP,
                "description": "Find profitable trading opportunities",
                "key": "trade_opportunities"
            },
            {
                "title": "Settings",
                "icon": ft.Icons.SETTINGS,
                "description": "Configure application settings",
                "key": "settings"
            }
        ]

        # Create menu cards
        menu_cards = []
        for item in menu_items:
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Icon(item["icon"], size=48, color=ft.Colors.BLUE),
                        ft.Container(height=10),
                        ft.Text(
                            item["title"],
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Container(height=5),
                        ft.Text(
                            item["description"],
                            size=12,
                            color=ft.Colors.GREY_700,
                            text_align=ft.TextAlign.CENTER
                        )
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=30,
                    width=300,
                    height=200,
                    ink=True,
                    on_click=lambda e, key=item["key"]: self.on_menu_select(key)
                ),
                elevation=2
            )
            menu_cards.append(card)

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Container(height=30),
                ft.Text(
                    "EVE Online Market Helper",
                    size=32,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Container(height=10),
                ft.Text(
                    "Select an option to continue",
                    size=14,
                    color=ft.Colors.GREY_600,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Container(height=30),
                ft.Row([
                    menu_cards[0],
                    menu_cards[1]
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                ft.Container(height=20),
                ft.Row([
                    menu_cards[2],
                    menu_cards[3]
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
            expand=True
        )

    def build(self):
        """Build and return the UI container"""
        return self.container
