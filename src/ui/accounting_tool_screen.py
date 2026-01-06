"""Accounting Tool screen UI component"""
import flet as ft
from pathlib import Path
from watchdog.observers import Observer
from src.handlers.export_file_handler import ExportFileHandler
from src.utils.export_parser import parse_export_file
from src.utils.price_calculator import (
    get_next_sell_tick, get_next_buy_tick,
    calculate_profit, count_competitors
)
from src.database.models import get_current_character_id, get_character


class AccountingToolScreen:
    """Screen for accounting tool"""

    def __init__(self, page: ft.Page, on_back_callback):
        self.page = page
        self.on_back_callback = on_back_callback
        self.observer = None

        # Current data
        self.current_item_name = None
        self.current_type_id = None
        self.current_min_sell = None
        self.current_max_buy = None
        self.current_sell_orders = []
        self.current_buy_orders = []

        # Load character settings
        self.broker_fee_sell = 3.0
        self.broker_fee_buy = 3.0
        self.sales_tax = 7.5

        character_id = get_current_character_id()
        if character_id:
            character = get_character(character_id)
            if character:
                self.broker_fee_sell = float(character.get('broker_fee_sell', 3.0))
                self.broker_fee_buy = float(character.get('broker_fee_buy', 3.0))
                self.sales_tax = float(character.get('sales_tax', 7.5))

        # UI Elements
        # Item info
        self.item_name_text = ft.Text(
            "Waiting for export file...",
            size=20,
            weight=ft.FontWeight.BOLD
        )
        self.type_id_text = ft.Text(
            "Type ID: -",
            size=14,
            color=ft.Colors.GREY_600
        )

        # Price fields
        self.min_sell_field = ft.TextField(
            label="Min. Sell Price",
            value="",
            read_only=True,
            width=200
        )
        self.max_buy_field = ft.TextField(
            label="Max. Buy Price",
            value="",
            read_only=True,
            width=200
        )

        # Radio group for price to copy
        self.price_to_copy_radio = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="sell", label="Sell Price"),
                ft.Radio(value="buy", label="Buy Price")
            ]),
            value="sell",
            on_change=self.on_price_type_changed
        )

        # Settings display
        self.broker_fee_sell_text = ft.Text(
            f"Broker Fee (sell): {self.broker_fee_sell}%",
            size=12,
            color=ft.Colors.GREY_700
        )
        self.broker_fee_buy_text = ft.Text(
            f"Broker Fee (buy): {self.broker_fee_buy}%",
            size=12,
            color=ft.Colors.GREY_700
        )
        self.sales_tax_text = ft.Text(
            f"Sales Tax: {self.sales_tax}%",
            size=12,
            color=ft.Colors.GREY_700
        )

        # Competitors count
        self.competitors_sell_text = ft.Text(
            "Competitors (Sell): -",
            size=14,
            weight=ft.FontWeight.W_500
        )
        self.competitors_buy_text = ft.Text(
            "Competitors (Buy): -",
            size=14,
            weight=ft.FontWeight.W_500
        )

        # Profit display
        self.profit_percent_text = ft.Text(
            "Profit: -%",
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN
        )
        self.profit_isk_text = ft.Text(
            "Profit: - ISK",
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN
        )

        # Fees in ISK
        self.broker_fee_sell_isk_text = ft.Text(
            "Broker Fee (sell): - ISK",
            size=12,
            color=ft.Colors.GREY_600
        )
        self.broker_fee_buy_isk_text = ft.Text(
            "Broker Fee (buy): - ISK",
            size=12,
            color=ft.Colors.GREY_600
        )
        self.sales_tax_isk_text = ft.Text(
            "Sales Tax: - ISK",
            size=12,
            color=ft.Colors.GREY_600
        )

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Accounting Tool",
                    size=28,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(height=10),
                ft.Text(
                    "Track transactions and calculate profits",
                    size=14,
                    color=ft.Colors.GREY_700
                ),
                ft.Container(height=5),
                ft.Text(
                    "Press 'Export to File' button on the item page in the market",
                    size=12,
                    color=ft.Colors.BLUE_700,
                    italic=True
                ),
                ft.Container(height=20),

                # Item info
                self.item_name_text,
                self.type_id_text,
                ft.Container(height=15),

                # Price fields
                ft.Row([
                    self.min_sell_field,
                    self.max_buy_field
                ], spacing=20),
                ft.Container(height=15),

                # Price to copy radio
                ft.Text("Price to Copy:", size=14, weight=ft.FontWeight.W_500),
                self.price_to_copy_radio,
                ft.Container(height=15),

                # Settings
                ft.Text("Trading Settings:", size=14, weight=ft.FontWeight.W_500),
                ft.Column([
                    self.broker_fee_sell_text,
                    self.broker_fee_buy_text,
                    self.sales_tax_text
                ], spacing=2),
                ft.Container(height=15),

                # Competitors
                ft.Text("Competitors:", size=14, weight=ft.FontWeight.W_500),
                ft.Column([
                    self.competitors_sell_text,
                    self.competitors_buy_text
                ], spacing=2),
                ft.Container(height=15),

                # Profit
                ft.Text("Profit Analysis:", size=14, weight=ft.FontWeight.W_500),
                self.profit_percent_text,
                self.profit_isk_text,
                ft.Container(height=10),

                # Fees breakdown
                ft.Text("Fees Breakdown:", size=12, weight=ft.FontWeight.W_500),
                ft.Column([
                    self.broker_fee_sell_isk_text,
                    self.broker_fee_buy_isk_text,
                    self.sales_tax_isk_text
                ], spacing=2)

            ], spacing=5, scroll=ft.ScrollMode.AUTO),
            padding=20,
            expand=True
        )

    def on_price_type_changed(self, e):
        """Handle price type radio change"""
        self.update_calculations()
        # Copy new price to clipboard
        async def copy_async():
            await self.copy_price_to_clipboard()
        self.page.run_task(copy_async)

    def on_export_file_created(self, file_path, region_name, item_name):
        """Callback when new export file is detected"""
        print(f"Processing export file: {file_path}")

        try:
            # Parse the file
            data = parse_export_file(file_path)

            # Update current data
            self.current_item_name = item_name
            self.current_type_id = data['type_id']
            self.current_min_sell = data['min_sell_price']
            self.current_max_buy = data['max_buy_price']
            self.current_sell_orders = data['sell_orders']
            self.current_buy_orders = data['buy_orders']

            # Update UI
            async def update_ui():
                await self.update_ui_with_data()
                self.page.update()

            self.page.run_task(update_ui)

        except Exception as e:
            print(f"Error processing export file: {e}")

    async def update_ui_with_data(self):
        """Update UI elements with current data"""
        # Update item info
        self.item_name_text.value = self.current_item_name or "Unknown Item"
        self.type_id_text.value = f"Type ID: {self.current_type_id}" if self.current_type_id else "Type ID: -"

        # Calculate next ticks
        if self.current_min_sell is not None:
            next_sell = get_next_sell_tick(self.current_min_sell)
            self.min_sell_field.value = f"{next_sell:,.2f}"
        else:
            self.min_sell_field.value = "N/A"

        if self.current_max_buy is not None:
            next_buy = get_next_buy_tick(self.current_max_buy)
            self.max_buy_field.value = f"{next_buy:,.2f}"
        else:
            self.max_buy_field.value = "N/A"

        # Update calculations
        self.update_calculations()

        # Copy to clipboard
        await self.copy_price_to_clipboard()

    def update_calculations(self):
        """Update all calculated fields"""
        if self.current_min_sell is None or self.current_max_buy is None:
            return

        # Get next tick prices
        next_sell = get_next_sell_tick(self.current_min_sell)
        next_buy = get_next_buy_tick(self.current_max_buy)

        # Calculate profit
        profit_data = calculate_profit(
            next_sell,
            next_buy,
            self.broker_fee_sell,
            self.broker_fee_buy,
            self.sales_tax
        )

        # Update profit display
        self.profit_percent_text.value = f"Profit: {profit_data['profit_percent']:,.2f}%"
        self.profit_isk_text.value = f"Profit: {profit_data['profit_isk']:,.2f} ISK"

        # Set color based on profit
        if profit_data['profit_isk'] > 0:
            self.profit_percent_text.color = ft.Colors.GREEN
            self.profit_isk_text.color = ft.Colors.GREEN
        elif profit_data['profit_isk'] < 0:
            self.profit_percent_text.color = ft.Colors.RED
            self.profit_isk_text.color = ft.Colors.RED
        else:
            self.profit_percent_text.color = ft.Colors.GREY
            self.profit_isk_text.color = ft.Colors.GREY

        # Update fees
        self.broker_fee_sell_isk_text.value = f"Broker Fee (sell): {profit_data['broker_fee_sell']:,.2f} ISK"
        self.broker_fee_buy_isk_text.value = f"Broker Fee (buy): {profit_data['broker_fee_buy']:,.2f} ISK"
        self.sales_tax_isk_text.value = f"Sales Tax: {profit_data['sales_tax']:,.2f} ISK"

        # Update competitors count for both sell and buy
        sell_competitors = count_competitors(self.current_sell_orders, is_sell_order=True)
        buy_competitors = count_competitors(self.current_buy_orders, is_sell_order=False)
        self.competitors_sell_text.value = f"Competitors (Sell): {sell_competitors}"
        self.competitors_buy_text.value = f"Competitors (Buy): {buy_competitors}"

        self.page.update()

    async def copy_price_to_clipboard(self):
        """Copy selected price to clipboard"""
        if self.current_min_sell is None or self.current_max_buy is None:
            return

        price_to_copy = None
        if self.price_to_copy_radio.value == "sell":
            price_to_copy = get_next_sell_tick(self.current_min_sell)
        else:
            price_to_copy = get_next_buy_tick(self.current_max_buy)

        if price_to_copy is not None:
            # Format price without thousand separators for game input
            price_str = f"{price_to_copy:.2f}"
            await ft.Clipboard().set(price_str)
            print(f"Copied to clipboard: {price_str}")

    def start_file_monitoring(self):
        """Start monitoring market logs directory"""
        # Get market logs directory from settings
        from src.database import get_setting
        from settings import MARKETLOGS_DIR

        marketlogs_dir = get_setting('marketlogs_dir', MARKETLOGS_DIR)
        marketlogs_path = Path(marketlogs_dir)

        if not marketlogs_path.exists():
            print(f"Market logs directory does not exist: {marketlogs_path}")
            print("Please check your Market Logs Directory setting")
            return

        event_handler = ExportFileHandler(self.on_export_file_created)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(marketlogs_path), recursive=False)
        self.observer.start()
        print(f"Started monitoring market logs directory: {marketlogs_path}")

    def stop_file_monitoring(self):
        """Stop monitoring market logs directory"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("Market logs directory monitoring stopped")

    def build(self):
        """Build and return the UI container"""
        return self.container
