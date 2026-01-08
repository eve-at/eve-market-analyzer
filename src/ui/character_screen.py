"""Character screen UI component"""
import flet as ft
from datetime import datetime, timedelta
from threading import Thread
from src.auth.eve_sso import EVESSO
from src.auth.esi_api import ESIAPI
from src.database.models import (
    get_character, save_character, get_current_character_id,
    save_setting, create_character_history_table, save_character_order_history,
    create_character_inventory_table, create_character_profit_table,
    process_character_orders, get_profit_by_months, get_profit_by_days,
    get_profit_by_items
)


class CharacterScreen:
    """Character screen with EVE Online account and trading settings"""

    def __init__(self, page: ft.Page, on_back_callback, on_logout_callback=None):
        self.page = page
        self.on_back_callback = on_back_callback
        self.on_logout_callback = on_logout_callback
        self.current_character = None
        self.eve_sso = EVESSO()

        # Load current character if logged in
        character_id = get_current_character_id()
        if character_id:
            self.current_character = get_character(character_id)
            # Create tables for this character if they don't exist
            create_character_history_table(character_id)
            create_character_inventory_table(character_id)
            create_character_profit_table(character_id)

        # Load settings from database or use defaults
        broker_fee_sell = "3.00"
        broker_fee_buy = "3.00"
        sales_tax = "7.50"

        if self.current_character:
            broker_fee_sell = str(self.current_character.get('broker_fee_sell', 3.00))
            broker_fee_buy = str(self.current_character.get('broker_fee_buy', 3.00))
            sales_tax = str(self.current_character.get('sales_tax', 7.50))

        # Character info display
        self.character_info_row = ft.Row(visible=False, spacing=15)

        # Set default avatar or character avatar
        avatar_src = "static/img/default_avatar.svg"
        if self.current_character:
            avatar_src = self.current_character.get('character_portrait_url', avatar_src)

        self.character_avatar = ft.Image(
            src=avatar_src,
            width=64,
            height=64,
            border_radius=32,
            fit=ft.BoxFit.COVER
        )
        self.character_name_text = ft.Text(size=16, weight=ft.FontWeight.W_500)
        self.character_id_text = ft.Text(size=12, color=ft.Colors.GREY_600)

        # Logout button
        self.logout_button = ft.TextButton(
            "Logout",
            on_click=self.on_logout,
            visible=bool(self.current_character),
            margin=ft.Margin(left=-12)
        )

        if self.current_character:
            self.character_name_text.value = self.current_character.get('character_name')
            self.character_id_text.value = f"ID: {self.current_character.get('character_id')}"
            self.character_info_row.visible = True
            self.character_info_row.controls = [
                self.character_avatar,
                ft.Column([
                    self.character_name_text,
                    self.character_id_text,
                    self.logout_button
                ], spacing=2)
            ]

        # EVE Online login button
        self.eve_login_button = ft.Container(
            content=ft.Image(
                src="static/img/ssologin.png",
                width=270,
                fit=ft.BoxFit.CONTAIN
            ),
            on_click=self.on_eve_login,
            visible=not bool(self.current_character),
            ink=True,
            border_radius=5
        )

        # Trading settings fields
        self.broker_fee_sell_field = ft.TextField(
            label="Broker Fee (sell), %",
            value=broker_fee_sell,
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.broker_fee_buy_field = ft.TextField(
            label="Broker Fee (buy), %",
            value=broker_fee_buy,
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        self.sales_tax_field = ft.TextField(
            label="Sales Tax, %",
            value=sales_tax,
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        # Save button
        self.save_button = ft.ElevatedButton(
            "Save",
            on_click=self.on_save,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(30, 10, 30, 10)
            )
        )

        # Status text
        self.status_text = ft.Text("", size=14)

        # Update Historical Orders button
        self.update_orders_button = ft.ElevatedButton(
            "Update Historical Orders",
            on_click=self.on_update_orders,
            visible=bool(self.current_character),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN,
                color=ft.Colors.WHITE,
                padding=ft.Padding(20, 10, 20, 10)
            )
        )

        # Log container for import progress
        self.log_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            auto_scroll=True,
            height=300
        )

        self.log_container = ft.Container(
            content=self.log_column,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            padding=10,
            visible=False
        )

        # Profit Reports UI Elements
        self.report_type_radio = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="months", label="Profit by Months"),
                ft.Radio(value="days", label="Profit by Days"),
                ft.Radio(value="items", label="Profit by Items")
            ]),
            value="months",
            on_change=self.on_report_type_change
        )

        # Date range pickers (hidden by default for months view)
        date_to = datetime.now()
        date_from = date_to - timedelta(days=30)

        self.date_from_picker = ft.TextField(
            label="From Date",
            value=date_from.strftime("%Y-%m-%d"),
            width=150,
            visible=False,
            read_only=True,
            on_click=lambda e: self._show_date_picker(e, "from")
        )

        self.date_to_picker = ft.TextField(
            label="To Date",
            value=date_to.strftime("%Y-%m-%d"),
            width=150,
            visible=False,
            read_only=True,
            on_click=lambda e: self._show_date_picker(e, "to")
        )

        self.generate_report_button = ft.ElevatedButton(
            "Generate Report",
            on_click=self.on_generate_report,
            visible=False,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE
            )
        )

        # Progress indicator for reports
        self.report_progress = ft.ProgressRing(visible=False, width=30, height=30)

        # Report table - initialize with placeholder column
        self.report_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("No Data", weight=ft.FontWeight.BOLD))
            ],
            rows=[],
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_300),
            heading_row_color=ft.Colors.GREY_200,
        )

        self.report_container = ft.Container(
            content=ft.Column([
                ft.Text("Select a report type and generate to view data", size=14, color=ft.Colors.GREY_600),
                ft.Container(height=10),
                self.report_table
            ], scroll=ft.ScrollMode.AUTO),
            expand=True
        )

        # EVE Online Account column
        eve_account_column = ft.Column([
            ft.Text(
                "EVE Online Account",
                size=18,
                weight=ft.FontWeight.W_500
            ),
            ft.Container(height=10),
            self.character_info_row,
            ft.Row([
                self.eve_login_button
            ], spacing=10)
        ], spacing=5)

        # Trading Settings column
        trading_settings_column = ft.Column([
            ft.Text(
                "Trading Settings",
                size=18,
                weight=ft.FontWeight.W_500
            ),
            ft.Row([
                self.broker_fee_sell_field,
                self.broker_fee_buy_field,
                self.sales_tax_field
            ]),
            ft.Row([
                self.save_button
            ], alignment=ft.MainAxisAlignment.START)
        ], spacing=5)

        # Create tab contents
        self.orders_import_content = ft.Container(
            content=ft.Column([
                ft.Container(height=10),
                ft.Row([
                    self.update_orders_button
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=10),
                self.log_container
            ], spacing=5, scroll=ft.ScrollMode.AUTO),
            padding=10,
            expand=True,
            visible=True
        )

        self.profit_reports_content = ft.Container(
            content=ft.Column([
                ft.Container(height=10),
                self.report_type_radio,
                ft.Container(height=10),
                ft.Row([
                    self.date_from_picker,
                    ft.Container(width=10),
                    self.date_to_picker,
                    ft.Container(width=10),
                    self.generate_report_button,
                    ft.Container(width=10),
                    self.report_progress
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=10),
                self.report_container
            ], spacing=5, expand=True, scroll=ft.ScrollMode.AUTO),
            padding=10,
            expand=True,
            visible=False
        )

        # Create custom tab buttons (instead of Tabs component)
        self.active_tab = "orders"  # Track active tab

        self.orders_tab_button = ft.Container(
            content=ft.Text("Orders Import", size=14, weight=ft.FontWeight.BOLD),
            padding=ft.Padding(15, 10, 15, 10),
            bgcolor=ft.Colors.BLUE,
            border_radius=ft.border_radius.only(top_left=5, top_right=5),
            on_click=lambda _: self.switch_tab("orders"),
            ink=True
        )

        self.reports_tab_button = ft.Container(
            content=ft.Text("Profit Reports", size=14),
            padding=ft.Padding(15, 10, 15, 10),
            bgcolor=ft.Colors.GREY_300,
            border_radius=ft.border_radius.only(top_left=5, top_right=5),
            on_click=lambda _: self.switch_tab("reports"),
            ink=True
        )

        self.tab_buttons_row = ft.Row([
            self.orders_tab_button,
            self.reports_tab_button
        ], spacing=2)

        # Tabs container to hold both tab bar and content
        self.tabs_container = ft.Column([
            self.tab_buttons_row,
            ft.Container(height=2, bgcolor=ft.Colors.BLUE),  # Separator line
            self.orders_import_content,
            self.profit_reports_content
        ], spacing=0, expand=True, visible=bool(self.current_character))

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                # EVE Account and Trading Settings side by side
                ft.Row([
                    eve_account_column,
                    ft.Container(width=50),
                    trading_settings_column
                ], spacing=0, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Container(height=10),
                self.status_text,
                ft.Container(height=20),
                # Tabs for Orders and Reports
                self.tabs_container
            ], spacing=5, scroll=ft.ScrollMode.AUTO, expand=True),
            padding=20,
            expand=True
        )

    def on_eve_login(self, e):
        """Handle EVE Online login button click"""
        self.status_text.value = "Opening browser for EVE Online authentication..."
        self.status_text.color = ft.Colors.BLUE
        self.page.update()

        # Start SSO login flow
        self.eve_sso.start_login(callback_func=self.on_login_complete)

    def on_login_complete(self, character_data):
        """Called when EVE SSO login is complete"""
        if character_data:
            # Save character to database
            save_character(character_data)

            # Save as current character
            save_setting('current_character_id', str(character_data['character_id']))

            # Create tables for this character if they don't exist
            create_character_history_table(character_data['character_id'])
            create_character_inventory_table(character_data['character_id'])
            create_character_profit_table(character_data['character_id'])

            # Update UI
            self.current_character = character_data
            self.character_avatar.src = character_data.get('character_portrait_url')
            self.character_name_text.value = character_data.get('character_name')
            self.character_id_text.value = f"ID: {character_data.get('character_id')}"
            self.character_info_row.visible = True
            self.character_info_row.controls = [
                self.character_avatar,
                ft.Column([
                    self.character_name_text,
                    self.character_id_text,
                    self.logout_button
                ], spacing=2)
            ]
            self.eve_login_button.visible = False
            self.logout_button.visible = True
            self.update_orders_button.visible = True
            self.tabs_container.visible = True

            self.status_text.value = f"Successfully logged in as {character_data.get('character_name')}"
            self.status_text.color = ft.Colors.GREEN

            # Call logout callback to refresh app bar
            if self.on_logout_callback:
                self.on_logout_callback()

            self.page.update()

    def on_logout(self, e):
        """Handle logout button click"""
        # Clear current character
        save_setting('current_character_id', '')

        self.current_character = None
        self.character_info_row.visible = False
        self.eve_login_button.visible = True
        self.logout_button.visible = False
        self.update_orders_button.visible = False
        self.tabs_container.visible = False
        self.log_container.visible = False

        # Reset avatar to default
        self.character_avatar.src = "static/img/default_avatar.svg"

        # Reset broker fee and sales tax to defaults
        self.broker_fee_sell_field.value = "3.00"
        self.broker_fee_buy_field.value = "3.00"
        self.sales_tax_field.value = "7.50"

        self.status_text.value = "Logged out successfully"
        self.status_text.color = ft.Colors.ORANGE

        # Call logout callback to refresh app bar
        if self.on_logout_callback:
            self.on_logout_callback()

        self.page.update()

    def on_save(self, e):
        """Handle save button click"""
        try:
            # Save trading settings to character if logged in
            if self.current_character:
                broker_fee_sell = float(self.broker_fee_sell_field.value)
                broker_fee_buy = float(self.broker_fee_buy_field.value)
                sales_tax = float(self.sales_tax_field.value)

                save_character({
                    'character_id': self.current_character['character_id'],
                    'character_name': self.current_character['character_name'],
                    'broker_fee_sell': broker_fee_sell,
                    'broker_fee_buy': broker_fee_buy,
                    'sales_tax': sales_tax
                })

                self.status_text.value = "Settings saved successfully!"
                self.status_text.color = ft.Colors.GREEN
            else:
                self.status_text.value = "Please log in first"
                self.status_text.color = ft.Colors.ORANGE

        except ValueError as e:
            self.status_text.value = "Error: Invalid number format"
            self.status_text.color = ft.Colors.RED
        except Exception as e:
            self.status_text.value = f"Error saving settings: {str(e)}"
            self.status_text.color = ft.Colors.RED

        self.page.update()

    def on_update_orders(self, e):
        """Handle Update Historical Orders button click"""
        if not self.current_character:
            self.status_text.value = "Please log in first"
            self.status_text.color = ft.Colors.ORANGE
            self.page.update()
            return

        # Disable button during update
        self.update_orders_button.disabled = True
        self.log_column.controls.clear()
        self.log_container.visible = True
        self.page.update()

        # Run import in background thread
        thread = Thread(target=self._run_orders_import, daemon=True)
        thread.start()

    def _run_orders_import(self):
        """Run orders import in background thread"""
        def log_callback(message):
            """Callback to display log messages"""
            async def add_log():
                self.log_column.controls.append(
                    ft.Text(
                        message,
                        size=12,
                        color=ft.Colors.BLACK,
                        selectable=True
                    )
                )
                self.page.update()

            self.page.run_task(add_log)

        try:
            character_id = self.current_character['character_id']
            access_token = self.current_character.get('access_token')
            refresh_token = self.current_character.get('refresh_token')
            token_expiry = self.current_character.get('token_expiry')

            log_callback(f"Starting orders import for character ID {character_id}...")

            # Check if token needs refresh
            esi_api = ESIAPI()
            if not access_token or not token_expiry or datetime.now() >= token_expiry:
                log_callback("Access token expired or missing, refreshing...")

                if not refresh_token:
                    log_callback("ERROR: No refresh token available. Please log in again.")
                    async def update_ui():
                        self.update_orders_button.disabled = False
                        self.page.update()
                    self.page.run_task(update_ui)
                    return

                token_data = esi_api.refresh_access_token(refresh_token)
                if not token_data:
                    log_callback("ERROR: Failed to refresh access token. Please log in again.")
                    async def update_ui():
                        self.update_orders_button.disabled = False
                        self.page.update()
                    self.page.run_task(update_ui)
                    return

                access_token = token_data['access_token']

                # Save updated token to database
                save_character({
                    'character_id': character_id,
                    'character_name': self.current_character['character_name'],
                    'access_token': access_token,
                    'token_expiry': token_data['token_expiry']
                })

                log_callback("Access token refreshed successfully")

            # Fetch orders with pagination
            log_callback("Fetching orders history from ESI API...")
            page = 1
            total_orders = 0
            total_inserted = 0
            total_skipped = 0

            while True:
                log_callback(f"Fetching page {page}...")

                orders, has_more = esi_api.get_character_orders_history(
                    character_id,
                    access_token,
                    page
                )

                if orders is None:
                    log_callback(f"ERROR: Failed to fetch page {page}")
                    break

                if not orders:
                    log_callback("No more orders to fetch")
                    break

                log_callback(f"Received {len(orders)} orders from page {page}")
                total_orders += len(orders)

                # Save orders to database
                log_callback(f"Saving orders to database...")
                inserted, skipped = save_character_order_history(character_id, orders)
                total_inserted += inserted
                total_skipped += skipped

                log_callback(f"Page {page}: Inserted {inserted} new orders, skipped {skipped} duplicates")

                if not has_more:
                    log_callback("All pages fetched")
                    break

                page += 1

            log_callback("=" * 50)
            log_callback(f"Import completed!")
            log_callback(f"Total orders fetched: {total_orders}")
            log_callback(f"New orders inserted: {total_inserted}")
            log_callback(f"Duplicates skipped: {total_skipped}")

            # Process orders to calculate profits
            if total_inserted > 0:
                log_callback("")
                log_callback("Processing orders to calculate profits...")

                broker_fee_buy = float(self.current_character.get('broker_fee_buy', 3.00))
                broker_fee_sell = float(self.current_character.get('broker_fee_sell', 3.00))
                sales_tax = float(self.current_character.get('sales_tax', 7.50))

                stats = process_character_orders(
                    character_id,
                    broker_fee_buy,
                    broker_fee_sell,
                    sales_tax
                )

                if stats:
                    log_callback("=" * 50)
                    log_callback("Profit calculation completed!")
                    log_callback(f"Buy orders processed: {stats['buy_orders_processed']}")
                    log_callback(f"Items added to inventory: {stats['items_added_to_inventory']}")
                    log_callback(f"Sell orders processed: {stats['sell_orders_processed']}")
                    log_callback(f"Items sold: {stats['items_sold']}")
                    if stats['items_sold_without_purchase'] > 0:
                        log_callback(f"Items sold without purchase record: {stats['items_sold_without_purchase']} (profit = 0)")
                else:
                    log_callback("ERROR: Failed to process orders")

        except Exception as e:
            log_callback(f"ERROR: {str(e)}")
            import traceback
            log_callback(traceback.format_exc())

        finally:
            # Re-enable button
            async def update_ui():
                self.update_orders_button.disabled = False
                self.page.update()
            self.page.run_task(update_ui)

    def switch_tab(self, tab_name):
        """Switch between tabs"""
        self.active_tab = tab_name

        if tab_name == "orders":
            # Orders Import tab
            self.orders_import_content.visible = True
            self.profit_reports_content.visible = False
            # Update button styles
            self.orders_tab_button.bgcolor = ft.Colors.BLUE
            self.orders_tab_button.content.weight = ft.FontWeight.BOLD
            self.reports_tab_button.bgcolor = ft.Colors.GREY_300
            self.reports_tab_button.content.weight = ft.FontWeight.NORMAL
        elif tab_name == "reports":
            # Profit Reports tab
            self.orders_import_content.visible = False
            self.profit_reports_content.visible = True
            # Update button styles
            self.orders_tab_button.bgcolor = ft.Colors.GREY_300
            self.orders_tab_button.content.weight = ft.FontWeight.NORMAL
            self.reports_tab_button.bgcolor = ft.Colors.BLUE
            self.reports_tab_button.content.weight = ft.FontWeight.BOLD
            # Auto-generate months report if on reports tab
            if self.report_type_radio.value == "months":
                self._load_profit_report()

        self.page.update()

    def on_report_type_change(self, e):
        """Handle report type radio button change"""
        report_type = self.report_type_radio.value

        # Show/hide date pickers and generate button based on report type
        if report_type == "months":
            self.date_from_picker.visible = False
            self.date_to_picker.visible = False
            self.generate_report_button.visible = False
            # Auto-generate report for months
            self._load_profit_report()
        else:
            self.date_from_picker.visible = True
            self.date_to_picker.visible = True
            self.generate_report_button.visible = True

        self.page.update()

    def _show_date_picker(self, e, picker_type):
        """Show date picker dialog"""
        def on_date_change(_):
            # Update value when date changes
            pass

        def on_date_dismiss(_):
            # Update the text field when picker is dismissed
            selected_date = date_picker.value
            if selected_date:
                if picker_type == "from":
                    self.date_from_picker.value = selected_date.strftime("%Y-%m-%d")
                else:
                    self.date_to_picker.value = selected_date.strftime("%Y-%m-%d")
                self.page.update()

        current_value = self.date_from_picker.value if picker_type == "from" else self.date_to_picker.value
        initial_date = datetime.strptime(current_value, "%Y-%m-%d") if current_value else datetime.now()

        date_picker = ft.DatePicker(
            on_change=on_date_change,
            on_dismiss=on_date_dismiss,
            first_date=datetime(2020, 1, 1),
            last_date=datetime.now(),
            value=initial_date
        )

        self.page.overlay.append(date_picker)
        self.page.update()
        date_picker.open = True
        self.page.update()

    def on_generate_report(self, e):
        """Handle generate report button click"""
        self._load_profit_report()

    def _load_profit_report(self):
        """Load profit report based on selected type"""
        if not self.current_character:
            return

        # Show progress indicator
        self.report_progress.visible = True
        self.report_table.rows = []
        self.page.update()

        # Run report generation in background
        thread = Thread(target=self._run_report_generation, daemon=True)
        thread.start()

    def _run_report_generation(self):
        """Generate report in background thread"""
        try:
            character_id = self.current_character['character_id']
            report_type = self.report_type_radio.value

            if report_type == "months":
                data = get_profit_by_months(character_id)
                async def update_ui():
                    self._display_months_report(data)
                self.page.run_task(update_ui)

            elif report_type == "days":
                date_from = self.date_from_picker.value
                date_to = self.date_to_picker.value
                data = get_profit_by_days(character_id, date_from, date_to)
                async def update_ui():
                    self._display_days_report(data)
                self.page.run_task(update_ui)

            elif report_type == "items":
                date_from = self.date_from_picker.value
                date_to = self.date_to_picker.value
                data = get_profit_by_items(character_id, date_from, date_to)
                async def update_ui():
                    self._display_items_report(data)
                self.page.run_task(update_ui)

        except Exception as e:
            print(f"Error generating report: {e}")
            import traceback
            traceback.print_exc()

        finally:
            async def hide_progress():
                self.report_progress.visible = False
                self.page.update()
            self.page.run_task(hide_progress)

    def _display_months_report(self, data):
        """Display profit by months report"""
        self.report_table.columns = [
            ft.DataColumn(ft.Text("Month", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Buy Orders", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Sell Orders", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Total Sales", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Taxes", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Net Profit", weight=ft.FontWeight.BOLD)),
        ]

        self.report_table.rows = []
        for row in data:
            self.report_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(row['month'] or 'N/A')),
                        ft.DataCell(ft.Text(str(row['buy_orders'] or 0))),
                        ft.DataCell(ft.Text(str(row['sell_orders'] or 0))),
                        ft.DataCell(ft.Text(f"{float(row['total_sales'] or 0):,.2f}")),
                        ft.DataCell(ft.Text(f"{float(row['total_taxes'] or 0):,.2f}")),
                        ft.DataCell(ft.Text(
                            f"{float(row['total_profit'] or 0):,.2f}",
                            color=ft.Colors.GREEN if float(row['total_profit'] or 0) > 0 else ft.Colors.RED
                        )),
                    ]
                )
            )

        self.page.update()

    def _display_days_report(self, data):
        """Display profit by days report"""
        self.report_table.columns = [
            ft.DataColumn(ft.Text("Date", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Buy Orders", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Sell Orders", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Total Sales", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Taxes", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Net Profit", weight=ft.FontWeight.BOLD)),
        ]

        self.report_table.rows = []
        for row in data:
            day_str = row['day'].strftime("%Y-%m-%d") if hasattr(row['day'], 'strftime') else str(row['day'])
            self.report_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(day_str)),
                        ft.DataCell(ft.Text(str(row['buy_orders'] or 0))),
                        ft.DataCell(ft.Text(str(row['sell_orders'] or 0))),
                        ft.DataCell(ft.Text(f"{float(row['total_sales'] or 0):,.2f}")),
                        ft.DataCell(ft.Text(f"{float(row['total_taxes'] or 0):,.2f}")),
                        ft.DataCell(ft.Text(
                            f"{float(row['total_profit'] or 0):,.2f}",
                            color=ft.Colors.GREEN if float(row['total_profit'] or 0) > 0 else ft.Colors.RED
                        )),
                    ]
                )
            )

        self.page.update()

    def _display_items_report(self, data):
        """Display profit by items report"""
        self.report_table.columns = [
            ft.DataColumn(ft.Text("Item Name", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Type ID", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Buy Orders", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Sell Orders", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Quantity Sold", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Total Sales", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Taxes", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Net Profit", weight=ft.FontWeight.BOLD)),
        ]

        self.report_table.rows = []
        for row in data:
            self.report_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(row['item_name'] or 'Unknown', max_lines=1)),
                        ft.DataCell(ft.Text(str(row['type_id']))),
                        ft.DataCell(ft.Text(str(row['buy_orders'] or 0))),
                        ft.DataCell(ft.Text(str(row['sell_orders'] or 0))),
                        ft.DataCell(ft.Text(f"{int(row['quantity_sold'] or 0):,}")),
                        ft.DataCell(ft.Text(f"{float(row['total_sales'] or 0):,.2f}")),
                        ft.DataCell(ft.Text(f"{float(row['total_taxes'] or 0):,.2f}")),
                        ft.DataCell(ft.Text(
                            f"{float(row['total_profit'] or 0):,.2f}",
                            color=ft.Colors.GREEN if float(row['total_profit'] or 0) > 0 else ft.Colors.RED
                        )),
                    ]
                )
            )

        self.page.update()

    def build(self):
        """Build and return the UI container"""
        return self.container
