"""Character screen UI component"""
import flet as ft
from datetime import datetime, timedelta
from threading import Thread
from src.auth.eve_sso import EVESSO
from src.database.models import (
    get_character, save_character, get_current_character_id,
    save_setting, create_character_history_table,
    create_character_inventory_table, create_character_profit_table,
    get_profit_by_months, get_profit_by_days,
    get_profit_by_items,
    create_character_wallet_transactions_table,
    get_wallet_transactions,
)
from src.handlers.wallet_handler import pull_wallet_transactions


class CharacterScreen:
    """Character screen with EVE Online account and trading settings"""

    def __init__(self, page: ft.Page, on_back_callback, on_logout_callback=None, on_login_callback=None):
        self.page = page
        self.on_back_callback = on_back_callback
        self.on_logout_callback = on_logout_callback
        self.on_login_callback = on_login_callback
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
            create_character_wallet_transactions_table(character_id)

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

        # Pull Wallet Transactions button
        self.update_wallet_button = ft.ElevatedButton(
            "Pull Wallet Transactions",
            on_click=self.on_update_wallet_transactions,
            visible=bool(self.current_character),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_700,
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
        self.report_type = "months"  # Track current report type

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
                    self.update_wallet_button,
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

        # Transactions tab content
        self.transactions_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
        )
        self.transactions_progress = ft.ProgressRing(visible=False, width=30, height=30)
        self.transactions_content = ft.Container(
            content=ft.Column([
                ft.Container(height=10),
                ft.Row([
                    ft.Text("Last 200 transactions", size=13, color=ft.Colors.GREY_600),
                    ft.Container(width=15),
                    self.transactions_progress,
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=8),
                ft.Container(
                    content=ft.Row([
                        ft.Text("Date", size=12, weight=ft.FontWeight.BOLD, width=155),
                        ft.Text("Item", size=12, weight=ft.FontWeight.BOLD, expand=True),
                        ft.Text("B/S", size=12, weight=ft.FontWeight.BOLD, width=35),
                        ft.Text("Qty", size=12, weight=ft.FontWeight.BOLD, width=65, text_align=ft.TextAlign.RIGHT),
                        ft.Text("Unit Price", size=12, weight=ft.FontWeight.BOLD, width=110, text_align=ft.TextAlign.RIGHT),
                        ft.Text("Total ISK", size=12, weight=ft.FontWeight.BOLD, width=130, text_align=ft.TextAlign.RIGHT),
                    ]),
                    bgcolor=ft.Colors.GREY_200,
                    padding=ft.Padding(8, 5, 8, 5),
                    border_radius=ft.border_radius.only(top_left=5, top_right=5),
                ),
                ft.Container(
                    content=self.transactions_column,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=ft.border_radius.only(bottom_left=5, bottom_right=5),
                    padding=0,
                    expand=True,
                ),
            ], spacing=0, expand=True),
            padding=10,
            expand=True,
            visible=False,
        )

        # Create custom tab buttons (instead of Tabs component)
        self.active_tab = "orders"  # Track active tab

        self.orders_tab_button = ft.Container(
            content=ft.Text("Orders Import", size=14, weight=ft.FontWeight.BOLD),
            padding=ft.Padding(15, 5, 15, 5),
            bgcolor=ft.Colors.BLUE,
            border_radius=ft.border_radius.only(top_left=5, top_right=5),
            on_click=lambda _: self.switch_tab("orders"),
            ink=True
        )

        self.months_tab_button = ft.Container(
            content=ft.Text("Profit by Month", size=14),
            padding=ft.Padding(15, 5, 15, 5),
            bgcolor=ft.Colors.GREY_300,
            border_radius=ft.border_radius.only(top_left=5, top_right=5),
            on_click=lambda _: self.switch_tab("months"),
            ink=True
        )

        self.days_tab_button = ft.Container(
            content=ft.Text("Profit by Days", size=14),
            padding=ft.Padding(15, 5, 15, 5),
            bgcolor=ft.Colors.GREY_300,
            border_radius=ft.border_radius.only(top_left=5, top_right=5),
            on_click=lambda _: self.switch_tab("days"),
            ink=True
        )

        self.items_tab_button = ft.Container(
            content=ft.Text("Profit by Items", size=14),
            padding=ft.Padding(15, 5, 15, 5),
            bgcolor=ft.Colors.GREY_300,
            border_radius=ft.border_radius.only(top_left=5, top_right=5),
            on_click=lambda _: self.switch_tab("items"),
            ink=True
        )

        self.transactions_tab_button = ft.Container(
            content=ft.Text("Transactions", size=14),
            padding=ft.Padding(15, 5, 15, 5),
            bgcolor=ft.Colors.GREY_300,
            border_radius=ft.border_radius.only(top_left=5, top_right=5),
            on_click=lambda _: self.switch_tab("transactions"),
            ink=True
        )

        self.tab_buttons_row = ft.Row([
            self.orders_tab_button,
            self.months_tab_button,
            self.days_tab_button,
            self.items_tab_button,
            self.transactions_tab_button,
        ], spacing=2)

        # Tabs container to hold both tab bar and content
        self.tabs_container = ft.Column([
            self.tab_buttons_row,
            ft.Container(height=2, bgcolor=ft.Colors.BLUE),  # Separator line
            self.orders_import_content,
            self.profit_reports_content,
            self.transactions_content,
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
                self.status_text,
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
            create_character_wallet_transactions_table(character_data['character_id'])

            # Load full character data from DB (preserves broker fees, sales tax)
            full_character = get_character(character_data['character_id'])
            if full_character:
                character_data = full_character

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
            self.update_wallet_button.visible = True
            self.tabs_container.visible = True

            # Update broker fee / sales tax fields from DB
            self.broker_fee_sell_field.value = str(character_data.get('broker_fee_sell', 3.00))
            self.broker_fee_buy_field.value = str(character_data.get('broker_fee_buy', 3.00))
            self.sales_tax_field.value = str(character_data.get('sales_tax', 7.50))

            self.status_text.value = f"Successfully logged in as {character_data.get('character_name')}"
            self.status_text.color = ft.Colors.GREEN

            # Notify main app about login (starts auto-sync, refreshes app bar)
            if self.on_login_callback:
                self.on_login_callback(character_data)
            elif self.on_logout_callback:
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
        self.update_wallet_button.visible = False
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

    # ------------------------------------------------------------------
    # Wallet transactions import
    # ------------------------------------------------------------------

    def on_update_wallet_transactions(self, _):
        """Handle Pull Wallet Transactions button click"""
        if not self.current_character:
            return

        self.update_wallet_button.disabled = True
        self.log_column.controls.clear()
        self.log_container.visible = True
        self.page.update()

        thread = Thread(target=self._run_wallet_transactions_import, daemon=True)
        thread.start()

    def _run_wallet_transactions_import(self):
        """Fetch and process wallet transactions in a background thread."""
        def log(message):
            async def _add():
                self.log_column.controls.append(
                    ft.Text(message, size=12, color=ft.Colors.BLACK, selectable=True)
                )
                self.page.update()
            self.page.run_task(_add)

        try:
            log("Starting wallet transactions import...")
            updated = pull_wallet_transactions(self.current_character, log=log)
            self.current_character = updated
        except Exception as e:
            log(f"ERROR: {str(e)}")
            import traceback
            log(traceback.format_exc())
        finally:
            async def _reenable():
                self.update_wallet_button.disabled = False
                self.page.update()
            self.page.run_task(_reenable)

    def _load_transactions_tab(self):
        """Load and render recent wallet transactions into the Transactions tab"""
        if not self.current_character:
            return

        self.transactions_progress.visible = True
        self.page.update()

        def _fetch():
            character_id = self.current_character['character_id']
            rows = get_wallet_transactions(character_id, limit=200)

            async def _render():
                self.transactions_column.controls.clear()

                for i, row in enumerate(rows):
                    # Format date: "2026-03-13T21:33:00Z" → "2026-03-13 21:33"
                    raw_date = row['date']
                    try:
                        dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                        date_str = dt.strftime('%Y-%m-%d %H:%M')
                    except Exception:
                        date_str = raw_date[:16]

                    is_buy = bool(row['is_buy'])
                    bs_text = ft.Text(
                        "B" if is_buy else "S",
                        size=12,
                        color=ft.Colors.GREEN if is_buy else ft.Colors.RED,
                        weight=ft.FontWeight.BOLD,
                        width=35,
                    )
                    total_isk = row['total_isk']
                    unit_price = row['unit_price']

                    self.transactions_column.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Text(date_str, size=11, width=155),
                                ft.Text(row['type_name'], size=11, expand=True),
                                bs_text,
                                ft.Text(f"{row['quantity']:,}", size=11, width=65, text_align=ft.TextAlign.RIGHT),
                                ft.Text(f"{unit_price:,.2f}", size=11, width=110, text_align=ft.TextAlign.RIGHT),
                                ft.Text(f"{total_isk:,.2f}", size=11, width=130, text_align=ft.TextAlign.RIGHT),
                            ]),
                            bgcolor=ft.Colors.GREY_100 if i % 2 == 0 else ft.Colors.WHITE,
                            padding=ft.Padding(8, 4, 8, 4),
                        )
                    )

                self.transactions_progress.visible = False
                self.page.update()

            self.page.run_task(_render)

        Thread(target=_fetch, daemon=True).start()

    def switch_tab(self, tab_name):
        """Switch between tabs"""
        self.active_tab = tab_name

        # Update all tab button styles
        tabs = {
            "orders": self.orders_tab_button,
            "months": self.months_tab_button,
            "days": self.days_tab_button,
            "items": self.items_tab_button,
            "transactions": self.transactions_tab_button,
        }

        for name, tab in tabs.items():
            if name == tab_name:
                tab.bgcolor = ft.Colors.BLUE
                tab.content.weight = ft.FontWeight.BOLD
            else:
                tab.bgcolor = ft.Colors.GREY_300
                tab.content.weight = ft.FontWeight.NORMAL

        # Show/hide content based on tab
        self.orders_import_content.visible = tab_name == "orders"
        self.profit_reports_content.visible = tab_name in ("months", "days", "items")
        self.transactions_content.visible = tab_name == "transactions"

        if tab_name in ("months", "days", "items"):
            self.report_type = tab_name

            if tab_name == "months":
                self.date_from_picker.visible = False
                self.date_to_picker.visible = False
                self.generate_report_button.visible = False
            else:
                self.date_from_picker.visible = True
                self.date_to_picker.visible = True
                self.generate_report_button.visible = True

            self._load_profit_report()

        elif tab_name == "transactions":
            self._load_transactions_tab()

        self.page.update()

    def navigate_to_tab_with_month(self, tab_name, month_str):
        """Navigate to a tab with date range set to the specified month

        Args:
            tab_name: "days" or "items"
            month_str: Month string in format "YYYY-MM"
        """
        import calendar

        # Parse month string
        year, month = map(int, month_str.split('-'))

        # Get first and last day of month
        first_day = f"{year}-{month:02d}-01"
        last_day_num = calendar.monthrange(year, month)[1]
        last_day = f"{year}-{month:02d}-{last_day_num:02d}"

        # Set date range
        self.date_from_picker.value = first_day
        self.date_to_picker.value = last_day

        # Switch to the tab (this will auto-load the report)
        self.switch_tab(tab_name)

    def navigate_to_day_items(self, day_str):
        """Navigate to Profit by Items for a specific day"""
        self.date_from_picker.value = day_str
        self.date_to_picker.value = day_str
        self.switch_tab("items")

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
            report_type = self.report_type

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
        # Use custom table with Column/Row for proper row-wide hover
        self.report_table.visible = False

        # Create header row
        header_style = ft.TextStyle(weight=ft.FontWeight.BOLD)
        header = ft.Container(
            content=ft.Row([
                ft.Container(ft.Text("Month", style=header_style), width=150),
                ft.Container(ft.Text("Buy Orders", style=header_style), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Sell Orders", style=header_style), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Total Sales", style=header_style), width=120, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Taxes", style=header_style), width=120, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Net Profit", style=header_style), width=120, alignment=ft.Alignment.CENTER_RIGHT),
            ], spacing=10),
            bgcolor=ft.Colors.GREY_200,
            padding=10,
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_400)),
        )

        # Create data rows
        rows = [header]
        for row in data:
            month_str = row['month'] or 'N/A'

            # Create icons for navigation (initially transparent)
            days_icon = ft.IconButton(
                icon=ft.Icons.CALENDAR_VIEW_DAY,
                icon_size=16,
                tooltip="Show by Days",
                opacity=0,
                on_click=lambda _, m=month_str: self.navigate_to_tab_with_month("days", m),
                style=ft.ButtonStyle(padding=0),
            )
            items_icon = ft.IconButton(
                icon=ft.Icons.LIST_ALT,
                icon_size=16,
                tooltip="Show by Items",
                opacity=0,
                on_click=lambda _, m=month_str: self.navigate_to_tab_with_month("items", m),
                style=ft.ButtonStyle(padding=0),
            )

            # Row hover handler
            def on_row_hover(e, d_icon=days_icon, i_icon=items_icon, container=None):
                is_hovered = e.data == True or e.data == "true"
                d_icon.opacity = 1 if is_hovered else 0
                i_icon.opacity = 1 if is_hovered else 0
                if container:
                    container.bgcolor = ft.Colors.BLUE_50 if is_hovered else None
                self.page.update()

            profit_value = float(row['total_profit'] or 0)
            row_content = ft.Row([
                ft.Container(
                    ft.Row([ft.Text(month_str), days_icon, items_icon], spacing=2, tight=True),
                    width=150
                ),
                ft.Container(ft.Text(str(row['buy_orders'] or 0)), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(str(row['sell_orders'] or 0)), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(f"{float(row['total_sales'] or 0):,.2f}"), width=120, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(f"{float(row['total_taxes'] or 0):,.2f}"), width=120, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(
                    f"{profit_value:,.2f}",
                    color=ft.Colors.GREEN if profit_value > 0 else ft.Colors.RED
                ), width=120, alignment=ft.Alignment.CENTER_RIGHT),
            ], spacing=10)

            row_container = ft.Container(
                content=row_content,
                padding=ft.Padding(10, 0, 10, 0),
                border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_300)),
            )
            # Set hover with reference to container
            row_container.on_hover = lambda e, d=days_icon, i=items_icon, c=row_container: on_row_hover(e, d, i, c)

            rows.append(row_container)

        # Replace report container content
        self.report_container.content = ft.Column(rows, spacing=0, scroll=ft.ScrollMode.AUTO)
        self.page.update()

    def _display_days_report(self, data):
        """Display profit by days report"""
        # Use custom table with Column/Row for proper row-wide hover
        self.report_table.visible = False

        # Create header row
        header_style = ft.TextStyle(weight=ft.FontWeight.BOLD)
        header = ft.Container(
            content=ft.Row([
                ft.Container(ft.Text("Date", style=header_style), width=150),
                ft.Container(ft.Text("Buy Orders", style=header_style), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Sell Orders", style=header_style), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Total Sales", style=header_style), width=120, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Taxes", style=header_style), width=120, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Net Profit", style=header_style), width=120, alignment=ft.Alignment.CENTER_RIGHT),
            ], spacing=10),
            bgcolor=ft.Colors.GREY_200,
            padding=10,
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_400)),
        )

        # Create data rows
        rows = [header]
        for row in data:
            day_str = row['day'].strftime("%Y-%m-%d") if hasattr(row['day'], 'strftime') else str(row['day'])

            # Create icon for navigation (initially transparent)
            items_icon = ft.IconButton(
                icon=ft.Icons.LIST_ALT,
                icon_size=16,
                tooltip="Show Items for this day",
                opacity=0,
                on_click=lambda _, d=day_str: self.navigate_to_day_items(d),
                style=ft.ButtonStyle(padding=0),
            )

            # Row hover handler
            def on_row_hover(e, i_icon=items_icon, container=None):
                is_hovered = e.data == True or e.data == "true"
                i_icon.opacity = 1 if is_hovered else 0
                if container:
                    container.bgcolor = ft.Colors.BLUE_50 if is_hovered else None
                self.page.update()

            profit_value = float(row['total_profit'] or 0)
            row_content = ft.Row([
                ft.Container(
                    ft.Row([ft.Text(day_str), items_icon], spacing=2, tight=True),
                    width=150
                ),
                ft.Container(ft.Text(str(row['buy_orders'] or 0)), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(str(row['sell_orders'] or 0)), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(f"{float(row['total_sales'] or 0):,.2f}"), width=120, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(f"{float(row['total_taxes'] or 0):,.2f}"), width=120, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(
                    f"{profit_value:,.2f}",
                    color=ft.Colors.GREEN if profit_value > 0 else ft.Colors.RED
                ), width=120, alignment=ft.Alignment.CENTER_RIGHT),
            ], spacing=10)

            row_container = ft.Container(
                content=row_content,
                padding=ft.Padding(10, 0, 10, 0),
                border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_300)),
            )
            # Set hover with reference to container
            row_container.on_hover = lambda e, i=items_icon, c=row_container: on_row_hover(e, i, c)

            rows.append(row_container)

        # Replace report container content
        self.report_container.content = ft.Column(rows, spacing=0, scroll=ft.ScrollMode.AUTO)
        self.page.update()

    def _display_items_report(self, data):
        """Display profit by items report"""
        # Use custom table style for consistency
        self.report_table.visible = False

        # Create header row
        header_style = ft.TextStyle(weight=ft.FontWeight.BOLD)
        header = ft.Container(
            content=ft.Row([
                ft.Container(ft.Text("Item Name", style=header_style), width=300),
                ft.Container(ft.Text("Type ID", style=header_style), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Buy", style=header_style), width=50, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Sell", style=header_style), width=50, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Qty Sold", style=header_style), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Total Sales", style=header_style), width=150, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Taxes", style=header_style), width=120, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text("Net Profit", style=header_style), width=120, alignment=ft.Alignment.CENTER_RIGHT),
            ], spacing=10),
            bgcolor=ft.Colors.GREY_200,
            padding=10,
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_400)),
        )

        # Create data rows
        rows = [header]
        for row in data:
            profit_value = float(row['total_profit'] or 0)
            row_content = ft.Row([
                ft.Container(ft.Text(row['item_name'] or 'Unknown', max_lines=1, overflow=ft.TextOverflow.ELLIPSIS), width=300),
                ft.Container(ft.Text(str(row['type_id'])), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(str(row['buy_orders'] or 0)), width=50, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(str(row['sell_orders'] or 0)), width=50, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(f"{int(row['quantity_sold'] or 0):,}"), width=80, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(f"{float(row['total_sales'] or 0):,.2f}"), width=150, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(f"{float(row['total_taxes'] or 0):,.2f}"), width=120, alignment=ft.Alignment.CENTER_RIGHT),
                ft.Container(ft.Text(
                    f"{profit_value:,.2f}",
                    color=ft.Colors.GREEN if profit_value > 0 else ft.Colors.RED
                ), width=120, alignment=ft.Alignment.CENTER_RIGHT),
            ], spacing=10)

            row_container = ft.Container(
                content=row_content,
                padding=10,
                border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_300)),
            )
            rows.append(row_container)

        # Replace report container content
        self.report_container.content = ft.Column(rows, spacing=0, scroll=ft.ScrollMode.AUTO)
        self.page.update()

    def build(self):
        """Build and return the UI container"""
        return self.container
