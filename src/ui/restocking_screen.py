"""Restocking List screen - items previously traded but not in current active orders"""
import flet as ft
import threading
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from src.database.models import get_current_character_id, get_character, get_setting, save_character
from src.auth.esi_api import ESIAPI
from src.handlers.restocking_handler import (
    load_active_order_type_ids,
    get_restocking_items,
    calculate_profit,
)
from src.handlers.export_file_handler import ExportFileHandler
from src.utils.export_parser import parse_export_file


class RestockingScreen:
    """Screen that shows profitable items not currently in the character's active orders"""

    def __init__(self, page: ft.Page, regions_data, on_back_callback):
        self.page = page
        self.regions_data = regions_data
        self.on_back_callback = on_back_callback

        self.current_character = None
        self.items_data = []
        self.sort_column_index = 2    # default: qty_sold
        self.sort_ascending = False
        self.current_page = 0
        self.rows_per_page = 50
        self.clicked_rows = set()

        # Per-item price freshness {type_id: datetime}
        self.price_updated_at = {}

        # File monitoring
        self.observer = None

        # Load character
        character_id = get_current_character_id()
        if character_id:
            self.current_character = get_character(character_id)

        # ── Status text ───────────────────────────────────────────────────
        self.status_text = ft.Text(
            "Loading active orders...", size=12, color=ft.Colors.BLUE
        )

        # ── Hint (shown after table loads) ───────────────────────────────
        self.hint_container = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, size=13, color=ft.Colors.BLUE_300),
                ft.Text(
                    "Click an item name to open its market window in EVE, "
                    "then use 'Export to File' - the price will update here automatically. "
                    "Requires login.",
                    size=11,
                    color=ft.Colors.GREY_600,
                    expand=True,
                ),
            ], spacing=6),
            visible=False,
            padding=ft.padding.only(top=3, bottom=1),
        )

        # ── Loader ───────────────────────────────────────────────────────
        self.loader_container = ft.Container(
            content=ft.Column([
                ft.ProgressRing(width=40, height=40),
                ft.Container(height=10),
                ft.Text(
                    "Refreshing active character orders...",
                    size=13,
                    color=ft.Colors.GREY_600,
                ),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=40,
            visible=True,
        )

        # ── Results table ─────────────────────────────────────────────────
        self.results_container = ft.Container(
            content=ft.Text("Loading…", size=14, color=ft.Colors.GREY_600),
            padding=ft.padding.only(top=0, left=0, right=4, bottom=4),
            expand=True,
            visible=False,
        )

        # ── Main container ────────────────────────────────────────────────
        self.container = ft.Container(
            content=ft.Column([
                ft.Text("Restocking List", size=18, weight=ft.FontWeight.BOLD),
                ft.Container(height=1),
                ft.Text(
                    "Items you previously traded profitably that are not in your current active orders",
                    size=11,
                    color=ft.Colors.GREY_700,
                ),
                ft.Container(height=8),
                self.status_text,
                self.hint_container,
                ft.Divider(),
                self.loader_container,
                self.results_container,
            ], spacing=0),
            padding=ft.padding.only(top=5, left=0, right=5, bottom=5),
            expand=True,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Initial auto-load
    # ─────────────────────────────────────────────────────────────────────

    def start_auto_load(self):
        """Called by main.py after the page is rendered."""
        thread = threading.Thread(target=self._auto_load_thread, daemon=True)
        thread.start()

    def _auto_load_thread(self):
        if not self.current_character:
            async def _no_char():
                self.loader_container.visible = False
                self.status_text.value = "Please log in first (EVE Online Account)"
                self.status_text.color = ft.Colors.ORANGE
                self.results_container.content = ft.Text(
                    "No character logged in. Go to EVE Online Account to log in.",
                    size=14, color=ft.Colors.ORANGE, text_align=ft.TextAlign.CENTER,
                )
                self.results_container.visible = True
                self.page.update()
            self.page.run_task(_no_char)
            return

        active_type_ids, updated_char = load_active_order_type_ids(self.current_character)
        if updated_char:
            self.current_character = updated_char

        if active_type_ids is None:
            async def _err():
                self.loader_container.visible = False
                self.status_text.value = "Failed to fetch active orders. Check your login."
                self.status_text.color = ft.Colors.RED
                self.results_container.content = ft.Text(
                    "Could not load active orders from ESI. Please check your login.",
                    size=14, color=ft.Colors.RED, text_align=ft.TextAlign.CENTER,
                )
                self.results_container.visible = True
                self.page.update()
            self.page.run_task(_err)
            return

        items = get_restocking_items(self.current_character['character_id'], active_type_ids)

        async def _done(items=items):
            self.loader_container.visible = False

            if not items:
                self.status_text.value = "No items found to restock."
                self.status_text.color = ft.Colors.ORANGE
                self.results_container.content = ft.Text(
                    "All previously traded items are already in your active orders, "
                    "or no profit history found.",
                    size=14, color=ft.Colors.GREY_600, text_align=ft.TextAlign.CENTER,
                )
                self.results_container.visible = True
            else:
                self.items_data = [
                    dict(item, buy_price=None, sell_price=None,
                         taxes=None, profit_isk=None, profit_pct=None)
                    for item in items
                ]

                self.sort_column_index = 2
                self.sort_ascending = False
                self.current_page = 0
                self._sort_data()
                self._render_table()

                self.status_text.value = f"Found {len(items)} items to restock."
                self.status_text.color = ft.Colors.GREEN
                self.hint_container.visible = True

            self.page.update()

        self.page.run_task(_done)

    # ─────────────────────────────────────────────────────────────────────
    # File monitoring (market export files)
    # ─────────────────────────────────────────────────────────────────────

    def start_file_monitoring(self):
        """Start watchdog observer on the market logs directory."""
        if self.observer and self.observer.is_alive():
            self.stop_file_monitoring()

        try:
            import settings as _settings
            import importlib
            importlib.reload(_settings)
            marketlogs_dir = get_setting('marketlogs_dir', _settings.MARKETLOGS_DIR)
            marketlogs_path = Path(marketlogs_dir)

            if not marketlogs_path.exists():
                print(f"RestockingScreen: market logs dir not found: {marketlogs_path}")
                return

            handler = ExportFileHandler(self.on_export_file_created)
            self.observer = Observer()
            self.observer.schedule(handler, str(marketlogs_path), recursive=False)
            self.observer.start()
            print(f"RestockingScreen: started file monitoring on {marketlogs_path}")
        except Exception as e:
            print(f"RestockingScreen: could not start file monitoring: {e}")

    def stop_file_monitoring(self):
        """Stop the watchdog observer."""
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=2)
                print("RestockingScreen: file monitoring stopped")
            except Exception as e:
                print(f"RestockingScreen: error stopping observer: {e}")
            finally:
                self.observer = None

    def on_export_file_created(self, file_path, region_name, item_name):
        """Called when EVE exports a market file while this screen is open."""
        try:
            data = parse_export_file(file_path)
            type_id = data.get('type_id')
            min_sell = data.get('min_sell_price')
            max_buy = data.get('max_buy_price')

            if type_id is None:
                return

            matched = None
            for item in self.items_data:
                if item['type_id'] == type_id:
                    matched = item
                    break

            if matched is None:
                return  # Item not in our restocking list

            broker_fee_buy = float(self.current_character.get('broker_fee_buy', 3.0))
            broker_fee_sell = float(self.current_character.get('broker_fee_sell', 3.0))
            sales_tax = float(self.current_character.get('sales_tax', 7.5))

            matched['buy_price'] = max_buy
            matched['sell_price'] = min_sell
            self.price_updated_at[type_id] = datetime.now()

            if max_buy is not None and min_sell is not None:
                calc = calculate_profit(
                    max_buy, min_sell,
                    broker_fee_buy, broker_fee_sell, sales_tax
                )
                matched['taxes'] = calc['taxes']
                matched['profit_isk'] = calc['profit_isk']
                matched['profit_pct'] = calc['profit_pct']
            else:
                matched['taxes'] = matched['profit_isk'] = matched['profit_pct'] = None

            async def _refresh():
                self._render_table()
                self.status_text.value = f"Price updated: {item_name} from {region_name}"
                self.status_text.color = ft.Colors.GREEN
                self.page.update()

            self.page.run_task(_refresh)

        except Exception as ex:
            print(f"RestockingScreen: error processing export file: {ex}")

    # ─────────────────────────────────────────────────────────────────────
    # Sorting & pagination
    # ─────────────────────────────────────────────────────────────────────

    def _sort_key(self, column_index):
        def _f(v):
            return float(v) if v is not None else -1e18

        keys = [
            lambda x: x['type_id'],
            lambda x: x['type_name'].lower(),
            lambda x: int(x['qty_sold']),
            lambda x: _f(x['buy_price']),
            lambda x: _f(x['sell_price']),
            lambda x: _f(x['taxes']),
            lambda x: _f(x['profit_pct']),
            lambda x: _f(x['profit_isk']),
        ]
        return keys[column_index]

    def _sort_data(self):
        self.items_data.sort(
            key=self._sort_key(self.sort_column_index),
            reverse=not self.sort_ascending,
        )

    def sort_by_column(self, column_index):
        if self.sort_column_index == column_index:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column_index = column_index
            self.sort_ascending = True
        self._sort_data()
        self.current_page = 0
        self._render_table()
        self.page.update()

    def change_page(self, delta):
        total_pages = max(1, (len(self.items_data) - 1) // self.rows_per_page + 1)
        new_page = self.current_page + delta
        if 0 <= new_page < total_pages:
            self.current_page = new_page
            self._render_table()
            self.page.update()

    def toggle_row_highlight(self, type_id):
        if type_id in self.clicked_rows:
            self.clicked_rows.remove(type_id)
        else:
            self.clicked_rows.add(type_id)
        self._render_table()
        self.page.update()

    # ─────────────────────────────────────────────────────────────────────
    # Open item in EVE market window
    # ─────────────────────────────────────────────────────────────────────

    def _open_in_game(self, type_id):
        """Open the in-game market window for type_id via ESI. Runs in a background thread."""
        def _thread():
            character = self.current_character
            if not character:
                self.page.run_task(self._show_snack, "Not logged in", error=True)
                return

            access_token = character.get('access_token')
            refresh_token = character.get('refresh_token')
            token_expiry = character.get('token_expiry')

            if isinstance(token_expiry, str):
                try:
                    token_expiry = datetime.fromisoformat(token_expiry)
                except ValueError:
                    token_expiry = None

            esi = ESIAPI()

            if not access_token or not token_expiry or datetime.now() >= token_expiry:
                if not refresh_token:
                    self.page.run_task(self._show_snack, "Token expired - please log in again", error=True)
                    return
                token_data = esi.refresh_access_token(refresh_token)
                if not token_data:
                    self.page.run_task(self._show_snack, "Token refresh failed - please log in again", error=True)
                    return
                access_token = token_data['access_token']
                save_character({
                    'character_id': character['character_id'],
                    'character_name': character['character_name'],
                    'access_token': access_token,
                    'token_expiry': token_data['token_expiry'],
                })
                self.current_character = get_character(character['character_id']) or character

            success = esi.open_market_window(type_id, access_token)
            if success:
                self.page.run_task(self._show_snack, "Market window opened in EVE")
            else:
                self.page.run_task(self._show_snack, "Failed to open market window", error=True)

        threading.Thread(target=_thread, daemon=True).start()

    async def _show_snack(self, message, error=False):
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_700 if error else ft.Colors.GREEN_700,
            duration=3000,
        )
        self.page.snack_bar.open = True
        self.page.update()

    # ─────────────────────────────────────────────────────────────────────
    # Table rendering
    # ─────────────────────────────────────────────────────────────────────

    def _fmt_isk(self, value):
        return f"{value:,.0f}" if value is not None else "-"

    def _fmt_pct(self, value):
        return f"{value:.1f}%" if value is not None else "-"

    def _is_price_stale(self, type_id):
        """True if the price for this item is present but older than 1 hour."""
        item = next((i for i in self.items_data if i['type_id'] == type_id), None)
        if item is None or (item.get('buy_price') is None and item.get('sell_price') is None):
            return False
        updated_at = self.price_updated_at.get(type_id)
        if updated_at is None:
            return True
        return (datetime.now() - updated_at).total_seconds() > 3600

    def _price_cell(self, text_value, stale):
        """DataCell content with optional stale warning icon."""
        if stale:
            return ft.Row(
                [
                    ft.Text(text_value),
                    ft.Icon(
                        ft.Icons.WARNING_AMBER,
                        size=12,
                        color=ft.Colors.ORANGE,
                        tooltip="Price data older than 1 hour",
                    ),
                ],
                spacing=3,
                tight=True,
            )
        return ft.Text(text_value)

    def _render_table(self):
        if not self.items_data:
            return

        start_idx = self.current_page * self.rows_per_page
        end_idx = min(start_idx + self.rows_per_page, len(self.items_data))
        page_data = self.items_data[start_idx:end_idx]
        total_pages = max(1, (len(self.items_data) - 1) // self.rows_per_page + 1)

        def _col(label, idx, numeric=False):
            return ft.DataColumn(
                ft.Text(label, weight=ft.FontWeight.BOLD),
                numeric=numeric,
                on_sort=lambda _, i=idx: self.sort_by_column(i),
            )

        columns = [
            _col("Type ID", 0, numeric=True),
            _col("Item", 1),
            _col("Qty Sold", 2, numeric=True),
            _col("Price Buy", 3, numeric=True),
            _col("Price Sell", 4, numeric=True),
            _col("Taxes", 5, numeric=True),
            _col("Profit %", 6, numeric=True),
            _col("Profit ISK", 7, numeric=True),
        ]

        rows = []
        for item in page_data:
            type_id = item['type_id']
            type_name = item['type_name']
            is_clicked = type_id in self.clicked_rows
            stale = self._is_price_stale(type_id)

            profit_pct = item.get('profit_pct')
            if profit_pct is not None and profit_pct > 0:
                profit_color = ft.Colors.GREEN_700
            elif profit_pct is not None and profit_pct < 0:
                profit_color = ft.Colors.RED
            else:
                profit_color = None

            def _tap(tid=type_id, tname=type_name, extra=None):
                def handler(e):
                    self.toggle_row_highlight(tid)
                    if extra:
                        extra(e, tid, tname)
                return handler

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Text(str(type_id), color=ft.Colors.BLUE),
                            on_tap=_tap(
                                extra=lambda _, tid, tname: self.page.run_task(
                                    self._copy_to_clipboard, str(tid), "Type ID"
                                )
                            ),
                        ),
                        ft.DataCell(
                            ft.Text(type_name, color=ft.Colors.BLUE),
                            on_tap=_tap(
                                extra=(
                                    lambda _, tid, tname: self._open_in_game(tid)
                                    if self.current_character else
                                    lambda _, tid, tname: self.page.run_task(
                                        self._copy_to_clipboard, tname, "Item name"
                                    )
                                ),
                            ),
                        ),
                        ft.DataCell(ft.Text(f"{item['qty_sold']:,}"), on_tap=_tap()),
                        ft.DataCell(
                            self._price_cell(self._fmt_isk(item.get('buy_price')), stale),
                            on_tap=_tap(),
                        ),
                        ft.DataCell(
                            self._price_cell(self._fmt_isk(item.get('sell_price')), stale),
                            on_tap=_tap(),
                        ),
                        ft.DataCell(ft.Text(self._fmt_isk(item.get('taxes'))), on_tap=_tap()),
                        ft.DataCell(
                            ft.Text(self._fmt_pct(profit_pct), color=profit_color),
                            on_tap=_tap(),
                        ),
                        ft.DataCell(
                            ft.Text(self._fmt_isk(item.get('profit_isk')), color=profit_color),
                            on_tap=_tap(),
                        ),
                    ],
                    color=ft.Colors.with_opacity(0.1, ft.Colors.BLUE) if is_clicked else None,
                )
            )

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

        prev_button = ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            on_click=lambda _: self.change_page(-1),
            disabled=self.current_page == 0,
        )
        next_button = ft.IconButton(
            icon=ft.Icons.ARROW_FORWARD,
            on_click=lambda _: self.change_page(1),
            disabled=self.current_page >= total_pages - 1,
        )
        page_info = ft.Text(
            f"Page {self.current_page + 1} of {total_pages} | "
            f"Showing {start_idx + 1}–{end_idx} of {len(self.items_data)}",
            size=12,
        )

        self.results_container.content = ft.Column([
            ft.Container(
                content=ft.Row([data_table], scroll=ft.ScrollMode.AUTO, expand=True),
                padding=ft.padding.only(top=0, left=0, right=4, bottom=4),
                expand=True,
            ),
            ft.Container(height=8),
            ft.Row(
                [prev_button, page_info, next_button],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
        ], scroll=ft.ScrollMode.AUTO, expand=True)

        self.results_container.visible = True

    # ─────────────────────────────────────────────────────────────────────
    # Clipboard helper
    # ─────────────────────────────────────────────────────────────────────

    async def _copy_to_clipboard(self, text, label):
        await ft.Clipboard().set(text)
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(f"{label} copied: {text}"),
            duration=2000,
        )
        self.page.snack_bar.open = True
        self.page.update()

    # ─────────────────────────────────────────────────────────────────────
    # Build
    # ─────────────────────────────────────────────────────────────────────

    def build(self):
        return self.container
