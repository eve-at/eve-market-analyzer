"""Handler for the Restocking List page"""
import sqlite3
import os
import importlib
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from src.auth.esi_api import ESIAPI
from src.database.models import get_character, save_character

THE_FORGE_REGION_ID = 10000002

ESI_MARKETS_URL = "https://esi.evetech.net/latest/markets"


def _get_settings():
    import settings
    importlib.reload(settings)
    return settings


def _get_connection():
    settings = _get_settings()
    db_path = settings.DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def load_active_order_type_ids(character, callback=None):
    """Refresh token if needed, fetch active character orders and return set of type_ids.

    Returns:
        (set_of_type_ids, updated_character) or (None, character) on error
    """
    def log(msg):
        if callback:
            callback(msg)

    character_id = character['character_id']
    access_token = character.get('access_token')
    refresh_token = character.get('refresh_token')
    token_expiry = character.get('token_expiry')

    esi = ESIAPI()

    if token_expiry and isinstance(token_expiry, str):
        try:
            token_expiry = datetime.fromisoformat(token_expiry)
        except ValueError:
            token_expiry = None

    if not access_token or not token_expiry or datetime.now() >= token_expiry:
        log("Access token expired, refreshing...")
        if not refresh_token:
            log("ERROR: No refresh token. Please log in again.")
            return None, character
        token_data = esi.refresh_access_token(refresh_token)
        if not token_data:
            log("ERROR: Failed to refresh token. Please log in again.")
            return None, character
        access_token = token_data['access_token']
        save_character({
            'character_id': character_id,
            'character_name': character['character_name'],
            'access_token': access_token,
            'token_expiry': token_data['token_expiry'],
        })
        character = get_character(character_id) or character
        log("Token refreshed.")

    log("Fetching active character orders from ESI...")
    orders = esi.get_character_active_orders(character_id, access_token)

    if orders is None:
        log("ERROR: Failed to fetch active orders from ESI.")
        return None, character

    type_ids = {order['type_id'] for order in orders}
    log(f"Found {len(orders)} active orders covering {len(type_ids)} distinct item types.")
    return type_ids, character


def get_restocking_items(character_id, active_type_ids):
    """Return items from profit history that are NOT in active orders.

    Only includes items with net_profit > 0 in total.

    Returns:
        list of dicts: [{'type_id', 'type_name', 'qty_sold'}, ...]
    """
    conn = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        profit_table = f"character_profit_{character_id}"

        cursor.execute("""
            SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?
        """, (profit_table,))
        if cursor.fetchone()[0] == 0:
            return []

        cursor.execute(f"""
            SELECT
                p.type_id,
                COALESCE(t.typeName, CAST(p.type_id AS TEXT)) AS type_name,
                SUM(p.quantity) AS qty_sold
            FROM [{profit_table}] p
            LEFT JOIN types t ON t.typeID = p.type_id
            GROUP BY p.type_id
            HAVING SUM(p.net_profit) > 0
            ORDER BY qty_sold DESC
        """)

        rows = [dict(row) for row in cursor.fetchall()]

        if active_type_ids:
            rows = [r for r in rows if r['type_id'] not in active_type_ids]

        return rows

    except Exception as e:
        print(f"Error getting restocking items: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_prices_from_esi(region_id, type_ids, callback=None):
    """Fetch max buy / min sell prices directly from ESI for the given type_ids.

    Public endpoint - no authentication required.
    Uses concurrent requests (max 5 workers) to stay within ESI rate limits.

    Returns:
        dict: {type_id: {'buy_price': float|None, 'sell_price': float|None}}
    """
    def log(msg):
        if callback:
            callback(msg)

    type_ids = list(type_ids)
    if not type_ids:
        return {}

    def _fetch_one(type_id):
        url = f"{ESI_MARKETS_URL}/{region_id}/orders/"
        params = {'order_type': 'all', 'type_id': type_id, 'datasource': 'tranquility'}
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                orders = resp.json()
                buy_prices = [o['price'] for o in orders if o.get('is_buy_order')]
                sell_prices = [o['price'] for o in orders if not o.get('is_buy_order')]
                return type_id, {
                    'buy_price': max(buy_prices) if buy_prices else None,
                    'sell_price': min(sell_prices) if sell_prices else None,
                }
        except Exception as e:
            print(f"ESI price fetch error for type_id {type_id}: {e}")
        return type_id, {'buy_price': None, 'sell_price': None}

    log(f"Fetching prices for {len(type_ids)} items from ESI...")
    prices = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_fetch_one, tid): tid for tid in type_ids}
        done = 0
        for future in as_completed(futures):
            type_id, price_data = future.result()
            prices[type_id] = price_data
            done += 1
            log(f"Fetched {done}/{len(type_ids)}...")

    return prices


def calculate_profit(buy_price, sell_price, broker_fee_buy, broker_fee_sell, sales_tax):
    """Calculate taxes and net profit per unit.

    Returns:
        dict: {'taxes': float, 'profit_isk': float, 'profit_pct': float}
    """
    tax_buy = buy_price * (broker_fee_buy / 100.0)
    tax_sell = sell_price * (broker_fee_sell / 100.0)
    tax_sales = sell_price * (sales_tax / 100.0)
    taxes = tax_buy + tax_sell + tax_sales
    profit_isk = sell_price - buy_price - taxes
    profit_pct = (profit_isk / sell_price * 100.0) if sell_price else 0.0
    return {
        'taxes': taxes,
        'profit_isk': profit_isk,
        'profit_pct': profit_pct,
    }
