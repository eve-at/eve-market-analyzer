"""Trade opportunities screen UI component"""
import flet as ft
from .autocomplete_field import AutoCompleteField
from src.handlers.trade_opportunities_handler import check_orders_count, update_orders, find_opportunities, export_opportunities_to_csv
from src.database import load_top_market_groups
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

        # Store opportunities data for sorting and pagination
        self.opportunities_data = []
        self.sort_column_index = 6  # Default sort by profit (index 6)
        self.sort_ascending = False  # Descending order
        self.current_page = 0
        self.rows_per_page = 50

        # Load settings
        import settings
        importlib.reload(settings)
        self.settings = settings

        # Load top market groups
        self.market_groups = load_top_market_groups()
        self.market_group_checkboxes = {}
        self.selected_market_group_ids = set()  # Track selected IDs

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
            height=45,
            text_size=12,
            content_padding=8,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True
        )

        self.max_buy_price_field = ft.TextField(
            label="Max. Buy Price",
            value=str(self.settings.MAX_BUY_PRICE),
            height=45,
            text_size=12,
            content_padding=8,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True
        )

        self.min_profit_percent_field = ft.TextField(
            label="Min. Profit, %",
            value=str(self.settings.MIN_PROFIT_PERCENT),
            height=45,
            text_size=12,
            content_padding=8,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True
        )

        self.max_profit_percent_field = ft.TextField(
            label="Max. Profit, %",
            value=str(self.settings.MAX_PROFIT_PERCENT),
            height=45,
            text_size=12,
            content_padding=8,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True
        )

        self.min_daily_quantity_field = ft.TextField(
            label="Min. Daily Quantity",
            value=str(self.settings.MIN_DAILY_QUANTITY),
            height=45,
            text_size=12,
            content_padding=8,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True
        )

        self.max_competitors_field = ft.TextField(
            label="Max. Competitors",
            value="5",
            height=45,
            text_size=12,
            content_padding=8,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True
        )

        # Create checkboxes for market groups
        market_group_checkboxes_controls = []
        for group in self.market_groups:
            group_id = group['marketGroupID']
            checkbox = ft.Checkbox(
                label=group['marketGroupName'],
                value=False,
                data=group_id,
                on_change=lambda e, gid=group_id: self.on_market_group_changed(e, gid)
            )
            self.market_group_checkboxes[group_id] = checkbox
            market_group_checkboxes_controls.append(checkbox)

        # Container for market groups checkboxes
        self.market_groups_container = ft.Container(
            content=ft.Column([
                ft.Text("Market Groups (optional)", size=12, weight=ft.FontWeight.BOLD),
                ft.Container(height=2),
                ft.Container(
                    content=ft.Column(
                        market_group_checkboxes_controls,
                        spacing=0,
                        scroll=ft.ScrollMode.AUTO
                    ),
                    height=200,
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    border_radius=5,
                    padding=5
                )
            ], spacing=0),
            visible=len(self.market_groups) > 0,
            padding=5
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

        self.export_button = ft.ElevatedButton(
            "Export to CSV",
            on_click=self.on_export_csv,
            visible=False,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.ORANGE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(20, 10, 20, 10)
            )
        )

        self.back_button = ft.TextButton(
            "← Back to Menu",
            on_click=lambda e: self.on_back_callback()
        )

        # Status text
        self.status_text = ft.Text("Select a region to begin", size=12, color=ft.Colors.GREY_600)

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
            padding=8,
            bgcolor=ft.Colors.BLACK,
            height=250,
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

        # Accordion for filters
        self.filter_accordion = ft.ExpansionTile(
            title=ft.Text("Filters & Settings", size=14, weight=ft.FontWeight.BOLD),
            subtitle=ft.Text("Click to expand/collapse", size=11),
            expanded=True,
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            self.region_field.container,
                            self.update_orders_button
                        ], spacing=10, vertical_alignment=ft.MainAxisAlignment.START),
                        ft.Container(height=3),
                        self.status_text,
                        ft.Container(height=5),
                        ft.Row([
                            # Left column - Filter Parameters
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("Filter Parameters", size=12, weight=ft.FontWeight.BOLD),
                                    ft.Container(height=2),
                                    ft.Column([
                                        ft.Row([
                                            self.min_sell_price_field,
                                            self.max_buy_price_field
                                        ], spacing=8),
                                        ft.Row([
                                            self.min_profit_percent_field,
                                            self.max_profit_percent_field
                                        ], spacing=8),
                                        ft.Row([
                                            self.min_daily_quantity_field,
                                            self.max_competitors_field
                                        ], spacing=8)
                                    ], spacing=5)
                                ], spacing=0),
                                expand=1
                            ),
                            # Right column - Market Groups
                            ft.Container(
                                content=self.market_groups_container,
                                expand=1
                            )
                        ], spacing=15, vertical_alignment=ft.CrossAxisAlignment.START),
                        ft.Container(height=5),
                        ft.Row([
                            self.find_opportunities_button,
                            self.export_button
                        ], spacing=10),
                    ], spacing=0),
                    padding=ft.padding.only(left=8, right=8, bottom=8, top=3)
                )
            ]
        )

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Row([
                    self.back_button
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=2),
                ft.Text(
                    "Trade Opportunities Finder",
                    size=18,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(height=1),
                ft.Text(
                    "Find profitable trading opportunities in EVE Online",
                    size=11,
                    color=ft.Colors.GREY_700
                ),
                ft.Container(height=3),
                self.filter_accordion,
                ft.Container(height=3),
                self.log_container,
                ft.Divider(),
                self.results_container
            ], spacing=0),
            padding=5,
            expand=True
        )

    def on_market_group_changed(self, e, group_id):
        """Handle market group checkbox change"""
        if e.control.value:
            self.selected_market_group_ids.add(group_id)
        else:
            self.selected_market_group_ids.discard(group_id)
        print(f"DEBUG: Market group {group_id} changed to {e.control.value}")
        print(f"DEBUG: Selected IDs: {self.selected_market_group_ids}")

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
            max_competitors = int(self.max_competitors_field.value) if self.max_competitors_field.value else None
        except ValueError:
            self.status_text.value = "Please enter valid numbers in all fields"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return

        # Get selected market group IDs from tracked set
        selected_market_groups = list(self.selected_market_group_ids)

        # Debug: print selected groups
        print(f"DEBUG: Selected market groups: {selected_market_groups}")
        print(f"DEBUG: Max competitors: {max_competitors}")

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
                max_competitors=max_competitors,
                selected_market_groups=selected_market_groups,
                callback=self.log_progress
            )

            # Update UI after completion
            async def update_after_search():
                self.find_opportunities_button.disabled = False
                self.update_orders_button.disabled = False

                if opportunities is not None and len(opportunities) > 0:
                    self.status_text.value = f"Found {len(opportunities)} opportunities"
                    self.status_text.color = ft.Colors.GREEN
                    self.export_button.visible = True
                    self.display_opportunities(opportunities, min_daily_quantity)
                elif opportunities is not None:
                    self.status_text.value = "No opportunities found with current filters"
                    self.status_text.color = ft.Colors.ORANGE
                    self.export_button.visible = False
                    self.log_container.visible = True
                    self.results_container.visible = False
                else:
                    self.status_text.value = "Failed to find opportunities"
                    self.status_text.color = ft.Colors.RED
                    self.export_button.visible = False

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
        # Order: Type ID, Type Name, Profit %, Daily Qty, Competitors, Buy Price, Sell Price, Buy Orders, Sell Orders, Daily Orders
        sort_keys = [
            lambda x: x['type_id'],
            lambda x: x['typeName'].lower(),
            lambda x: float(x['profit']),
            lambda x: x['daily_volume'] if x['daily_volume'] is not None else 0,
            lambda x: x['competitors'] if x['competitors'] is not None else 0,
            lambda x: float(x['max_buy_price']),
            lambda x: float(x['min_sell_price']),
            lambda x: x['buy_orders_count'],
            lambda x: x['sell_orders_count'],
            lambda x: x['daily_orders'] if x['daily_orders'] is not None else 0,
        ]

        # Sort the data
        self.opportunities_data.sort(key=sort_keys[column_index], reverse=not self.sort_ascending)

        # Reset to first page and redisplay
        self.current_page = 0
        self.update_table_display()

    def change_page(self, delta):
        """Change current page"""
        new_page = self.current_page + delta
        total_pages = (len(self.opportunities_data) - 1) // self.rows_per_page + 1

        if 0 <= new_page < total_pages:
            self.current_page = new_page
            self.update_table_display()

    def update_table_display(self):
        """Update table display with current page"""
        if not self.opportunities_data:
            return

        # Calculate pagination
        start_idx = self.current_page * self.rows_per_page
        end_idx = min(start_idx + self.rows_per_page, len(self.opportunities_data))
        page_data = self.opportunities_data[start_idx:end_idx]
        total_pages = (len(self.opportunities_data) - 1) // self.rows_per_page + 1

        # Create DataTable columns with sort callbacks
        # Order: Type ID, Type Name, Profit %, Daily Qty, Competitors, Buy Price, Sell Price, Buy Orders, Sell Orders, Daily Orders
        columns = [
            ft.DataColumn(
                ft.Text("Type ID", weight=ft.FontWeight.BOLD),
                on_sort=lambda _: self.sort_opportunities(0)
            ),
            ft.DataColumn(
                ft.Text("Type Name", weight=ft.FontWeight.BOLD),
                on_sort=lambda _: self.sort_opportunities(1)
            ),
            ft.DataColumn(
                ft.Text("Profit %", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(2)
            ),
            ft.DataColumn(
                ft.Text("Daily Qty", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(3)
            ),
            ft.DataColumn(
                ft.Text("Competitors", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(4)
            ),
            ft.DataColumn(
                ft.Text("Buy Price", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(5)
            ),
            ft.DataColumn(
                ft.Text("Sell Price", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(6)
            ),
            ft.DataColumn(
                ft.Text("Buy Orders", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(7)
            ),
            ft.DataColumn(
                ft.Text("Sell Orders", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(8)
            ),
            ft.DataColumn(
                ft.Text("Daily Orders", weight=ft.FontWeight.BOLD),
                numeric=True,
                on_sort=lambda _: self.sort_opportunities(9)
            ),
        ]

        # Create DataTable rows
        rows = []
        for opp in page_data:
            type_id_text = ft.Text(
                str(opp['type_id']),
                color=ft.Colors.BLUE
            )
            item_name_text = ft.Text(
                opp['typeName'],
                color=ft.Colors.BLUE
            )

            # Order: Type ID, Type Name, Profit %, Daily Qty, Competitors, Buy Price, Sell Price, Buy Orders, Sell Orders, Daily Orders
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            type_id_text,
                            on_tap=lambda _, tid=opp['type_id']: self.page.run_task(self.copy_to_clipboard, str(tid), "Type ID")
                        ),
                        ft.DataCell(
                            item_name_text,
                            on_tap=lambda _, name=opp['typeName']: self.page.run_task(self.copy_to_clipboard, name, "Item name")
                        ),
                        ft.DataCell(ft.Text(f"{int(opp['profit'])}%")),
                        ft.DataCell(ft.Text(f"{opp['daily_volume']:,}" if opp['daily_volume'] is not None else "0")),
                        ft.DataCell(ft.Text(str(opp['competitors']) if opp['competitors'] is not None else "0")),
                        ft.DataCell(ft.Text(f"{float(opp['max_buy_price']):,.0f}")),
                        ft.DataCell(ft.Text(f"{float(opp['min_sell_price']):,.0f}")),
                        ft.DataCell(ft.Text(str(opp['buy_orders_count']))),
                        ft.DataCell(ft.Text(str(opp['sell_orders_count']))),
                        ft.DataCell(ft.Text(str(opp['daily_orders']) if opp['daily_orders'] is not None else "0")),
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
            heading_row_height=25,
            data_row_min_height=30,
            data_row_max_height=30,
            sort_column_index=self.sort_column_index,
            sort_ascending=self.sort_ascending,
        )

        # Pagination controls
        prev_button = ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            on_click=lambda _: self.change_page(-1),
            disabled=self.current_page == 0
        )

        next_button = ft.IconButton(
            icon=ft.Icons.ARROW_FORWARD,
            on_click=lambda _: self.change_page(1),
            disabled=self.current_page >= total_pages - 1
        )

        page_info = ft.Text(
            f"Page {self.current_page + 1} of {total_pages} | Showing {start_idx + 1}-{end_idx} of {len(self.opportunities_data)}",
            size=12
        )

        # Update results container with scrollable table
        self.results_container.content = ft.Column([
            ft.Text(
                f"Trade Opportunities ({len(self.opportunities_data)} items)",
                size=16,
                weight=ft.FontWeight.BOLD
            ),
            ft.Container(height=10),
            ft.Container(
                content=ft.Row([data_table], scroll=ft.ScrollMode.AUTO, expand=True),
                padding=10,
                expand=True,
            ),
            ft.Container(height=10),
            ft.Row([
                prev_button,
                page_info,
                next_button
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=20)
        ], scroll=ft.ScrollMode.AUTO, expand=True)

        # Hide log and show results
        self.log_container.visible = False
        self.results_container.visible = True
        self.page.update()

    def on_export_csv(self, _):
        """Handle export to CSV button click"""
        if not self.selected_region_id:
            return

        # Show progress log
        self.log_column.controls.clear()
        self.log_container.visible = True
        self.results_container.visible = False

        # Disable buttons during export
        self.export_button.disabled = True
        self.find_opportunities_button.disabled = True
        self.update_orders_button.disabled = True

        self.status_text.value = "Exporting to CSV..."
        self.status_text.color = ft.Colors.BLUE

        self.page.update()

        # Run export in separate thread
        def export_thread():
            filepath = export_opportunities_to_csv(
                self.selected_region_id,
                callback=self.log_progress
            )

            # Update UI after completion
            async def update_after_export():
                self.export_button.disabled = False
                self.find_opportunities_button.disabled = False
                self.update_orders_button.disabled = False

                if filepath:
                    self.status_text.value = f"Successfully exported to CSV"
                    self.status_text.color = ft.Colors.GREEN
                    # Show the results table again
                    self.log_container.visible = False
                    self.results_container.visible = True
                else:
                    self.status_text.value = "Failed to export to CSV"
                    self.status_text.color = ft.Colors.RED

                self.page.update()

            self.page.run_task(update_after_export)

        thread = threading.Thread(target=export_thread, daemon=True)
        thread.start()

    async def copy_to_clipboard(self, text, label):
        """Copy text to clipboard and show notification"""
        # Set clipboard value using Flet's async Clipboard API
        await ft.Clipboard().set(text)

        # Show snackbar notification
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(f"{label} copied: {text}"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()

    def display_opportunities(self, opportunities, min_daily_quantity):
        """Display opportunities in a sortable DataTable"""
        # Filter opportunities by daily_volume >= min_daily_quantity
        filtered_opportunities = [
            opp for opp in opportunities
            if opp.get('daily_volume') is not None and opp['daily_volume'] >= min_daily_quantity
        ]

        # Store filtered opportunities data
        self.opportunities_data = filtered_opportunities

        # Sort by default column (profit) in descending order
        sort_keys = [
            lambda x: x['type_id'],
            lambda x: x['typeName'].lower(),
            lambda x: x['buy_orders_count'],
            lambda x: x['sell_orders_count'],
            lambda x: float(x['min_sell_price']),
            lambda x: float(x['max_buy_price']),
            lambda x: float(x['profit']),
        ]
        self.opportunities_data.sort(key=sort_keys[self.sort_column_index], reverse=not self.sort_ascending)

        # Reset to first page
        self.current_page = 0

        # Display the table
        self.update_table_display()

    def build(self):
        """Build and return the UI container"""
        return self.container
