"""Restocking List screen — items previously traded but not in current active orders"""
import flet as ft
import threading
from .autocomplete_field import AutoCompleteField
from src.database.models import get_current_character_id, get_character
from src.handlers.restocking_handler import (
    load_active_order_type_ids,
    get_restocking_items,
    get_prices_for_items,
    calculate_profit,
)
from src.handlers.trade_opportunities_handler import check_orders_count, update_orders


class RestockingScreen:
    """Screen that shows profitable items not currently in the character's active orders"""

    def __init__(self, page: ft.Page, regions_data, on_back_callback):
        self.page = page
        self.regions_data = regions_data
        self.on_back_callback = on_back_callback

        self.current_character = None
        self.items_data = []          # list of dicts: type_id, type_name, qty_sold, + price fields
        self.sort_column_index = 2    # default sort by qty_sold (index 2)
        self.sort_ascending = False
        self.current_page = 0
        self.rows_per_page = 50
        self.clicked_rows = set()

        self.selected_region_id = None
        self.selected_region_name = None

        # Load character
        character_id = get_current_character_id()
        if character_id:
            self.current_character = get_character(character_id)

        # ── Region selector ──────────────────────────────────────────────
        self.region_field = AutoCompleteField(
            label="Region (for price lookup)",
            hint_text="Start typing region name...",
            default_value="",
            data_dict=self.regions_data,
            on_select_callback=self.on_region_selected,
            on_validation_change=None,
        )

        # ── Buttons ──────────────────────────────────────────────────────
        self.update_orders_button = ft.ElevatedButton(
            "Update Orders",
            on_click=self.on_update_orders,
            disabled=True,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(20, 10, 20, 10),
            ),
        )

        self.update_prices_button = ft.ElevatedButton(
            "Update Prices",
            on_click=self.on_update_prices,
            disabled=True,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN,
                color=ft.Colors.WHITE,
                padding=ft.Padding(20, 10, 20, 10),
            ),
        )

        # ── Status text ──────────────────────────────────────────────────
        self.status_text = ft.Text("Loading active orders...", size=12, color=ft.Colors.BLUE)

        self.orders_status_text = ft.Text("", size=12, color=ft.Colors.GREY_600)

        # ── Log container (for update-orders progress) ───────────────────
        self.log_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            auto_scroll=True,
            spacing=2,
        )
        self.log_container = ft.Container(
            content=self.log_column,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            padding=8,
            bgcolor=ft.Colors.BLACK,
            height=180,
            width=700,
            visible=False,
        )

        # ── Loader (shown on initial page load) ──────────────────────────
        self.loader_container = ft.Container(
            content=ft.Column([
                ft.ProgressRing(width=40, height=40),
                ft.Container(height=10),
                ft.Text("Refreshing active character orders...", size=13, color=ft.Colors.GREY_600),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=40,
            visible=True,
        )

        # ── Results table container ───────────────────────────────────────
        self.results_container = ft.Container(
            content=ft.Text(
                "Loading…",
                size=14,
                color=ft.Colors.GREY_600,
                text_align=ft.TextAlign.CENTER,
            ),
            padding=20,
            expand=True,
            visible=False,
        )

        # ── Price controls row (shown after initial load) ─────────────────
        self.price_controls_row = ft.Row(
            [
                self.region_field.container,
                self.update_orders_button,
                self.update_prices_button,
            ],
            spacing=10,
            vertical_alignment=ft.MainAxisAlignment.START,
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
                ft.Container(height=4),
                self.price_controls_row,
                ft.Container(height=2),
                self.orders_status_text,
                ft.Container(height=4),
                self.log_container,
                ft.Divider(),
                self.loader_container,
                self.results_container,
            ], spacing=0),
            padding=5,
            expand=True,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Initial auto-load
    # ─────────────────────────────────────────────────────────────────────

    def start_auto_load(self):
        """Called by main.py after the page is rendered — kicks off background load"""
        thread = threading.Thread(target=self._auto_load_thread, daemon=True)
        thread.start()

    def _auto_load_thread(self):
        """Background: refresh active orders then build the items list"""
        def log(msg):
            async def _add():
                self.log_column.controls.append(
                    ft.Text(msg, size=11, color=ft.Colors.GREEN_300, font_family="Consolas", selectable=True)
                )
                self.page.update()
            self.page.run_task(_add)

        if not self.current_character:
            async def _no_char():
                self.loader_container.visible = False
                self.status_text.value = "Please log in first (EVE Online Account)"
                self.status_text.color = ft.Colors.ORANGE
                self.results_container.content = ft.Text(
                    "No character logged in. Go to EVE Online Account to log in.",
                    size=14,
                    color=ft.Colors.ORANGE,
                    text_align=ft.TextAlign.CENTER,
                )
                self.results_container.visible = True
                self.page.update()
            self.page.run_task(_no_char)
            return

        # Fetch active orders (with token refresh if needed)
        active_type_ids, updated_char = load_active_order_type_ids(
            self.current_character, callback=log
        )
        if updated_char:
            self.current_character = updated_char

        if active_type_ids is None:
            async def _err():
                self.loader_container.visible = False
                self.status_text.value = "Failed to fetch active orders. Check your login."
                self.status_text.color = ft.Colors.RED
                self.results_container.content = ft.Text(
                    "Could not load active orders from ESI. Please check your login.",
                    size=14,
                    color=ft.Colors.RED,
                    text_align=ft.TextAlign.CENTER,
                )
                self.results_container.visible = True
                self.page.update()
            self.page.run_task(_err)
            return

        # Query DB for restocking items
        items = get_restocking_items(self.current_character['character_id'], active_type_ids)

        async def _done(items=items):
            self.loader_container.visible = False
            self.price_controls_row.visible = True

            if not items:
                self.status_text.value = "No items found to restock."
                self.status_text.color = ft.Colors.ORANGE
                self.results_container.content = ft.Text(
                    "All previously traded items are already in your active orders, or no profit history found.",
                    size=14,
                    color=ft.Colors.GREY_600,
                    text_align=ft.TextAlign.CENTER,
                )
                self.results_container.visible = True
            else:
                # Store items (price fields empty initially)
                self.items_data = [
                    dict(item, buy_price=None, sell_price=None, taxes=None,
                         profit_isk=None, profit_pct=None)
                    for item in items
                ]
                self.sort_column_index = 2
                self.sort_ascending = False
                self.current_page = 0
                self._sort_data()
                self.status_text.value = (
                    f"Found {len(items)} items to restock. Select a region and click 'Update Prices'."
                )
                self.status_text.color = ft.Colors.GREEN
                self._render_table()

            self.page.update()

        self.page.run_task(_done)

    # ─────────────────────────────────────────────────────────────────────
    # Region selection
    # ─────────────────────────────────────────────────────────────────────

    def on_region_selected(self, name, region_id):
        self.selected_region_id = region_id
        self.selected_region_name = name
        self.update_orders_button.disabled = False
        self._refresh_orders_status()
        self.page.update()

    def _refresh_orders_status(self):
        if not self.selected_region_id:
            return
        count = check_orders_count(self.selected_region_id)
        if count > 0:
            self.orders_status_text.value = f"Orders for {self.selected_region_name}: {count:,} records"
            self.orders_status_text.color = ft.Colors.GREEN
            self._set_update_prices_enabled(True)
        else:
            self.orders_status_text.value = "No orders found for this region. Click 'Update Orders' first."
            self.orders_status_text.color = ft.Colors.ORANGE
            self._set_update_prices_enabled(False)
        self.page.update()

    def _set_update_prices_enabled(self, enabled):
        self.update_prices_button.disabled = not enabled or not self.items_data

    # ─────────────────────────────────────────────────────────────────────
    # Update Orders
    # ─────────────────────────────────────────────────────────────────────

    def log_progress(self, message):
        async def _add():
            self.log_column.controls.append(
                ft.Text(message, size=11, color=ft.Colors.GREEN_300, font_family="Consolas", selectable=True)
            )
            self.page.update()
        self.page.run_task(_add)

    def on_update_orders(self, e):
        if not self.selected_region_id:
            return

        self.log_column.controls.clear()
        self.log_container.visible = True
        self.update_orders_button.disabled = True
        self.update_prices_button.disabled = True
        self.orders_status_text.value = f"Updating orders for {self.selected_region_name}..."
        self.orders_status_text.color = ft.Colors.BLUE
        self.page.update()

        def _thread():
            success = update_orders(self.selected_region_id, callback=self.log_progress)

            async def _done():
                self.update_orders_button.disabled = False
                self.log_container.visible = False
                if success:
                    self._refresh_orders_status()
                else:
                    self.orders_status_text.value = "Failed to update orders."
                    self.orders_status_text.color = ft.Colors.RED
                self.page.update()

            self.page.run_task(_done)

        threading.Thread(target=_thread, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────
    # Update Prices
    # ─────────────────────────────────────────────────────────────────────

    def on_update_prices(self, e):
        if not self.selected_region_id or not self.items_data:
            return

        self.update_prices_button.disabled = True
        self.update_orders_button.disabled = True
        self.status_text.value = "Fetching prices..."
        self.status_text.color = ft.Colors.BLUE
        self.page.update()

        type_ids = [item['type_id'] for item in self.items_data]

        def _thread():
            prices = get_prices_for_items(
                self.selected_region_id,
                type_ids,
                callback=self.log_progress,
            )

            broker_fee_buy = float(self.current_character.get('broker_fee_buy', 3.0))
            broker_fee_sell = float(self.current_character.get('broker_fee_sell', 3.0))
            sales_tax = float(self.current_character.get('sales_tax', 7.5))

            # Enrich items with price and profit data
            for item in self.items_data:
                p = prices.get(item['type_id'], {})
                buy_price = p.get('buy_price')
                sell_price = p.get('sell_price')
                item['buy_price'] = buy_price
                item['sell_price'] = sell_price
                if buy_price is not None and sell_price is not None:
                    calc = calculate_profit(buy_price, sell_price, broker_fee_buy, broker_fee_sell, sales_tax)
                    item['taxes'] = calc['taxes']
                    item['profit_isk'] = calc['profit_isk']
                    item['profit_pct'] = calc['profit_pct']
                else:
                    item['taxes'] = None
                    item['profit_isk'] = None
                    item['profit_pct'] = None

            async def _done():
                self.update_prices_button.disabled = False
                self.update_orders_button.disabled = False
                self.sort_column_index = 6   # sort by profit % after update
                self.sort_ascending = False
                self._sort_data()
                self._render_table()
                self.status_text.value = (
                    f"{len(self.items_data)} items — prices updated from {self.selected_region_name}"
                )
                self.status_text.color = ft.Colors.GREEN
                self.page.update()

            self.page.run_task(_done)

        threading.Thread(target=_thread, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────
    # Sorting & pagination
    # ─────────────────────────────────────────────────────────────────────

    def _sort_key(self, column_index):
        """Return a sort-key lambda for the given column index"""
        def _safe_float(v):
            return float(v) if v is not None else -1e18

        keys = [
            lambda x: x['type_id'],                         # 0 Type ID
            lambda x: x['type_name'].lower(),               # 1 Item
            lambda x: int(x['qty_sold']),                   # 2 Qty Sold
            lambda x: _safe_float(x['buy_price']),          # 3 Price Buy
            lambda x: _safe_float(x['sell_price']),         # 4 Price Sell
            lambda x: _safe_float(x['taxes']),              # 5 Taxes
            lambda x: _safe_float(x['profit_pct']),         # 6 Profit %
            lambda x: _safe_float(x['profit_isk']),         # 7 Profit ISK
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
    # Table rendering
    # ─────────────────────────────────────────────────────────────────────

    def _fmt_isk(self, value):
        if value is None:
            return "—"
        return f"{value:,.0f}"

    def _fmt_pct(self, value):
        if value is None:
            return "—"
        return f"{value:.1f}%"

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

            def _tap(type_id=type_id, type_name=type_name, extra=None):
                def handler(e):
                    self.toggle_row_highlight(type_id)
                    if extra:
                        extra(e, type_id, type_name)
                return handler

            profit_pct = item.get('profit_pct')
            if profit_pct is not None and profit_pct > 0:
                profit_color = ft.Colors.GREEN_700
            elif profit_pct is not None and profit_pct < 0:
                profit_color = ft.Colors.RED
            else:
                profit_color = None

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Text(str(type_id), color=ft.Colors.BLUE),
                            on_tap=_tap(
                                type_id=type_id, type_name=type_name,
                                extra=lambda _, tid, tname: self.page.run_task(
                                    self._copy_to_clipboard, str(tid), "Type ID"
                                )
                            ),
                        ),
                        ft.DataCell(
                            ft.Text(type_name, color=ft.Colors.BLUE),
                            on_tap=_tap(
                                type_id=type_id, type_name=type_name,
                                extra=lambda _, tid, tname: self.page.run_task(
                                    self._copy_to_clipboard, tname, "Item name"
                                )
                            ),
                        ),
                        ft.DataCell(ft.Text(f"{item['qty_sold']:,}"), on_tap=_tap()),
                        ft.DataCell(ft.Text(self._fmt_isk(item.get('buy_price'))), on_tap=_tap()),
                        ft.DataCell(ft.Text(self._fmt_isk(item.get('sell_price'))), on_tap=_tap()),
                        ft.DataCell(ft.Text(self._fmt_isk(item.get('taxes'))), on_tap=_tap()),
                        ft.DataCell(
                            ft.Text(self._fmt_pct(item.get('profit_pct')), color=profit_color),
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
            ft.Text(
                f"Items to Restock ({len(self.items_data)})",
                size=16,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Container(height=8),
            ft.Container(
                content=ft.Row([data_table], scroll=ft.ScrollMode.AUTO, expand=True),
                padding=10,
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
