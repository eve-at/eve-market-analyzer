"""Trade opportunities screen UI component"""
import flet as ft
from .autocomplete_field import AutoCompleteField
from src.handlers.trade_opportunities_handler import check_orders_count, update_orders, find_opportunities
import threading
import importlib


class TradeOpportunitiesScreen:
    """Screen for finding trade opportunities"""

    def __init__(self, page: ft.Page, regions_data, on_back_callback):
        self.page = page
        self.regions_data = regions_data
        self.on_back_callback = on_back_callback
        self.selected_region_id = None
        self.selected_region_name = None

        # Store opportunities data for sorting
        self.opportunities_data = []
        self.sort_column_index = 0
        self.sort_ascending = True

        # Load settings
        import settings
        importlib.reload(settings)
        self.settings = settings

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

        # Filter input fields
        self.min_sell_price_field = ft.TextField(
            label="Min. Sell Price",
            value=str(self.settings.MIN_SELL_PRICE),
            width=180,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.max_buy_price_field = ft.TextField(
            label="Max. Buy Price",
            value=str(self.settings.MAX_BUY_PRICE),
            width=180,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.min_profit_percent_field = ft.TextField(
            label="Min. Profit, %",
            value=str(self.settings.MIN_PROFIT_PERCENT),
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.max_profit_percent_field = ft.TextField(
            label="Max. Profit, %",
            value=str(self.settings.MAX_PROFIT_PERCENT),
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.min_daily_quantity_field = ft.TextField(
            label="Min. Daily Quantity",
            value=str(self.settings.MIN_DAILY_QUANTITY),
            width=180,
            keyboard_type=ft.KeyboardType.NUMBER
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
                ft.Text("Filter Parameters", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(height=5),
                ft.Row([
                    self.min_sell_price_field,
                    self.max_buy_price_field,
                    self.min_profit_percent_field,
                    self.max_profit_percent_field,
                    self.min_daily_quantity_field
                ], spacing=15, wrap=True),
                ft.Container(height=10),
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
        if not self.selected_region_id:
            self.status_text.value = "Please select a region first"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return

        # Validate input fields
        try:
            min_sell_price = int(self.min_sell_price_field.value)
            max_buy_price = int(self.max_buy_price_field.value)
            min_profit_percent = int(self.min_profit_percent_field.value)
            max_profit_percent = int(self.max_profit_percent_field.value)
            min_daily_quantity = int(self.min_daily_quantity_field.value)
        except ValueError:
            self.status_text.value = "Please enter valid numbers in all fields"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return

        # Show progress log
        self.log_column.controls.clear()
        self.log_container.visible = True
        self.results_container.visible = False

        # Disable buttons during search
        self.find_opportunities_button.disabled = True
        self.update_orders_button.disabled = True

        self.status_text.value = f"Searching for opportunities in {self.selected_region_name}..."
        self.status_text.color = ft.Colors.BLUE

        self.page.update()

        # Run search in separate thread to avoid blocking UI
        def search_thread():
            opportunities = find_opportunities(
                self.selected_region_id,
                min_sell_price,
                max_buy_price,
                min_profit_percent,
                max_profit_percent,
                min_daily_quantity,
                callback=self.log_progress
            )

            # Update UI after completion
            async def update_after_search():
                self.find_opportunities_button.disabled = False
                self.update_orders_button.disabled = False

                if opportunities is not None and len(opportunities) > 0:
                    self.status_text.value = f"Found {len(opportunities)} opportunities"
                    self.status_text.color = ft.Colors.GREEN
                    self.display_opportunities(opportunities)
                elif opportunities is not None:
                    self.status_text.value = "No opportunities found with current filters"
                    self.status_text.color = ft.Colors.ORANGE
                    self.log_container.visible = True
                    self.results_container.visible = False
                else:
                    self.status_text.value = "Failed to find opportunities"
                    self.status_text.color = ft.Colors.RED

                self.page.update()

            self.page.run_task(update_after_search)

        thread = threading.Thread(target=search_thread, daemon=True)
        thread.start()

    def sort_opportunities(self, column_index):
        """Sort opportunities by column"""
        # Toggle sort direction if clicking same column
        if self.sort_column_index == column_index:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column_index = column_index
            self.sort_ascending = True

        # Define sort keys for each column
        sort_keys = [
            lambda x: x['type_id'],
            lambda x: x['typeName'].lower(),
            lambda x: x['buy_orders_count'],
            lambda x: x['sell_orders_count'],
            lambda x: float(x['min_sell_price']),
            lambda x: float(x['max_buy_price']),
            lambda x: float(x['profit']),
        ]

        # Sort the data
        self.opportunities_data.sort(key=sort_keys[column_index], reverse=not self.sort_ascending)

        # Redisplay the table
        self.display_opportunities(self.opportunities_data)

    def display_opportunities(self, opportunities):
        """Display opportunities in a sortable DataTable"""
        # Store opportunities data for sorting
        self.opportunities_data = opportunities

        # Create DataTable columns with sort callbacks
        columns = [
            ft.DataColumn(
                ft.Text("Type ID", weight=ft.FontWeight.BOLD),
                on_sort=lambda _: self.sort_opportunities(0)
            ),
            ft.DataColumn(
                ft.Text("Item Name", weight=ft.FontWeight.BOLD),
                on_sort=lambda _: self.sort_opportunities(1)
            ),
            ft.DataColumn(
                ft.Text("Buy Orders", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(2)
            ),
            ft.DataColumn(
                ft.Text("Sell Orders", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(3)
            ),
            ft.DataColumn(
                ft.Text("Min Sell Price", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(4)
            ),
            ft.DataColumn(
                ft.Text("Max Buy Price", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(5)
            ),
            ft.DataColumn(
                ft.Text("Profit %", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(6)
            ),
        ]

        # Create DataTable rows
        rows = []
        for opp in opportunities:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(opp['type_id']))),
                        ft.DataCell(ft.Text(opp['typeName'])),
                        ft.DataCell(ft.Text(str(opp['buy_orders_count']))),
                        ft.DataCell(ft.Text(str(opp['sell_orders_count']))),
                        ft.DataCell(ft.Text(f"{float(opp['min_sell_price']):,.2f}")),
                        ft.DataCell(ft.Text(f"{float(opp['max_buy_price']):,.2f}")),
                        ft.DataCell(ft.Text(f"{float(opp['profit']):.2f}%")),
                    ]
                )
            )

        # Create DataTable
        data_table = ft.DataTable(
            columns=columns,
            rows=rows,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            vertical_lines=ft.BorderSide(1, ft.Colors.GREY_300),
            horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_300),
            heading_row_color=ft.Colors.GREY_200,
            heading_row_height=50,
            data_row_min_height=40,
            sort_column_index=self.sort_column_index,
            sort_ascending=self.sort_ascending,
        )

        # Update results container with scrollable table
        self.results_container.content = ft.Column([
            ft.Text(
                f"Trade Opportunities ({len(opportunities)} items)",
                size=18,
                weight=ft.FontWeight.BOLD
            ),
            ft.Container(height=10),
            ft.Container(
                content=data_table,
                border=ft.border.all(1, ft.Colors.GREY_400),
                border_radius=5,
                padding=10,
            )
        ], scroll=ft.ScrollMode.AUTO)

        # Hide log and show results
        self.log_container.visible = False
        self.results_container.visible = True

    def build(self):
        """Build and return the UI container"""
        return self.container
