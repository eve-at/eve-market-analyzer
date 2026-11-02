"""Hub hauling handler: find items to instant-buy in one trade hub and instant-sell in another"""
import sqlite3
import os
import csv
import math
import importlib
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime


# Trade hubs (https://wiki.eveuniversity.org/Trade_hubs).
# Station IDs are resolved from the `stations` table by exact station name.
TRADE_HUBS = [
    ("Jita", "Jita IV - Moon 4 - Caldari Navy Assembly Plant"),
    ("Amarr", "Amarr VIII (Oris) - Emperor Family Academy"),
    ("Dodixie", "Dodixie IX - Moon 20 - Federation Navy Assembly Plant"),
    ("Rens", "Rens VI - Moon 8 - Brutor Tribe Treasury"),
    ("Hek", "Hek VIII - Moon 12 - Boundless Creation Factory"),
    ("Oursulaert", "Oursulaert III - Federation Navy Testing Facilities"),
    ("Tash-Murkon Prime", "Tash-Murkon Prime II - Moon 1 - Kaalakiota Corporation Factory"),
    ("Agil", "Agil VI - Moon 2 - CONCORD Logistic Support"),
]

LIMIT_MARKET = "market"
LIMIT_CARGO = "cargo"
LIMIT_BUDGET = "budget"
LIMIT_RISK = "risk"

# Float tolerance for volume / ISK comparisons
_EPS = 1e-6


def _get_settings():
    """Reload and get settings from settings module"""
    import settings
    importlib.reload(settings)
    return settings


def _get_connection(settings):
    """Get a SQLite connection"""
    db_path = settings.DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def resolve_hubs():
    """
    Resolve trade hub stations from the static `stations` table

    Returns:
    list of dicts with keys: name, station_name, station_id, solar_system_id,
    region_id, region_name. IDs are None if the station was not found.
    """
    settings = _get_settings()
    conn = None
    found = {}

    try:
        conn = _get_connection(settings)
        cursor = conn.cursor()
        placeholders = ', '.join(['?'] * len(TRADE_HUBS))
        cursor.execute(f"""
            SELECT s.stationID, s.stationName, s.solarSystemID, s.regionID, r.regionName
            FROM stations s
            LEFT JOIN regions r ON r.regionID = s.regionID
            WHERE s.stationName IN ({placeholders})
        """, [station_name for _, station_name in TRADE_HUBS])
        found = {row['stationName']: dict(row) for row in cursor.fetchall()}
    except Exception as e:
        print(f"Database error while resolving trade hubs: {e}")
    finally:
        if conn:
            conn.close()

    hubs = []
    for name, station_name in TRADE_HUBS:
        row = found.get(station_name)
        hubs.append({
            'name': name,
            'station_name': station_name,
            'station_id': row['stationID'] if row else None,
            'solar_system_id': row['solarSystemID'] if row else None,
            'region_id': row['regionID'] if row else None,
            'region_name': row['regionName'] if row else None,
        })
    return hubs


def get_orders_status(region_id):
    """
    Get orders table status for a region

    Returns:
    tuple (count, fetched_at) - count is -1 if table doesn't exist,
    fetched_at is a datetime or None
    """
    settings = _get_settings()
    conn = None
    table_name = f"orders_{region_id}"

    try:
        conn = _get_connection(settings)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?
        """, (table_name,))
        if cursor.fetchone()[0] == 0:
            return -1, None

        # Tables created before the fetched_at column was introduced don't have it
        cursor.execute(f"PRAGMA table_info([{table_name}])")
        has_fetched_at = any(row[1] == 'fetched_at' for row in cursor.fetchall())
        if has_fetched_at:
            cursor.execute(f"SELECT COUNT(*), MAX(fetched_at) FROM [{table_name}]")
            count, fetched_at = cursor.fetchone()
        else:
            cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            count, fetched_at = cursor.fetchone()[0], None
        fetched_dt = None
        if fetched_at:
            try:
                fetched_dt = datetime.fromisoformat(fetched_at)
            except ValueError:
                pass
        return count, fetched_dt

    except Exception as e:
        print(f"Database error: {e}")
        return -1, None
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Pure calculation functions (no database access)
# ---------------------------------------------------------------------------

def match_order_books(asks, bids, tax_rate):
    """
    Match source sell orders against destination buy orders while profitable

    Parameters:
    asks - list of (price, qty) sell orders in the source hub, any order
    bids - list of (price, qty, min_volume) buy orders in the destination hub, any order
    tax_rate - sales tax as a fraction (0.075 for 7.5%)

    Returns:
    list of chunks with decreasing unit profit. Each chunk is a dict:
    qty, buy_price, sell_price, net_sell_price, unit_profit
    """
    asks = sorted([[price, qty] for price, qty in asks if qty > 0], key=lambda a: a[0])
    bids = sorted([[price, qty, max(min_volume or 1, 1)] for price, qty, min_volume in bids if qty > 0],
                  key=lambda b: -b[0])

    chunks = []
    ai = 0
    bi = 0
    bid_filled = 0  # Units already sold into the current bid

    while ai < len(asks) and bi < len(bids):
        ask_price, ask_qty = asks[ai]
        bid_price, bid_qty, min_volume = bids[bi]
        net_bid = bid_price * (1 - tax_rate)

        if net_bid <= ask_price:
            break

        # A bid with min_volume is only usable if enough profitable asks remain to satisfy it
        if bid_filled == 0 and min_volume > 1:
            needed = min(min_volume, bid_qty)
            available = ask_qty
            j = ai + 1
            while available < needed and j < len(asks) and asks[j][0] < net_bid:
                available += asks[j][1]
                j += 1
            if available < needed:
                bi += 1
                continue

        q = min(ask_qty, bid_qty)
        chunks.append({
            'qty': q,
            'buy_price': ask_price,
            'sell_price': bid_price,
            'net_sell_price': net_bid,
            'unit_profit': net_bid - ask_price,
        })

        asks[ai][1] -= q
        bids[bi][1] -= q
        bid_filled += q
        if asks[ai][1] == 0:
            ai += 1
        if bids[bi][1] == 0:
            bi += 1
            bid_filled = 0

    return chunks


def _max_units(remaining, unit_cost):
    """How many whole units fit into the remaining resource (inf if unlimited)"""
    if remaining is None:
        return math.inf
    if unit_cost <= 0:
        return math.inf
    return max(int(math.floor(remaining / unit_cost + _EPS)), 0)


def _summarize(taken):
    """Aggregate taken chunks into totals"""
    qty = sum(c['qty'] for c in taken)
    investment = sum(c['qty'] * c['buy_price'] for c in taken)
    revenue = sum(c['qty'] * c['net_sell_price'] for c in taken)
    profit = revenue - investment
    return {
        'qty': qty,
        'investment': investment,
        'revenue': revenue,
        'profit': profit,
        'margin': profit / investment * 100 if investment > 0 else 0.0,
        'max_buy_price': max((c['buy_price'] for c in taken), default=None),
        'min_sell_price': min((c['sell_price'] for c in taken), default=None),
    }


def apply_limits(chunks, unit_volume, cargo_m3, budget=None, max_cargo_value=None):
    """
    Take chunks in order until the first limit is hit (the last chunk may be cut)

    Parameters:
    chunks - output of match_order_books
    unit_volume - packaged volume of one unit, m3
    cargo_m3 - ship cargo capacity, m3
    budget - max ISK to spend, None = unlimited
    max_cargo_value - max ISK value of cargo on board, None = unlimited

    Returns:
    dict with qty, investment, revenue, profit, margin, max_buy_price,
    min_sell_price, volume, limited_by, chunks (taken chunks)
    """
    taken = []
    used_m3 = 0.0
    spent = 0.0
    limited_by = LIMIT_MARKET

    for chunk in chunks:
        price = chunk['buy_price']
        caps = [
            (LIMIT_CARGO, _max_units(cargo_m3 - used_m3, unit_volume)),
            (LIMIT_BUDGET, _max_units(None if budget is None else budget - spent, price)),
            (LIMIT_RISK, _max_units(None if max_cargo_value is None else max_cargo_value - spent, price)),
        ]
        limit_name, limit_units = min(caps, key=lambda c: c[1])
        q = min(chunk['qty'], limit_units)

        if q > 0:
            taken.append({**chunk, 'qty': q})
            used_m3 += q * unit_volume
            spent += q * price

        if q < chunk['qty']:
            limited_by = limit_name
            break

    result = _summarize(taken)
    result['volume'] = result['qty'] * unit_volume
    result['limited_by'] = limited_by
    result['chunks'] = taken
    return result


def build_cargo_plan(deals, cargo_m3, budget=None, max_cargo_value=None):
    """
    Greedy two-resource knapsack (m3 and ISK) over market chunks of all deals

    Parameters:
    deals - list of dicts with keys type_id, typeName, unit_volume, market_chunks
    cargo_m3, budget, max_cargo_value - limits as in apply_limits

    Returns:
    dict with items (list), volume, investment, revenue, profit, margin
    """
    caps = [c for c in (budget, max_cargo_value) if c is not None]
    isk_cap = min(caps) if caps else None

    candidates = []
    for deal in deals:
        unit_volume = deal['unit_volume']
        for chunk in deal['market_chunks']:
            volume_share = unit_volume / cargo_m3
            isk_share = chunk['buy_price'] / isk_cap if isk_cap else 0.0
            weight = max(volume_share, isk_share)
            density = chunk['unit_profit'] / weight if weight > 0 else math.inf
            candidates.append((density, deal, chunk))

    # Stable sort keeps chunks of one item in their original (decreasing profit) order on ties
    candidates.sort(key=lambda c: -c[0])

    used_m3 = 0.0
    spent = 0.0
    by_type = {}

    for _, deal, chunk in candidates:
        q = min(
            chunk['qty'],
            _max_units(cargo_m3 - used_m3, deal['unit_volume']),
            _max_units(None if isk_cap is None else isk_cap - spent, chunk['buy_price']),
        )
        if q <= 0:
            continue
        used_m3 += q * deal['unit_volume']
        spent += q * chunk['buy_price']
        entry = by_type.setdefault(deal['type_id'], {'deal': deal, 'chunks': []})
        entry['chunks'].append({**chunk, 'qty': q})

    items = []
    for type_id, entry in by_type.items():
        item = _summarize(entry['chunks'])
        item['type_id'] = type_id
        item['typeName'] = entry['deal']['typeName']
        item['volume'] = item['qty'] * entry['deal']['unit_volume']
        items.append(item)
    items.sort(key=lambda i: -i['profit'])

    totals = _summarize([c for entry in by_type.values() for c in entry['chunks']])
    return {
        'items': items,
        'volume': used_m3,
        'investment': totals['investment'],
        'revenue': totals['revenue'],
        'profit': totals['profit'],
        'margin': totals['margin'],
    }


def format_multibuy(items):
    """Format plan items for the EVE Multibuy window: '<typeName> <qty>' per line"""
    return "\n".join(f"{item['typeName']} {item['qty']}" for item in items)


# ---------------------------------------------------------------------------
# Database / ESI operations
# ---------------------------------------------------------------------------

def _fetch_packaged_volume(type_id):
    """Fetch packaged volume for a type from ESI, None on failure"""
    try:
        response = requests.get(
            f"https://esi.evetech.net/latest/universe/types/{type_id}/?datasource=tranquility",
            timeout=10
        )
        if response.status_code != 200:
            return None
        data = response.json()
        return data.get('packaged_volume', data.get('volume'))
    except requests.exceptions.RequestException:
        return None


def get_packaged_volumes(conn, type_volumes, log):
    """
    Get packaged volumes for types, using the type_packaged_volume cache and ESI

    Parameters:
    conn - SQLite connection
    type_volumes - dict {type_id: types.volume} used as fallback
    log - logging function

    Returns:
    dict {type_id: packaged volume}
    """
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS type_packaged_volume (
            type_id INTEGER PRIMARY KEY,
            packaged_volume REAL NOT NULL,
            fetched_at TEXT NOT NULL
        )
    """)

    volumes = {}
    cursor.execute("SELECT type_id, packaged_volume FROM type_packaged_volume")
    for row in cursor.fetchall():
        if row[0] in type_volumes:
            volumes[row[0]] = row[1]

    missing = [type_id for type_id in type_volumes if type_id not in volumes]
    if missing:
        log(f"Fetching packaged volume for {len(missing)} item(s) from ESI...")
        with ThreadPoolExecutor(max_workers=8) as executor:
            fetched = list(executor.map(_fetch_packaged_volume, missing))

        now_iso = datetime.now().isoformat()
        failed = 0
        for type_id, volume in zip(missing, fetched):
            if volume is None:
                failed += 1
                volumes[type_id] = type_volumes[type_id]
                continue
            volumes[type_id] = volume
            cursor.execute("""
                INSERT OR REPLACE INTO type_packaged_volume (type_id, packaged_volume, fetched_at)
                VALUES (?, ?, ?)
            """, (type_id, volume, now_iso))
        conn.commit()
        if failed:
            log(f"  Warning: ESI failed for {failed} item(s), using unpackaged volume from static data")

    return volumes


def _ensure_orders_index(cursor, region_id):
    """Create index for hub order lookups if not exists"""
    cursor.execute(f"""
        CREATE INDEX IF NOT EXISTS [idx_orders_{region_id}_location]
        ON [orders_{region_id}] (location_id, is_buy_order, type_id)
    """)


def _load_order_books(cursor, region_id, station_id, is_buy_order, type_ids):
    """Load orders at a station grouped by type_id for the given types"""
    cursor.execute(f"""
        SELECT type_id, price, volume_remain, min_volume
        FROM [orders_{region_id}]
        WHERE location_id = ? AND is_buy_order = ?
    """, (station_id, is_buy_order))
    books = {}
    for type_id, price, volume_remain, min_volume in cursor.fetchall():
        if type_id not in type_ids:
            continue
        if is_buy_order:
            books.setdefault(type_id, []).append((price, volume_remain, min_volume))
        else:
            books.setdefault(type_id, []).append((price, volume_remain))
    return books


def _find_candidates(cursor, src, dst, tax_rate, market_group_ids):
    """Find types whose best ask in src is below best net bid in dst"""
    market_groups_join = ""
    market_groups_filter = ""
    params = [src['station_id'], dst['station_id'], 1 - tax_rate]

    if market_group_ids:
        market_groups_join = "JOIN market_groups mg ON mg.marketGroupID = t.marketGroupID"
        placeholders = ', '.join(['?'] * len(market_group_ids))
        market_groups_filter = f"AND mg.topGroupID IN ({placeholders})"
        params.extend(market_group_ids)

    cursor.execute(f"""
        WITH a AS (
            SELECT type_id, MIN(price) AS price
            FROM [orders_{src['region_id']}]
            WHERE location_id = ? AND is_buy_order = 0
            GROUP BY type_id
        ),
        b AS (
            SELECT type_id, MAX(price) AS price
            FROM [orders_{dst['region_id']}]
            WHERE location_id = ? AND is_buy_order = 1
            GROUP BY type_id
        )
        SELECT a.type_id, t.typeName, t.volume
        FROM a
        JOIN b ON b.type_id = a.type_id
        JOIN types t ON t.typeID = a.type_id
        {market_groups_join}
        WHERE a.price < b.price * ?
            {market_groups_filter}
    """, params)
    return [dict(row) for row in cursor.fetchall()]


def find_hub_deals(hub_a, hub_b, cargo_m3, budget, max_cargo_value,
                   min_profit, min_margin, market_group_ids, sales_tax_percent,
                   callback=None):
    """
    Find instant buy -> haul -> instant sell deals between two hubs in both directions

    Parameters:
    hub_a, hub_b - hub dicts from resolve_hubs()
    cargo_m3 - ship cargo capacity, m3
    budget, max_cargo_value - ISK limits, None = unlimited
    min_profit - min profit per deal row, ISK
    min_margin - min margin per deal row, %
    market_group_ids - list of top market group IDs, empty = all
    sales_tax_percent - character sales tax, % (7.5 for 7.5%)
    callback - optional callback function for progress messages

    Returns:
    dict {"deals": [...], "plans": {"A->B": plan, "B->A": plan}} or None on error
    """

    def log(message):
        """Helper to log message to console and callback"""
        print(message)
        if callback:
            callback(message)

    settings = _get_settings()
    conn = None
    tax_rate = sales_tax_percent / 100.0

    try:
        log("=" * 60)
        log(f"Finding hauling deals {hub_a['name']} <-> {hub_b['name']}")
        log(f"Cargo: {cargo_m3:,.0f} m3, sales tax: {sales_tax_percent:.2f}%")
        log("=" * 60)
        log("")

        conn = _get_connection(settings)
        cursor = conn.cursor()

        for region_id in {hub_a['region_id'], hub_b['region_id']}:
            cursor.execute("""
                SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?
            """, (f"orders_{region_id}",))
            if cursor.fetchone()[0] == 0:
                log(f"Error: Orders table orders_{region_id} doesn't exist")
                log("Please click 'Update Orders' first")
                return None
            _ensure_orders_index(cursor, region_id)
        conn.commit()

        directions = [("A->B", hub_a, hub_b), ("B->A", hub_b, hub_a)]
        deals = []
        plans = {}

        for key, src, dst in directions:
            label = f"{src['name']} -> {dst['name']}"
            log(f"[{label}] Searching candidates...")
            candidates = _find_candidates(cursor, src, dst, tax_rate, market_group_ids)
            log(f"[{label}] Found {len(candidates)} candidate item(s)")

            type_ids = {c['type_id'] for c in candidates}
            asks = _load_order_books(cursor, src['region_id'], src['station_id'], 0, type_ids)
            bids = _load_order_books(cursor, dst['region_id'], dst['station_id'], 1, type_ids)

            volumes = get_packaged_volumes(
                conn, {c['type_id']: c['volume'] for c in candidates}, log
            )

            direction_deals = []
            for candidate in candidates:
                type_id = candidate['type_id']
                unit_volume = volumes.get(type_id)
                if not unit_volume or unit_volume <= 0:
                    continue

                market_chunks = match_order_books(asks.get(type_id, []), bids.get(type_id, []), tax_rate)
                if not market_chunks:
                    continue

                row = apply_limits(market_chunks, unit_volume, cargo_m3, budget, max_cargo_value)
                if row['qty'] == 0 or row['profit'] < min_profit or row['margin'] < min_margin:
                    continue

                row.update({
                    'direction': key,
                    'direction_label': label,
                    'type_id': type_id,
                    'typeName': candidate['typeName'],
                    'unit_volume': unit_volume,
                    'profit_per_m3': row['profit'] / row['volume'],
                    'market_chunks': market_chunks,
                })
                direction_deals.append(row)

            plans[key] = build_cargo_plan(direction_deals, cargo_m3, budget, max_cargo_value)
            plans[key]['direction_label'] = label
            log(f"[{label}] {len(direction_deals)} deal(s), cargo plan profit: {plans[key]['profit']:,.0f} ISK")
            log("")
            deals.extend(direction_deals)

        log("=" * 60)
        log(f"Found {len(deals)} deals")
        log("=" * 60)

        return {'deals': deals, 'plans': plans}

    except Exception as e:
        log(f"Database error: {e}")
        return None
    finally:
        if conn:
            conn.close()


def export_deals_to_csv(deals, callback=None):
    """
    Export hauling deals to CSV file

    Returns:
    str - file path, or None on error
    """

    def log(message):
        """Helper to log message to console and callback"""
        print(message)
        if callback:
            callback(message)

    try:
        from src.database.models import get_setting

        csv_export_path = get_setting('csv_export_path', 'data')
        os.makedirs(csv_export_path, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(csv_export_path, f"hub_hauling_{timestamp}.csv")

        log(f"Writing {len(deals)} deals to {filepath}...")

        fieldnames = ['direction_label', 'type_id', 'typeName', 'qty', 'volume', 'max_buy_price',
                      'min_sell_price', 'investment', 'revenue', 'profit', 'margin',
                      'profit_per_m3', 'limited_by']
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for deal in deals:
                writer.writerow(deal)

        log(f"Successfully exported to {os.path.basename(filepath)}")
        return filepath

    except Exception as e:
        log(f"Export error: {e}")
        return None
