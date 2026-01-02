"""Trade opportunities screen UI component"""
import flet as ft
from .autocomplete_field import AutoCompleteField
from src.handlers.trade_opportunities_handler import check_orders_count, update_orders
import threading


class TradeOpportunitiesScreen:
    """Screen for finding trade opportunities"""

    def __init__(self, page: ft.Page, regions_data, on_back_callback):
        self.page = page
        self.regions_data = regions_data
        self.on_back_callback = on_back_callback
        self.selected_region_id = None
        self.selected_region_name = None

        # Region selection field
        self.region_field = AutoCompleteField(
            label="Region",
            hint_text="Start typing region name...",
            default_value="",
            data_dict=self.regions_data,
            on_select_callback=self.on_region_selected,
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
        self.status_text = ft.Text("Select a region to begin", size=14, color=ft.Colors.GREY_600)

        # Log container for update progress
        self.log_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            auto_scroll=True,  # Auto-scroll to bottom
            spacing=2,
        )

        self.log_container = ft.Container(
            content=self.log_column,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            padding=10,
            bgcolor=ft.Colors.BLACK,
            height=350,
            width=700,
            visible=False
        )

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
                    self.update_orders_button
                ], spacing=20, vertical_alignment=ft.MainAxisAlignment.START),
                self.status_text,
                ft.Container(height=15),
                ft.Row([
                    self.find_opportunities_button
                ], spacing=15),
                ft.Container(height=10),
                ft.Container(height=5),
                self.log_container,
                ft.Divider(),
                self.results_container
            ], spacing=5),
            padding=20,
            expand=True
        )

    def on_region_selected(self, name, region_id):
        """Handle region selection"""
        self.selected_region_id = region_id
        self.selected_region_name = name

        # Enable Update Orders button
        self.update_orders_button.disabled = False
        self.find_opportunities_button.disabled = True

        # Check if orders table exists and has data
        self.check_and_display_orders_status()

        self.page.update()

    def check_and_display_orders_status(self):
        """Check orders table and display status"""
        if not self.selected_region_id:
            return

        count = check_orders_count(self.selected_region_id)

        if count == -1 or count == 0:
            self.status_text.value = "Click Update Orders to fetch the orders"
            self.status_text.color = ft.Colors.GREY_600
            self.find_opportunities_button.disabled = True
        else:
            self.status_text.value = f"Fetched orders: {count}"
            self.status_text.color = ft.Colors.GREEN
            self.find_opportunities_button.disabled = False

        self.page.update()

    def log_progress(self, message):
        """Append message to progress log"""
        async def add_log():
            self.log_column.controls.append(
                ft.Text(
                    message,
                    size=11,
                    color=ft.Colors.GREEN_300,
                    font_family="Consolas",
                    selectable=True
                )
            )
            self.page.update()

        self.page.run_task(add_log)

    def on_update_orders(self, e):
        """Handle update orders button click"""
        if not self.selected_region_id:
            return

        # Show progress log
        self.log_column.controls.clear()
        self.log_container.visible = True
        self.results_container.visible = False

        # Disable buttons during update
        self.update_orders_button.disabled = True
        self.find_opportunities_button.disabled = True

        self.status_text.value = f"Updating orders for {self.selected_region_name}..."
        self.status_text.color = ft.Colors.BLUE

        self.page.update()

        # Run update in separate thread to avoid blocking UI
        def update_thread():
            success = update_orders(self.selected_region_id, callback=self.log_progress)

            # Update UI after completion
            async def update_after_import():
                self.update_orders_button.disabled = False

                if success:
                    self.check_and_display_orders_status()
                else:
                    self.status_text.value = "Failed to update orders"
                    self.status_text.color = ft.Colors.RED

                self.page.update()

            self.page.run_task(update_after_import)

        thread = threading.Thread(target=update_thread, daemon=True)
        thread.start()

    def on_find_opportunities(self, e):
        """Handle find opportunities button click"""
        # Hide progress log and show results container
        self.log_container.visible = False
        self.results_container.visible = True

        # TODO: Implement find opportunities functionality
        self.status_text.value = "Find opportunities functionality - coming soon"
        self.status_text.color = ft.Colors.ORANGE
        self.page.update()

    def build(self):
        """Build and return the UI container"""
        return self.container
