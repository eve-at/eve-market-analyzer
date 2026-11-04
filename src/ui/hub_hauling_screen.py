"""Hub hauling screen UI component"""
import flet as ft
import threading
from datetime import datetime
from src.handlers.hub_hauling_handler import (
    resolve_hubs,
    get_orders_status,
    find_hub_deals,
    export_deals_to_csv,
    format_multibuy,
    get_route_jumps,
    trip_hours,
    isk_per_hour,
)
from src.handlers.hub_trading_handler import find_hub_trading_deals
from src.handlers.trade_opportunities_handler import update_orders
from src.handlers.fees import get_trade_skills, get_hub_broker_fee, ADVANCED_BROKER_RELATIONS_SKILL_ID
from src.database import load_top_market_groups, get_setting, save_setting
from src.database.models import get_current_character_id, get_character
from src.utils.price_calculator import format_price_display


DEFAULT_SALES_TAX = 7.50
DEFAULT_BROKER_FEE = 3.00
STALE_ORDERS_MINUTES = 30

MODE_INSTANT = "instant"
MODE_TRADING = "trading"
MODE_DESCRIPTIONS = {
    MODE_INSTANT: "Buy from sell orders in one hub, haul and sell instantly to buy orders in another",
    MODE_TRADING: "Buy from sell orders in one hub, haul and place your own sell orders in another",
}

# Orders update state shared by all screen instances: the update keeps running
# in background when the user leaves the screen, and a reopened screen follows it
_orders_update_lock = threading.Lock()
_orders_update = {'running': False, 'region_name': None, 'screen': None}


def _parse_number(value):
    """Parse a number typed with optional thousands separators, None if empty"""
    cleaned = (value or "").replace(" ", "").replace(",", "").replace("_", "").replace(" ", "")
    if not cleaned:
        return None
    return float(cleaned)


def _format_number(value):
    """Format a parsed number with thousands separators, keeping decimals only if present"""
    if value is None:
        return ""
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip('0').rstrip('.')


def _format_isk(value):
    """Format ISK amount without decimals"""
    return f"{value:,.0f}"


def _format_hours(hours):
    """Format duration in hours as '1 h 50 min' / '55 min'"""
    minutes = int(round(hours * 60))
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60} min"


def _format_daily_volume(value):
    """Daily volume with decimals only for small numbers"""
    return f"{value:,.1f}" if value < 10 else f"{value:,.0f}"


def _direction_text(deal):
    """'Jita → Amarr'"""
    return deal['direction_label'].replace(" -> ", " → ")


# Deals table columns per mode: (header, sort key, cell text, numeric, header tooltip).
# The "Item" column cell is rendered separately (clickable name).
_INSTANT_COLUMNS = [
    ("Direction", lambda d: d['direction_label'], _direction_text, False, None),
    ("Item", lambda d: d['typeName'].lower(), None, False, None),
    ("Qty", lambda d: d['qty'], lambda d: f"{d['qty']:,}", True, None),
    ("m³", lambda d: d['volume'], lambda d: f"{d['volume']:,.1f}", True, "Volume, m³"),
    ("Max Buy", lambda d: d['max_buy_price'], lambda d: format_price_display(d['max_buy_price']), True,
     "Max buy price: the highest sell order price to buy up to in the source hub"),
    ("Avg Buy", lambda d: d['investment'] / d['qty'], lambda d: format_price_display(d['investment'] / d['qty']), True,
     "Average buy price"),
    ("Min Sell", lambda d: d['min_sell_price'], lambda d: format_price_display(d['min_sell_price']), True,
     "Lowest buy order price we sell into in the destination hub"),
    ("Investment", lambda d: d['investment'], lambda d: _format_isk(d['investment']), True, None),
    ("Revenue", lambda d: d['revenue'], lambda d: _format_isk(d['revenue']), True, "Revenue after sales tax"),
    ("Profit", lambda d: d['profit'], lambda d: _format_isk(d['profit']), True, None),
    ("Margin %", lambda d: d['margin'], lambda d: f"{d['margin']:.1f}", True, None),
    ("Profit/m³", lambda d: d['profit_per_m3'], lambda d: _format_isk(d['profit_per_m3']), True, None),
    ("Limit", lambda d: d['limited_by'], lambda d: d['limited_by'], False, "What limited the quantity"),
]

_TRADING_COLUMNS = [
    ("Direction", lambda d: d['direction_label'], _direction_text, False, None),
    ("Item", lambda d: d['typeName'].lower(), None, False, None),
    ("Qty", lambda d: d['qty'], lambda d: f"{d['qty']:,}", True, None),
    ("m³", lambda d: d['volume'], lambda d: f"{d['volume']:,.1f}", True, "Volume, m³"),
    ("Max Buy", lambda d: d['max_buy_price'], lambda d: format_price_display(d['max_buy_price']), True,
     "Max buy price: the highest sell order price to buy up to in the source hub"),
    ("Sell", lambda d: d['sell_price'],
     lambda d: format_price_display(d['sell_price']) + (" *" if d['price_capped'] else ""), True,
     "Price of your sell order in the destination hub (* = capped by 30-day average price)"),
    ("Investment", lambda d: d['investment'], lambda d: _format_isk(d['investment']), True, None),
    ("Fees", lambda d: d['fees'], lambda d: _format_isk(d['fees']), True, "Broker fee + relists + sales tax"),
    ("Profit", lambda d: d['profit'], lambda d: _format_isk(d['profit']), True, None),
    ("Margin %", lambda d: d['margin'], lambda d: f"{d['margin']:.1f}", True, None),
    ("Daily Vol", lambda d: d['daily_volume'], lambda d: _format_daily_volume(d['daily_volume']), True,
     "Average units traded per day in the destination region (30 days)"),
    ("Comp.", lambda d: d['competitors'], lambda d: str(d['competitors']), True,
     "Competitors: sell orders in the destination hub updated in the last 2 days"),
    ("Share %", lambda d: d['market_share'], lambda d: f"{d['market_share']:.0f}", True,
     "Expected share of daily volume: Market share, but not more than an equal split with competitors"),
    ("Days", lambda d: d['days_to_sell'], lambda d: f"{d['days_to_sell']:.1f}", True, "Expected days to sell"),
    ("Profit/m³", lambda d: d['profit_per_m3'], lambda d: _format_isk(d['profit_per_m3']), True, None),
    ("Limit", lambda d: d['limited_by'], lambda d: d['limited_by'], False, "What limited the quantity"),
]

DEALS_TEXT_SIZE = 11
ITEM_COLUMN_WIDTH = 200

_COLUMNS = {MODE_INSTANT: _INSTANT_COLUMNS, MODE_TRADING: _TRADING_COLUMNS}

_TRADING_CSV_FIELDS = ['direction_label', 'type_id', 'typeName', 'qty', 'volume', 'max_buy_price',
                       'sell_price', 'price_capped', 'avg_price_dst', 'best_ask_dst', 'best_bid_dst',
                       'investment', 'fees', 'revenue', 'profit', 'margin', 'daily_volume',
                       'days_to_sell', 'competitors', 'profit_per_m3', 'limited_by']


def _profit_column_index(mode):
    """Index of the Profit column (default sort) for a mode"""
    return next(i for i, column in enumerate(_COLUMNS[mode]) if column[0] == "Profit")


class HubHaulingScreen:
    """Screen for finding hauling deals between two trade hubs"""

    def __init__(self, page: ft.Page, on_back_callback):
        self.page = page
        self.on_back_callback = on_back_callback

        # Trade hubs resolved from static data
        all_hubs = resolve_hubs()
        self.hubs = [h for h in all_hubs if h['station_id']]
        self.hubs_by_name = {h['name']: h for h in self.hubs}
        missing_hubs = len(all_hubs) - len(self.hubs)

        # Mode
        self.mode = get_setting('hub_hauling_mode', MODE_INSTANT)
        if self.mode not in _COLUMNS:
            self.mode = MODE_INSTANT

        # Results data for sorting and pagination
        self.deals_data = []
        self.plans = {}
        self.results_mode = self.mode
        self.trip = None
        self.direction_filter = "all"
        self.sort_column_index = _profit_column_index(self.mode)
        self.sort_ascending = False
        self.current_page = 0
        self.rows_per_page = 20
        self.clicked_rows = set()  # Track clicked (direction, type_id)
        self.active_tab = "deals"

        # Character sales tax, broker fee fallback and trade skills
        self.sales_tax = DEFAULT_SALES_TAX
        self.broker_fee_fallback = DEFAULT_BROKER_FEE
        self.character_id = get_current_character_id()
        character = get_character(self.character_id) if self.character_id else None
        if character:
            if character.get('sales_tax') is not None:
                self.sales_tax = float(character['sales_tax'])
            if character.get('broker_fee_sell') is not None:
                self.broker_fee_fallback = float(character['broker_fee_sell'])
        self.has_character = character is not None
        self.advanced_broker_relations = 0
        if self.character_id:
            levels, _ = get_trade_skills(self.character_id)
            self.advanced_broker_relations = levels[ADVANCED_BROKER_RELATIONS_SKILL_ID]

        self.sales_tax_text = ft.Text("", size=11)

        # Mode selection
        self.mode_radio = ft.RadioGroup(
            value=self.mode,
            on_change=self.on_mode_changed,
            content=ft.Row([
                ft.Radio(value=MODE_INSTANT, label="Instant (sell to buy orders)"),
                ft.Radio(value=MODE_TRADING, label="Trading (place sell orders)"),
            ], spacing=20)
        )
        self.mode_description_text = ft.Text(MODE_DESCRIPTIONS[self.mode], size=11, color=ft.Colors.GREY_700)

        # Hub selection
        hub_names = [h['name'] for h in self.hubs]
        self.hub_a_name = self._saved_hub('hub_hauling_hub_a', 'Jita', hub_names)
        self.hub_b_name = self._saved_hub('hub_hauling_hub_b', 'Amarr', hub_names, exclude=self.hub_a_name)

        self.hub_a_dropdown = ft.Dropdown(
            label="Hub A",
            value=self.hub_a_name,
            options=[ft.DropdownOption(key=name, text=name) for name in hub_names],
            on_select=lambda e: self.on_hub_changed("a", e.control.value),
            width=200,
            text_size=12,
            dense=True,
        )
        self.hub_b_dropdown = ft.Dropdown(
            label="Hub B",
            value=self.hub_b_name,
            options=[ft.DropdownOption(key=name, text=name) for name in hub_names],
            on_select=lambda e: self.on_hub_changed("b", e.control.value),
            width=200,
            text_size=12,
            dense=True,
        )
        self.swap_button = ft.IconButton(
            icon=ft.Icons.SWAP_HORIZ,
            tooltip="Swap hubs",
            on_click=self.on_swap_hubs
        )

        self.hubs_warning_text = ft.Text(
            f"{missing_hubs} trade hub(s) not found in static data - run Update Static Data",
            size=11,
            color=ft.Colors.ORANGE,
            visible=missing_hubs > 0
        )

        # Parameter fields (both modes)
        self.cargo_field = self._number_field("Cargo capacity, m³", get_setting('hub_hauling_cargo', '60000'))
        self.budget_field = self._number_field("Budget, ISK (empty = no limit)", get_setting('hub_hauling_budget', ''))
        self.max_value_field = self._number_field("Max cargo value, ISK (empty = no limit)", get_setting('hub_hauling_max_value', ''))
        self.min_profit_field = self._number_field("Min profit per item, ISK", get_setting('hub_hauling_min_profit', '1000000'))
        self.min_margin_field = self._number_field("Min margin, %", get_setting('hub_hauling_min_margin', '5'))
        self.max_margin_field = self._number_field("Max margin, % (empty = no limit)", get_setting('hub_hauling_max_margin', '100'))
        self.max_margin_field.tooltip = "Very high margins usually mean a thin market or inflated prices in the destination"
        self.min_investment_field = self._number_field("Min investment per item, ISK", get_setting('hub_hauling_min_investment', '1000000'))
        self.max_plan_items_field = self._number_field("Max items in cargo plan", get_setting('hub_hauling_max_plan_items', '50'))
        self.time_per_jump_field = self._number_field("Time per jump, sec", get_setting('hub_hauling_time_per_jump', '60'))
        self.overhead_field = self._number_field("Overhead per trip, min", get_setting('hub_hauling_overhead', '10'))

        self.route_radio = ft.RadioGroup(
            value=get_setting('hub_hauling_route', 'safest'),
            content=ft.Row([
                ft.Text("Route:", size=12),
                ft.Radio(value="safest", label="Safest (high-sec only)"),
                ft.Radio(value="shortest", label="Shortest"),
            ], spacing=10)
        )

        # Parameter fields (Trading mode only)
        self.max_days_field = self._number_field("Max days to sell", get_setting('hub_hauling_max_days', '7'))
        self.market_share_field = self._number_field("Market share, %", get_setting('hub_hauling_market_share', '20'))
        self.relists_field = self._number_field("Expected relists", get_setting('hub_hauling_relists', '2'))
        self.max_competitors_field = self._number_field("Max competitors", get_setting('hub_hauling_max_competitors', '10'))
        self.max_competitors_field.tooltip = ("Sell orders in the destination hub updated in the last 2 days. "
                                              "Empty = no limit. Your market share is also limited to an equal "
                                              "split with competitors")
        self.trading_fields_row = ft.Row(
            [self.max_days_field, self.market_share_field, self.relists_field, self.max_competitors_field],
            spacing=8,
            visible=self.mode == MODE_TRADING
        )

        # Market groups
        self.market_groups = load_top_market_groups()
        saved_groups = get_setting('hub_hauling_market_groups', '') or ''
        self.selected_market_group_ids = {int(g) for g in saved_groups.split(',') if g.strip().isdigit()}

        market_group_checkboxes_controls = []
        for group in self.market_groups:
            group_id = group['marketGroupID']
            market_group_checkboxes_controls.append(ft.Checkbox(
                label=group['marketGroupName'],
                value=group_id in self.selected_market_group_ids,
                on_change=lambda e, gid=group_id: self.on_market_group_changed(e, gid),
                margin=-8
            ))

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

        # Buttons, orders status and broker fee under each hub
        self.update_a_button = self._update_orders_button("a")
        self.update_b_button = self._update_orders_button("b")
        self.hub_a_status_text = ft.Text("", size=11, width=200)
        self.hub_b_status_text = ft.Text("", size=11, width=200)
        self.hub_a_fee_text = ft.Text("", size=11, width=200)
        self.hub_b_fee_text = ft.Text("", size=11, width=200)

        self.find_deals_button = ft.ElevatedButton(
            "Find Deals",
            on_click=self.on_find_deals,
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

        # Status text
        self.status_text = ft.Text("", size=12, color=ft.Colors.GREY_600)

        # Log container for progress
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
            height=250,
            width=700,
            visible=False
        )

        # Result tabs
        self.deals_tab_button = self._tab_button("Deals", "deals", active=True)
        self.plan_tab_button = self._tab_button("Cargo plan", "plan", active=False)

        self.direction_radio = ft.RadioGroup(
            value="all",
            on_change=self.on_direction_filter_changed,
            content=ft.Row([
                ft.Radio(value="all", label="All"),
                ft.Radio(value="A->B", label="A → B"),
                ft.Radio(value="B->A", label="B → A"),
            ], spacing=10)
        )

        self.deals_content = ft.Column(expand=True)
        self.plan_content = ft.Column(expand=True, visible=False, scroll=ft.ScrollMode.AUTO)

        self.results_container = ft.Container(
            content=self._results_placeholder(),
            padding=20,
            expand=True
        )

        # Accordion for filters
        self.filter_accordion = ft.ExpansionTile(
            title=ft.Text("Hubs & Parameters", size=14, weight=ft.FontWeight.BOLD),
            subtitle=ft.Text("Click to expand/collapse", size=11),
            expanded=True,
            controls=[
                ft.Container(
                    content=ft.Column([
                        self.mode_radio,
                        ft.Container(height=5),
                        ft.Row([
                            ft.Column([
                                self.hub_a_dropdown,
                                self.update_a_button,
                                self.hub_a_status_text,
                                self.hub_a_fee_text,
                            ], spacing=5),
                            ft.Container(content=self.swap_button, padding=ft.padding.only(top=2)),
                            ft.Column([
                                self.hub_b_dropdown,
                                self.update_b_button,
                                self.hub_b_status_text,
                                self.hub_b_fee_text,
                            ], spacing=5),
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
                        self.hubs_warning_text,
                        ft.Container(height=5),
                        ft.Row([
                            # Left column - Parameters
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("Parameters", size=12, weight=ft.FontWeight.BOLD),
                                    ft.Container(height=2),
                                    ft.Column([
                                        ft.Row([self.cargo_field, self.max_plan_items_field], spacing=8),
                                        ft.Row([self.budget_field, self.max_value_field], spacing=8),
                                        ft.Row([self.min_profit_field, self.min_investment_field], spacing=8),
                                        ft.Row([self.min_margin_field, self.max_margin_field], spacing=8),
                                        self.trading_fields_row,
                                        ft.Row([self.time_per_jump_field, self.overhead_field], spacing=8),
                                    ], spacing=15),
                                    self.route_radio,
                                    self.sales_tax_text,
                                ], spacing=3),
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
                            self.find_deals_button,
                            self.export_button,
                            self.status_text,
                        ], spacing=10),
                    ], spacing=0),
                    padding=ft.padding.only(left=8, right=8, bottom=8, top=3)
                )
            ]
        )

        # Main container
        self.container = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Hub Hauling",
                    size=18,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(height=1),
                self.mode_description_text,
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

        self._refresh_mode_texts()
        self.refresh_orders_status(update=False)
        self._attach_to_running_update()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _saved_hub(self, setting_name, default, hub_names, exclude=None):
        """Get saved hub name if valid, otherwise default or first available"""
        saved = get_setting(setting_name, default)
        for name in (saved, default, *hub_names):
            if name in hub_names and name != exclude:
                return name
        return None

    def _number_field(self, label, value):
        """Create a numeric parameter field, reformatted with thousands separators on blur"""
        field = ft.TextField(
            label=label,
            value=str(value or ""),
            height=45,
            text_size=12,
            content_padding=8,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_blur=lambda e: self._reformat_number_field(e.control),
            expand=True
        )
        self._reformat_number_field(field, update=False)
        return field

    def _reformat_number_field(self, field, update=True):
        """Show a valid number as 2,000,000,000; leave invalid input as typed"""
        try:
            field.value = _format_number(_parse_number(field.value))
        except ValueError:
            return
        if update:
            self.page.update()

    def _tab_button(self, title, tab_name, active):
        """Create a tab button like on the character screen"""
        return ft.Container(
            content=ft.Text(title, size=14, weight=ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL),
            padding=ft.Padding(15, 5, 15, 5),
            bgcolor=ft.Colors.BLUE if active else ft.Colors.GREY_300,
            border_radius=ft.border_radius.only(top_left=5, top_right=5),
            on_click=lambda _: self.switch_tab(tab_name),
            ink=True
        )

    def _results_placeholder(self):
        """Hint shown before the first search"""
        return ft.Text(
            "Select two hubs and click 'Find Deals' to search for hauling opportunities",
            size=14,
            color=ft.Colors.GREY_600,
            text_align=ft.TextAlign.CENTER
        )

    def _selected_hubs(self):
        """Return (hub_a, hub_b) dicts"""
        return self.hubs_by_name.get(self.hub_a_name), self.hubs_by_name.get(self.hub_b_name)

    def _update_orders_button(self, side):
        """Create Update Orders button for hub A or B"""
        return ft.ElevatedButton(
            "Update Orders",
            on_click=lambda _: self.on_update_orders(side),
            width=200,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
                padding=ft.Padding(20, 10, 20, 10)
            )
        )

    def _set_busy(self, busy):
        """Enable/disable controls while a background task runs"""
        self.update_a_button.disabled = busy
        self.update_b_button.disabled = busy
        self.find_deals_button.disabled = busy
        self.export_button.disabled = busy
        self.hub_a_dropdown.disabled = busy
        self.hub_b_dropdown.disabled = busy
        self.swap_button.disabled = busy
        self.mode_radio.disabled = busy

    def _show_snackbar(self, message):
        """Show snackbar notification"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()

    def _hub_broker_fee(self, hub):
        """Broker fee info for placing an order in a hub"""
        return get_hub_broker_fee(self.character_id, hub['corporation_id'], self.broker_fee_fallback)

    # ------------------------------------------------------------------
    # Mode
    # ------------------------------------------------------------------

    def on_mode_changed(self, e):
        """Switch between Instant and Trading modes"""
        self.mode = e.control.value
        save_setting('hub_hauling_mode', self.mode)

        # Results of the other mode have different columns
        self.deals_data = []
        self.plans = {}
        self.sort_column_index = _profit_column_index(self.mode)
        self.sort_ascending = False
        self.results_container.content = self._results_placeholder()
        self.results_container.visible = True
        self.export_button.visible = False
        self.status_text.value = ""

        self._refresh_mode_texts()
        self.page.update()

    def _refresh_mode_texts(self):
        """Show fields and texts relevant for the current mode"""
        trading = self.mode == MODE_TRADING
        self.mode_description_text.value = MODE_DESCRIPTIONS[self.mode]
        self.trading_fields_row.visible = trading
        self.hub_a_fee_text.visible = trading
        self.hub_b_fee_text.visible = trading

        if self.has_character:
            self.sales_tax_text.value = f"Sales tax: {self.sales_tax:.3f}".rstrip('0').rstrip('.') + "% (from EVE Online Account)"
            self.sales_tax_text.color = ft.Colors.GREY_700
        else:
            self.sales_tax_text.value = (f"Sales tax: {self.sales_tax:.2f}% "
                                         "(default - log in on EVE Online Account to use your character's tax)")
            self.sales_tax_text.color = ft.Colors.ORANGE
        self.sales_tax_text.tooltip = (
            "Buying from sell orders pays no broker fee. Your sell order pays the destination hub broker fee, "
            "relist fees and sales tax" if trading else
            "Both trades are instant: buying from sell orders and selling to buy orders pay no broker fee, only sales tax"
        )

        self._refresh_broker_fees()

    def _refresh_broker_fees(self):
        """Show broker fee under each hub (Trading mode)"""
        for hub, fee_text in zip(self._selected_hubs(), (self.hub_a_fee_text, self.hub_b_fee_text)):
            if not hub:
                fee_text.value = ""
                continue
            fee = self._hub_broker_fee(hub)
            if fee['source'] == 'esi':
                fee_text.value = f"Broker fee: {fee['fee_percent']:.3f}".rstrip('0').rstrip('.') + "%"
                fee_text.tooltip = (f"Broker Relations {fee['broker_relations']}, "
                                    f"{fee['faction_name']} {fee['faction_standing']:.2f}, "
                                    f"{fee['corp_name']} {fee['corp_standing']:.2f}")
                fee_text.color = ft.Colors.GREY_700
            else:
                fee_text.value = f"Broker fee: {fee['fee_percent']:.2f}% (manual)"
                fee_text.tooltip = "Click Sync Standings & Skills on EVE Online Account to calculate broker fee per hub"
                fee_text.color = ft.Colors.ORANGE

    # ------------------------------------------------------------------
    # Hubs and orders status
    # ------------------------------------------------------------------

    def on_hub_changed(self, side, value):
        """Handle hub dropdown change; selecting the other hub swaps them"""
        if side == "a":
            if value == self.hub_b_name:
                self.hub_b_name = self.hub_a_name
            self.hub_a_name = value
        else:
            if value == self.hub_a_name:
                self.hub_a_name = self.hub_b_name
            self.hub_b_name = value

        self.hub_a_dropdown.value = self.hub_a_name
        self.hub_b_dropdown.value = self.hub_b_name
        save_setting('hub_hauling_hub_a', self.hub_a_name)
        save_setting('hub_hauling_hub_b', self.hub_b_name)
        self._refresh_broker_fees()
        self.refresh_orders_status()

    def on_swap_hubs(self, _):
        """Swap hub A and hub B"""
        self.on_hub_changed("a", self.hub_b_name)

    def refresh_orders_status(self, update=True):
        """Show orders count and age under each selected hub"""
        all_loaded = True

        for hub, status_text in zip(self._selected_hubs(), (self.hub_a_status_text, self.hub_b_status_text)):
            if not hub:
                all_loaded = False
                status_text.value = ""
                continue

            region_name = hub['region_name']
            count, fetched_at = get_orders_status(hub['region_id'])

            if count <= 0:
                all_loaded = False
                text = f"{region_name}: no orders - click Update Orders"
                color = ft.Colors.RED
            else:
                if fetched_at:
                    age_minutes = int((datetime.now() - fetched_at).total_seconds() // 60)
                    if age_minutes < 60:
                        age = f"{age_minutes} min ago"
                    elif age_minutes < 60 * 24:
                        age = f"{age_minutes // 60} h ago"
                    else:
                        age = f"{age_minutes // (60 * 24)} d ago"
                    stale = age_minutes > STALE_ORDERS_MINUTES
                else:
                    age = "update time unknown"
                    stale = True
                text = f"{region_name}: {count:,} orders, updated {age}"
                color = ft.Colors.ORANGE if stale else ft.Colors.GREEN

            status_text.value = text
            status_text.color = color

        self.find_deals_button.disabled = not all_loaded
        if update:
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

    def _attach_to_running_update(self):
        """If orders are being updated (e.g. started before leaving this screen), lock controls and follow it"""
        with _orders_update_lock:
            if not _orders_update['running']:
                return
            _orders_update['screen'] = self
            region_name = _orders_update['region_name']

        self.log_container.visible = True
        self.results_container.visible = False
        self._set_busy(True)
        self.status_text.value = f"Updating orders for {region_name}..."
        self.status_text.color = ft.Colors.BLUE

    def on_update_orders(self, side):
        """Fetch orders for the region of hub A or B"""
        hub_a, hub_b = self._selected_hubs()
        hub = hub_a if side == "a" else hub_b
        if not hub:
            return

        # Only one orders update at a time, across all instances of this screen
        with _orders_update_lock:
            if _orders_update['running']:
                return
            _orders_update.update(running=True, region_name=hub['region_name'], screen=self)

        self.log_column.controls.clear()
        self.log_container.visible = True
        self.results_container.visible = False
        self._set_busy(True)
        self.status_text.value = f"Updating orders for {hub['region_name']}..."
        self.status_text.color = ft.Colors.BLUE
        self.page.update()

        def current_screen():
            """Screen that currently shows the update (may change if the user reopens the screen)"""
            with _orders_update_lock:
                return _orders_update['screen']

        def update_thread():
            try:
                success = update_orders(hub['region_id'], callback=lambda msg: current_screen().log_progress(msg))
            finally:
                with _orders_update_lock:
                    _orders_update['running'] = False
            current_screen()._finish_orders_update(hub, success)

        threading.Thread(target=update_thread, daemon=True).start()

    def _finish_orders_update(self, hub, success):
        """Unlock controls and show result of the orders update"""
        async def update_after_import():
            self._set_busy(False)
            if success:
                self.status_text.value = f"Orders updated for {hub['region_name']}"
                self.status_text.color = ft.Colors.GREEN
            else:
                self.status_text.value = "Failed to update orders"
                self.status_text.color = ft.Colors.RED
            self.refresh_orders_status()

        self.page.run_task(update_after_import)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def on_market_group_changed(self, e, group_id):
        """Handle market group checkbox change"""
        if e.control.value:
            self.selected_market_group_ids.add(group_id)
        else:
            self.selected_market_group_ids.discard(group_id)

    def _show_error(self, message):
        """Show validation error in status"""
        self.status_text.value = message
        self.status_text.color = ft.Colors.RED
        self.page.update()

    def on_find_deals(self, _):
        """Validate parameters and run deal search"""
        hub_a, hub_b = self._selected_hubs()
        if not hub_a or not hub_b:
            return

        try:
            cargo_m3 = _parse_number(self.cargo_field.value)
            budget = _parse_number(self.budget_field.value)
            max_cargo_value = _parse_number(self.max_value_field.value)
            min_profit = _parse_number(self.min_profit_field.value) or 0
            min_margin = _parse_number(self.min_margin_field.value) or 0
            seconds_per_jump = _parse_number(self.time_per_jump_field.value) or 0
            overhead_minutes = _parse_number(self.overhead_field.value) or 0
            max_days = _parse_number(self.max_days_field.value) or 0
            market_share = _parse_number(self.market_share_field.value) or 0
            relists = _parse_number(self.relists_field.value) or 0
            max_competitors = _parse_number(self.max_competitors_field.value)
            min_investment = _parse_number(self.min_investment_field.value) or 0
            max_margin = _parse_number(self.max_margin_field.value)
            max_plan_items = _parse_number(self.max_plan_items_field.value)
            max_plan_items = int(max_plan_items) if max_plan_items else None
        except ValueError:
            self._show_error("Please enter valid numbers in all fields")
            return

        if not cargo_m3 or cargo_m3 <= 0:
            self._show_error("Cargo capacity must be greater than 0")
            return
        if self.mode == MODE_TRADING and (max_days <= 0 or market_share <= 0):
            self._show_error("Max days to sell and market share must be greater than 0")
            return

        # Remember parameters between launches
        for name, field in (('cargo', self.cargo_field), ('budget', self.budget_field),
                            ('max_value', self.max_value_field), ('min_profit', self.min_profit_field),
                            ('min_margin', self.min_margin_field), ('time_per_jump', self.time_per_jump_field),
                            ('overhead', self.overhead_field), ('max_days', self.max_days_field),
                            ('market_share', self.market_share_field), ('relists', self.relists_field),
                            ('max_competitors', self.max_competitors_field),
                            ('min_investment', self.min_investment_field),
                            ('max_margin', self.max_margin_field),
                            ('max_plan_items', self.max_plan_items_field)):
            save_setting(f'hub_hauling_{name}', field.value.strip())
        save_setting('hub_hauling_route', self.route_radio.value)
        save_setting('hub_hauling_market_groups', ','.join(str(g) for g in sorted(self.selected_market_group_ids)))

        self.log_column.controls.clear()
        self.log_container.visible = True
        self.results_container.visible = False
        self._set_busy(True)
        self.status_text.value = f"Searching deals {hub_a['name']} ⇄ {hub_b['name']}..."
        self.status_text.color = ft.Colors.BLUE
        self.page.update()

        mode = self.mode
        market_group_ids = list(self.selected_market_group_ids)
        safest = self.route_radio.value == 'safest'
        broker_fees = {hub['name']: self._hub_broker_fee(hub)['fee_percent'] for hub in (hub_a, hub_b)}

        def search_thread():
            if mode == MODE_TRADING:
                result = find_hub_trading_deals(
                    hub_a, hub_b, cargo_m3, budget, max_cargo_value,
                    min_profit, min_margin, market_group_ids, self.sales_tax,
                    broker_fees, self.advanced_broker_relations, relists, max_days, market_share,
                    max_competitors=max_competitors, min_investment=min_investment,
                    max_plan_items=max_plan_items, max_margin=max_margin, callback=self.log_progress
                )
            else:
                result = find_hub_deals(
                    hub_a, hub_b, cargo_m3, budget, max_cargo_value,
                    min_profit, min_margin, market_group_ids, self.sales_tax,
                    min_investment=min_investment, max_plan_items=max_plan_items,
                    max_margin=max_margin, callback=self.log_progress
                )

            jumps = get_route_jumps(hub_a['solar_system_id'], hub_b['solar_system_id'], safest)
            trip = {
                'jumps': jumps,
                'safest': safest,
                'hours': trip_hours(jumps, seconds_per_jump, overhead_minutes) if jumps is not None else None,
            }

            async def update_after_search():
                self._set_busy(False)
                if result is None:
                    self.status_text.value = "Failed to find deals"
                    self.status_text.color = ft.Colors.RED
                    self.export_button.visible = False
                elif not result['deals']:
                    self.status_text.value = "No deals found with current parameters"
                    self.status_text.color = ft.Colors.ORANGE
                    self.export_button.visible = False
                else:
                    self.status_text.value = f"Found {len(result['deals'])} deals"
                    self.status_text.color = ft.Colors.GREEN
                    self.export_button.visible = True
                    self.display_results(result, mode, trip)
                self.page.update()

            self.page.run_task(update_after_search)

        threading.Thread(target=search_thread, daemon=True).start()

    def display_results(self, result, mode, trip):
        """Store results and show tabs"""
        self.deals_data = result['deals']
        self.plans = result['plans']
        self.results_mode = mode
        self.trip = trip
        self.clicked_rows = set()
        self.current_page = 0
        self._sort_deals()

        self.results_container.content = ft.Column([
            ft.Row([self.deals_tab_button, self.plan_tab_button], spacing=2),
            ft.Container(height=1, bgcolor=ft.Colors.BLUE),
            ft.Container(height=5),
            self.deals_content,
            self.plan_content,
        ], spacing=0, expand=True)

        self.update_deals_display()
        self.update_plan_display()
        self.switch_tab(self.active_tab)

        self.log_container.visible = False
        self.results_container.visible = True

    def switch_tab(self, tab_name):
        """Switch between Deals and Cargo plan tabs"""
        self.active_tab = tab_name
        for name, tab in (("deals", self.deals_tab_button), ("plan", self.plan_tab_button)):
            tab.bgcolor = ft.Colors.BLUE if name == tab_name else ft.Colors.GREY_300
            tab.content.weight = ft.FontWeight.BOLD if name == tab_name else ft.FontWeight.NORMAL
        self.deals_content.visible = tab_name == "deals"
        self.plan_content.visible = tab_name == "plan"
        self.page.update()

    # ------------------------------------------------------------------
    # Deals tab
    # ------------------------------------------------------------------

    def _sort_deals(self):
        """Sort deals by current sort column"""
        sort_key = _COLUMNS[self.results_mode][self.sort_column_index][1]
        self.deals_data.sort(key=sort_key, reverse=not self.sort_ascending)

    def _filtered_deals(self):
        """Deals matching the direction filter"""
        if self.direction_filter == "all":
            return self.deals_data
        return [d for d in self.deals_data if d['direction'] == self.direction_filter]

    def sort_deals(self, column_index):
        """Sort deals by column"""
        if self.sort_column_index == column_index:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column_index = column_index
            # Text columns ascending, numbers descending by default
            self.sort_ascending = not _COLUMNS[self.results_mode][column_index][3]
        self._sort_deals()
        self.current_page = 0
        self.update_deals_display()

    def on_direction_filter_changed(self, e):
        """Handle direction filter change"""
        self.direction_filter = e.control.value
        self.current_page = 0
        self.update_deals_display()

    def change_page(self, delta):
        """Change current page"""
        new_page = self.current_page + delta
        total_pages = max((len(self._filtered_deals()) - 1) // self.rows_per_page + 1, 1)
        if 0 <= new_page < total_pages:
            self.current_page = new_page
            self.update_deals_display()

    def toggle_row_highlight(self, row_key):
        """Toggle row highlight on click"""
        if row_key in self.clicked_rows:
            self.clicked_rows.remove(row_key)
        else:
            self.clicked_rows.add(row_key)
        self.update_deals_display()

    async def copy_to_clipboard(self, text, label):
        """Copy text to clipboard and show notification"""
        await ft.Clipboard().set(text)
        self._show_snackbar(f"{label} copied")

    def update_deals_display(self):
        """Render deals table for current page"""
        columns_spec = _COLUMNS[self.results_mode]
        deals = self._filtered_deals()
        start_idx = self.current_page * self.rows_per_page
        end_idx = min(start_idx + self.rows_per_page, len(deals))
        page_data = deals[start_idx:end_idx]
        total_pages = max((len(deals) - 1) // self.rows_per_page + 1, 1)

        columns = [
            ft.DataColumn(
                ft.Text(header, weight=ft.FontWeight.BOLD, size=DEALS_TEXT_SIZE, tooltip=header_tooltip),
                numeric=numeric,
                on_sort=lambda _, i=index: self.sort_deals(i)
            )
            for index, (header, _, _, numeric, header_tooltip) in enumerate(columns_spec)
        ]

        rows = []
        for deal in page_data:
            row_key = (deal['direction'], deal['type_id'])
            highlight = lambda _, k=row_key: self.toggle_row_highlight(k)

            def copy_name(_, k=row_key, name=deal['typeName']):
                self.toggle_row_highlight(k)
                self.page.run_task(self.copy_to_clipboard, name, "Item name")

            cells = []
            for header, _, cell_text, _, _ in columns_spec:
                if cell_text is None:
                    cells.append(ft.DataCell(
                        ft.Text(deal['typeName'], color=ft.Colors.BLUE, size=DEALS_TEXT_SIZE,
                                width=ITEM_COLUMN_WIDTH, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                tooltip=deal['typeName']),
                        on_tap=copy_name
                    ))
                    continue
                tooltip = None
                if header == "Sell" and deal.get('price_capped'):
                    tooltip = (f"Best sell in destination ({format_price_display(deal['best_ask_dst'])}) is far above "
                               f"the 30-day average price - average price used")
                cells.append(ft.DataCell(ft.Text(cell_text(deal), size=DEALS_TEXT_SIZE, tooltip=tooltip), on_tap=highlight))

            rows.append(ft.DataRow(
                cells=cells,
                color=ft.Colors.with_opacity(0.1, ft.Colors.BLUE) if row_key in self.clicked_rows else None
            ))

        data_table = ft.DataTable(
            columns=columns,
            rows=rows,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            vertical_lines=ft.BorderSide(1, ft.Colors.GREY_300),
            horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_300),
            heading_row_color=ft.Colors.GREY_200,
            heading_row_height=25,
            data_row_min_height=26,
            data_row_max_height=26,
            column_spacing=12,
            horizontal_margin=6,
            sort_column_index=self.sort_column_index,
            sort_ascending=self.sort_ascending,
        )

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
            f"Page {self.current_page + 1} of {total_pages} | Showing {start_idx + 1 if deals else 0}-{end_idx} of {len(deals)}",
            size=12
        )

        if self.results_mode == MODE_TRADING:
            hint = ("Max Buy: the highest sell order price to buy up to in the source hub. "
                    "Sell: your order price in the destination (* = capped by 30-day average). "
                    "Profit is after broker fee, relists and sales tax. Hover headers for details, click item name to copy it.")
        else:
            hint = ("Max Buy: the highest sell order price to buy up to in the source hub. "
                    "Hover headers for details, click item name to copy it.")

        self.deals_content.controls = [
            ft.Column([
                ft.Row([
                    ft.Text(f"Deals ({len(deals)})", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(width=20),
                    self.direction_radio,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(hint, size=11, color=ft.Colors.GREY_600),
                ft.Container(height=5),
                ft.Container(
                    content=ft.Row([data_table], scroll=ft.ScrollMode.AUTO, expand=True),
                    padding=10,
                    expand=True,
                ),
                ft.Row([prev_button, page_info, next_button], alignment=ft.MainAxisAlignment.CENTER, spacing=20)
            ], scroll=ft.ScrollMode.AUTO, expand=True)
        ]
        self.page.update()

    # ------------------------------------------------------------------
    # Cargo plan tab
    # ------------------------------------------------------------------

    def _trip_summary(self, profit):
        """Route, trip time and ISK/h text for a plan"""
        trip = self.trip
        route_name = "safest" if trip['safest'] else "shortest"
        if trip['jumps'] is None:
            return f"Route ({route_name}): no route"
        text = f"Route: {trip['jumps']} jumps ({route_name})   ·   Trip: {_format_hours(trip['hours'])}"
        rate = isk_per_hour(profit, trip['hours'])
        if rate is not None:
            text += f"   ·   ISK/h: {_format_isk(rate)}"
            if self.results_mode == MODE_TRADING:
                text += " (hauling time, income delayed)"
        return text

    def update_plan_display(self):
        """Render cargo plans for both directions"""
        trading = self.results_mode == MODE_TRADING
        try:
            cargo_m3 = _parse_number(self.cargo_field.value) or 0
        except ValueError:
            cargo_m3 = 0

        blocks = []
        for key in ("A->B", "B->A"):
            plan = self.plans.get(key)
            if not plan:
                continue

            title = plan['direction_label'].replace("->", "→")
            if not plan['items']:
                blocks.append(ft.Column([
                    ft.Text(title, size=16, weight=ft.FontWeight.BOLD),
                    ft.Text("No deals in this direction", size=12, color=ft.Colors.GREY_600),
                ], spacing=5))
                blocks.append(ft.Divider())
                continue

            fill = plan['volume'] / cargo_m3 * 100 if cargo_m3 else 0
            summary = (
                f"Cargo: {plan['volume']:,.0f} / {cargo_m3:,.0f} m³ ({fill:.0f}%)   |   "
                f"Investment: {_format_isk(plan['investment'])} ISK   |   "
                f"Profit: {_format_isk(plan['profit'])} ISK   |   "
                f"Margin: {plan['margin']:.1f}%"
            )
            if trading:
                summary += f"   |   Sell-through: up to {plan['max_days_to_sell']:.1f} days"

            deal_by_type = {d['type_id']: d for d in self.deals_data if d['direction'] == key}
            rows = []
            for item in plan['items']:
                cells = [
                    ft.DataCell(
                        ft.Text(item['typeName'], color=ft.Colors.BLUE),
                        on_tap=lambda _, name=item['typeName']: self.page.run_task(self.copy_to_clipboard, name, "Item name")
                    ),
                    ft.DataCell(ft.Text(f"{item['qty']:,}")),
                    ft.DataCell(ft.Text(f"{item['volume']:,.1f}")),
                    ft.DataCell(ft.Text(format_price_display(item['max_buy_price']))),
                ]
                if trading:
                    deal = deal_by_type.get(item['type_id'], {})
                    sell_text = format_price_display(item['min_sell_price']) + (" *" if deal.get('price_capped') else "")
                    cells.append(ft.DataCell(ft.Text(sell_text)))
                cells += [
                    ft.DataCell(ft.Text(_format_isk(item['investment']))),
                    ft.DataCell(ft.Text(_format_isk(item['profit']))),
                ]
                if trading:
                    cells.append(ft.DataCell(ft.Text(f"{item['days_to_sell']:.1f}")))
                rows.append(ft.DataRow(cells=cells))

            headers = ["Item", "Qty", "Volume, m³", "Max Buy Price"]
            if trading:
                headers.append("Sell Price")
            headers += ["Investment", "Profit"]
            if trading:
                headers.append("Days to Sell")

            table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text(header, weight=ft.FontWeight.BOLD), numeric=header != "Item")
                    for header in headers
                ],
                rows=rows,
                border=ft.border.all(1, ft.Colors.GREY_400),
                border_radius=5,
                vertical_lines=ft.BorderSide(1, ft.Colors.GREY_300),
                horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_300),
                heading_row_color=ft.Colors.GREY_200,
                heading_row_height=25,
                data_row_min_height=30,
                data_row_max_height=30,
            )

            multibuy_text = format_multibuy(plan['items'])
            copy_button = ft.ElevatedButton(
                "Copy for Multibuy",
                icon=ft.Icons.CONTENT_COPY,
                on_click=lambda _, text=multibuy_text: self.page.run_task(self.copy_to_clipboard, text, "Multibuy list"),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.BLUE,
                    color=ft.Colors.WHITE,
                    padding=ft.Padding(20, 10, 20, 10)
                )
            )

            blocks.append(ft.Column([
                ft.Row([
                    ft.Text(f"{title} ({len(plan['items'])} items)", size=16, weight=ft.FontWeight.BOLD),
                    copy_button,
                ], spacing=20, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(summary, size=12, color=ft.Colors.GREY_800, selectable=True),
                ft.Text(self._trip_summary(plan['profit']), size=12, color=ft.Colors.GREY_800, selectable=True),
                ft.Container(
                    content=ft.Row([table], scroll=ft.ScrollMode.AUTO),
                    padding=10,
                ),
            ], spacing=5))
            blocks.append(ft.Divider())

        # Round trip: carry the A -> B plan there and the B -> A plan back
        plan_ab, plan_ba = self.plans.get("A->B"), self.plans.get("B->A")
        if plan_ab and plan_ba and self.trip and self.trip['hours']:
            hub_a, hub_b = plan_ab['direction_label'].split(" -> ")
            round_profit = plan_ab['profit'] + plan_ba['profit']
            round_hours = 2 * self.trip['hours']
            blocks.append(ft.Text(
                f"Round trip ({hub_a} → {hub_b} → {hub_a}): profit {_format_isk(round_profit)} ISK   ·   "
                f"{_format_hours(round_hours)}   ·   ISK/h {_format_isk(isk_per_hour(round_profit, round_hours))}",
                size=13, weight=ft.FontWeight.BOLD, selectable=True
            ))

        self.plan_content.controls = blocks

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def on_export_csv(self, _):
        """Export current deals to CSV"""
        if not self.deals_data:
            return

        self.status_text.value = "Exporting to CSV..."
        self.status_text.color = ft.Colors.BLUE
        self.export_button.disabled = True
        self.page.update()

        fieldnames = _TRADING_CSV_FIELDS if self.results_mode == MODE_TRADING else None

        def export_thread():
            filepath = export_deals_to_csv(self.deals_data, fieldnames=fieldnames)

            async def update_after_export():
                self.export_button.disabled = False
                if filepath:
                    self.status_text.value = f"Exported to {filepath}"
                    self.status_text.color = ft.Colors.GREEN
                else:
                    self.status_text.value = "Failed to export to CSV"
                    self.status_text.color = ft.Colors.RED
                self.page.update()

            self.page.run_task(update_after_export)

        threading.Thread(target=export_thread, daemon=True).start()

    def build(self):
        """Build and return the UI container"""
        return self.container
