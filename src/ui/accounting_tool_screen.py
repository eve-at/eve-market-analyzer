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
from src.database.models import get_current_character_id, get_character, get_last_buy_price


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
        self.character_id = None

        character_id = get_current_character_id()
        if character_id:
            self.character_id = character_id
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

        # Instruction text (hidden after file detection)
        self.instruction_text = ft.Text(
            "Press 'Export to File' button on the item page in the market",
            size=12,
            color=ft.Colors.BLUE_700,
            italic=True,
            visible=True
        )

        # Subtitle text (shown next to title)
        self.subtitle_text = ft.Text(
            "Track transactions and calculate profits",
            size=14,
            color=ft.Colors.GREY_700
        )

        # Price fields
        self.min_sell_field = ft.TextField(
            label="Min. Sell Price",
            value="",
            read_only=True,
            width=200,
            on_click=self.on_min_sell_field_click
        )
        self.max_buy_field = ft.TextField(
            label="Max. Buy Price",
            value="",
            read_only=True,
            width=200,
            on_click=self.on_max_buy_field_click
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

        # Profit display (spread-based)
        self.profit_percent_text = ft.Text(
            "-%",
            size=32,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN
        )
        self.profit_isk_text = ft.Text(
            "- ISK",
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN
        )

        # Last buy price display
        self.last_buy_price_text = ft.Text(
            "Last Buy Price: -",
            size=14,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.BLUE_600
        )

        # Profit from buy price display
        self.profit_from_buy_percent_text = ft.Text(
            "-%",
            size=24,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN
        )
        self.profit_from_buy_isk_text = ft.Text(
            "- ISK",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN
        )

        # Fees in ISK (with percentages integrated)
        self.broker_fee_sell_isk_text = ft.Text(
            f"Broker Fee (sell) ({self.broker_fee_sell}%): - ISK",
            size=12,
            color=ft.Colors.GREY_600
        )
        self.broker_fee_buy_isk_text = ft.Text(
            f"Broker Fee (buy) ({self.broker_fee_buy}%): - ISK",
            size=12,
            color=ft.Colors.GREY_600
        )
        self.sales_tax_isk_text = ft.Text(
            f"Sales Tax ({self.sales_tax}%): - ISK",
            size=12,
            color=ft.Colors.GREY_600
        )

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                # Title and subtitle on same line
                ft.Row([
                    ft.Text(
                        "Accounting Tool",
                        size=28,
                        weight=ft.FontWeight.BOLD
                    ),
                    ft.Container(width=20),
                    self.subtitle_text
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=5),

                # Instruction text (hidden after file detection)
                self.instruction_text,
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

                # Profit Analysis and Competitors side by side
                ft.Row([
                    # Left column - Profit Analysis
                    ft.Column([
                        ft.Text("Profit Analysis (Spread):", size=14, weight=ft.FontWeight.W_500),
                        self.profit_percent_text,
                        self.profit_isk_text,
                    ], spacing=5, expand=True),

                    # Right column - Competitors
                    ft.Column([
                        ft.Text("Competitors:", size=14, weight=ft.FontWeight.W_500),
                        self.competitors_sell_text,
                        self.competitors_buy_text
                    ], spacing=5, expand=True)
                ], spacing=20),
                ft.Container(height=10),

                # Last buy price and profit from it
                self.last_buy_price_text,
                ft.Text("Profit from Last Buy:", size=14, weight=ft.FontWeight.W_500),
                self.profit_from_buy_percent_text,
                self.profit_from_buy_isk_text,
                ft.Container(height=10),

                # Fees breakdown (with percentages integrated)
                ft.Text("Fees Breakdown:", size=12, weight=ft.FontWeight.W_500),
                ft.Column([
                    self.broker_fee_sell_isk_text,
                    self.broker_fee_buy_isk_text,
                    self.sales_tax_isk_text
                ], spacing=2),
                ft.Container(height=15)

            ], spacing=5, scroll=ft.ScrollMode.AUTO),
            padding=20,
            expand=True
        )

    def on_min_sell_field_click(self, _):
        """Handle click on Min. Sell Price field"""
        if self.current_min_sell is not None:
            next_sell = get_next_sell_tick(self.current_min_sell)
            async def copy_async():
                price_str = f"{next_sell:.2f}"
                await ft.Clipboard().set(price_str)
                print(f"Copied Min. Sell Price to clipboard: {price_str}")
            self.page.run_task(copy_async)

    def on_max_buy_field_click(self, _):
        """Handle click on Max. Buy Price field"""
        if self.current_max_buy is not None:
            next_buy = get_next_buy_tick(self.current_max_buy)
            async def copy_async():
                price_str = f"{next_buy:.2f}"
                await ft.Clipboard().set(price_str)
                print(f"Copied Max. Buy Price to clipboard: {price_str}")
            self.page.run_task(copy_async)

    def on_price_type_changed(self, e):
        """Handle price type radio change"""
        # Capture current value to avoid race condition
        current_price_type = self.price_to_copy_radio.value

        self.update_calculations()

        # Copy new price to clipboard with explicit type
        async def copy_async():
            await self.copy_price_to_clipboard(price_type=current_price_type)
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
        # Capture current price type to avoid race condition
        current_price_type = self.price_to_copy_radio.value

        # Hide instruction text after file is detected
        self.instruction_text.visible = False

        # Update item info
        self.item_name_text.value = self.current_item_name or "Unknown Item"
        self.type_id_text.value = f"Type ID: {self.current_type_id}" if self.current_type_id else "Type ID: -"

        # Calculate next ticks (show without decimals in display, but keep decimals for clipboard)
        if self.current_min_sell is not None:
            next_sell = get_next_sell_tick(self.current_min_sell)
            self.min_sell_field.value = f"{int(next_sell):,}"
        else:
            self.min_sell_field.value = "N/A"

        if self.current_max_buy is not None:
            next_buy = get_next_buy_tick(self.current_max_buy)
            self.max_buy_field.value = f"{int(next_buy):,}"
        else:
            self.max_buy_field.value = "N/A"

        # Update calculations
        self.update_calculations()

        # Copy to clipboard with explicit type
        await self.copy_price_to_clipboard(price_type=current_price_type)

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

        # Update profit display (no decimals, enlarged percentage)
        self.profit_percent_text.value = f"{profit_data['profit_percent']:.0f}%"
        self.profit_isk_text.value = f"{int(profit_data['profit_isk']):,} ISK"

        # Set color based on profit percentage (green if >= 5%, red if < 5%)
        if profit_data['profit_percent'] >= 5:
            self.profit_percent_text.color = ft.Colors.GREEN
            self.profit_isk_text.color = ft.Colors.GREEN
        else:
            self.profit_percent_text.color = ft.Colors.RED
            self.profit_isk_text.color = ft.Colors.RED

        # Update fees (with percentages integrated, no decimals)
        self.broker_fee_sell_isk_text.value = f"Broker Fee (sell) ({self.broker_fee_sell}%): {int(profit_data['broker_fee_sell']):,} ISK"
        self.broker_fee_buy_isk_text.value = f"Broker Fee (buy) ({self.broker_fee_buy}%): {int(profit_data['broker_fee_buy']):,} ISK"
        self.sales_tax_isk_text.value = f"Sales Tax ({self.sales_tax}%): {int(profit_data['sales_tax']):,} ISK"

        # Update competitors count for both sell and buy (green if < 10, red if >= 10)
        sell_competitors = count_competitors(self.current_sell_orders, is_sell_order=True)
        buy_competitors = count_competitors(self.current_buy_orders, is_sell_order=False)

        self.competitors_sell_text.value = f"Competitors (Sell): {sell_competitors}"
        self.competitors_sell_text.color = ft.Colors.GREEN if sell_competitors < 10 else ft.Colors.RED

        self.competitors_buy_text.value = f"Competitors (Buy): {buy_competitors}"
        self.competitors_buy_text.color = ft.Colors.GREEN if buy_competitors < 10 else ft.Colors.RED

        # Get last buy price and calculate profit from it
        if self.character_id and self.current_type_id:
            last_buy_price = get_last_buy_price(self.character_id, self.current_type_id)

            if last_buy_price:
                # Display last buy price
                self.last_buy_price_text.value = f"Last Buy Price: {int(last_buy_price):,} ISK"
                self.last_buy_price_text.visible = True

                # Calculate profit from last buy to current sell
                # Sell price after fees
                sell_after_fees = next_sell * (1 - (self.broker_fee_sell / 100) - (self.sales_tax / 100))
                # Buy price with fees (what we paid)
                buy_with_fees = last_buy_price * (1 + (self.broker_fee_buy / 100))

                # Profit
                profit_isk = sell_after_fees - buy_with_fees
                profit_percent = (profit_isk / buy_with_fees) * 100 if buy_with_fees > 0 else 0

                # Update profit from buy display
                self.profit_from_buy_percent_text.value = f"{profit_percent:.0f}%"
                self.profit_from_buy_isk_text.value = f"{int(profit_isk):,} ISK"
                self.profit_from_buy_percent_text.visible = True
                self.profit_from_buy_isk_text.visible = True

                # Set color based on profit percentage
                if profit_percent >= 5:
                    self.profit_from_buy_percent_text.color = ft.Colors.GREEN
                    self.profit_from_buy_isk_text.color = ft.Colors.GREEN
                else:
                    self.profit_from_buy_percent_text.color = ft.Colors.RED
                    self.profit_from_buy_isk_text.color = ft.Colors.RED
            else:
                # No last buy price found
                self.last_buy_price_text.value = "Last Buy Price: Not found"
                self.last_buy_price_text.visible = True
                self.profit_from_buy_percent_text.visible = False
                self.profit_from_buy_isk_text.visible = False
        else:
            # Not logged in or no type_id
            self.last_buy_price_text.visible = False
            self.profit_from_buy_percent_text.visible = False
            self.profit_from_buy_isk_text.visible = False

        self.page.update()

    async def copy_price_to_clipboard(self, price_type=None):
        """Copy selected price to clipboard

        Args:
            price_type: "sell" or "buy". If None, uses current radio value
        """
        if self.current_min_sell is None or self.current_max_buy is None:
            return

        # Use provided price_type or fall back to radio value
        if price_type is None:
            price_type = self.price_to_copy_radio.value

        price_to_copy = None
        if price_type == "sell":
            price_to_copy = get_next_sell_tick(self.current_min_sell)
        else:
            price_to_copy = get_next_buy_tick(self.current_max_buy)

        if price_to_copy is not None:
            # Format price without thousand separators for game input
            price_str = f"{price_to_copy:.2f}"
            await ft.Clipboard().set(price_str)
            print(f"Copied to clipboard ({price_type}): {price_str}")

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
