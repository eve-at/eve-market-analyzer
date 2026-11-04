"""Hub trading handler: instant-buy in one trade hub, haul and place sell orders in another"""
import math
from datetime import datetime, timezone
from src.handlers.hub_hauling_handler import (
    _get_settings,
    _get_connection,
    _ensure_orders_index,
    _load_order_books,
    get_packaged_volumes,
    apply_limits,
    build_cargo_plan,
)
from src.handlers.market_history_handler import ensure_market_history, get_market_stats, HISTORY_DAYS
from src.handlers.fees import relist_rate, MIN_BROKER_FEE_ISK
from src.utils.price_calculator import get_next_sell_tick, calculate_tick_size


# Best ask above this multiple of the 30-day average trade price is treated as unrealistic
MAX_PRICE_OVER_AVERAGE = 1.5


# ---------------------------------------------------------------------------
# Pure calculation functions (no database access)
# ---------------------------------------------------------------------------

def choose_sell_price(best_ask, avg_price):
    """
    Price of our sell order: one tick below the best ask. If that is far above the
    recent volume-weighted average trade price (a lone absurdly priced order),
    the average price is used instead.

    Returns:
    tuple (sell_price, capped) - capped is True if the average price was used
    """
    undercut = get_next_sell_tick(best_ask)
    if avg_price is None or undercut <= avg_price * MAX_PRICE_OVER_AVERAGE:
        return undercut, False
    tick = calculate_tick_size(avg_price)
    return round(math.floor(avg_price / tick + 1e-9) * tick, 2), True


def sell_order_net_price(sell_price, tax_rate, broker_fee_rate, relist_rate_value, relists):
    """Net ISK per unit received from our sell order after sales tax, broker fee and relists"""
    return sell_price * (1 - tax_rate - broker_fee_rate - relists * relist_rate_value)


def build_sell_order_chunks(asks, sell_price, net_sell_price):
    """
    Source sell orders that are profitable to buy for reselling at net_sell_price

    Parameters:
    asks - list of (price, qty) sell orders in the source hub, any order
    sell_price - price of our sell order in the destination hub
    net_sell_price - net ISK per unit after all fees

    Returns:
    list of chunks (same format as match_order_books) with decreasing unit profit
    """
    chunks = []
    for price, qty in sorted(asks, key=lambda a: a[0]):
        if qty <= 0:
            continue
        if net_sell_price <= price:
            break
        chunks.append({
            'qty': qty,
            'buy_price': price,
            'sell_price': sell_price,
            'net_sell_price': net_sell_price,
            'unit_profit': net_sell_price - price,
        })
    return chunks


def fair_market_share(market_share_percent, competitors):
    """
    Share of daily volume we can expect: the user's share, but not more than an
    equal split with active competitors (sell orders updated in the last 2 days)
    """
    return min(market_share_percent, 100.0 / ((competitors or 0) + 1))


def demand_quantity(daily_volume, market_share_percent, max_days):
    """Units the destination market can absorb from us within max_days"""
    return int(math.floor(daily_volume * market_share_percent / 100.0 * max_days + 1e-9))


def days_to_sell(qty, daily_volume, market_share_percent):
    """Expected days to sell qty units at our market share"""
    daily_sales = daily_volume * market_share_percent / 100.0
    return qty / daily_sales if daily_sales > 0 else math.inf


def apply_min_broker_fee(row, sell_price, broker_fee_rate):
    """Charge at least MIN_BROKER_FEE_ISK broker fee for the order (mutates and returns row)"""
    broker_fee_isk = row['qty'] * sell_price * broker_fee_rate
    surcharge = max(MIN_BROKER_FEE_ISK - broker_fee_isk, 0) if row['qty'] > 0 else 0
    row['revenue'] -= surcharge
    row['profit'] -= surcharge
    row['margin'] = row['profit'] / row['investment'] * 100 if row['investment'] > 0 else 0.0
    return row


# ---------------------------------------------------------------------------
# Database / ESI operations
# ---------------------------------------------------------------------------

def _find_trading_candidates(cursor, src, dst, net_factor, market_group_ids):
    """Types whose best ask in src is below best ask in dst after fees, with dst market stats"""
    market_groups_join = ""
    market_groups_filter = ""

    # Competitors are counted relative to the orders snapshot time, not to now:
    # with orders fetched 2 days ago every order would look inactive
    cursor.execute(f"PRAGMA table_info([orders_{dst['region_id']}])")
    fetched_at = None
    if any(row[1] == 'fetched_at' for row in cursor.fetchall()):
        cursor.execute(f"SELECT MAX(fetched_at) FROM [orders_{dst['region_id']}]")
        fetched_at = cursor.fetchone()[0]
    # fetched_at is local time, issued is UTC (EVE time)
    snapshot = datetime.fromisoformat(fetched_at).astimezone(timezone.utc) if fetched_at else datetime.now(timezone.utc)

    params = [snapshot.strftime("%Y-%m-%d %H:%M:%S"), src['station_id'], dst['station_id'], net_factor]

    if market_group_ids:
        market_groups_join = "JOIN market_groups mg ON mg.marketGroupID = t.marketGroupID"
        placeholders = ', '.join(['?'] * len(market_group_ids))
        market_groups_filter = f"AND mg.topGroupID IN ({placeholders})"
        params.extend(market_group_ids)

    cursor.execute(f"""
        WITH snapshot AS (SELECT julianday(?) AS time),
        a AS (
            SELECT type_id, MIN(price) AS price
            FROM [orders_{src['region_id']}]
            WHERE location_id = ? AND is_buy_order = 0
            GROUP BY type_id
        ),
        d AS (
            SELECT type_id,
                MIN(CASE WHEN is_buy_order = 0 THEN price END) AS best_ask,
                MAX(CASE WHEN is_buy_order = 1 THEN price END) AS best_bid,
                COUNT(CASE WHEN is_buy_order = 0
                    AND (SELECT time FROM snapshot) - julianday(issued) < 2 THEN 1 END) AS competitors
            FROM [orders_{dst['region_id']}]
            WHERE location_id = ?
            GROUP BY type_id
        )
        SELECT a.type_id, t.typeName, t.volume, d.best_ask, d.best_bid, d.competitors
        FROM a
        JOIN d ON d.type_id = a.type_id
        JOIN types t ON t.typeID = a.type_id
        {market_groups_join}
        WHERE d.best_ask IS NOT NULL
            AND a.price < d.best_ask * ?
            {market_groups_filter}
    """, params)
    return [dict(row) for row in cursor.fetchall()]


def find_hub_trading_deals(hub_a, hub_b, cargo_m3, budget, max_cargo_value,
                           min_profit, min_margin, market_group_ids, sales_tax_percent,
                           broker_fee_percent_by_hub, advanced_broker_relations,
                           expected_relists, max_days, market_share_percent,
                           max_competitors=None, min_investment=0, max_plan_items=None, max_margin=None,
                           callback=None):
    """
    Find instant buy -> haul -> sell order deals between two hubs in both directions

    Parameters:
    hub_a, hub_b - hub dicts from resolve_hubs()
    cargo_m3, budget, max_cargo_value, min_profit, min_margin, market_group_ids - as in find_hub_deals
    sales_tax_percent - character sales tax, %
    broker_fee_percent_by_hub - {hub name: broker fee %} for placing orders in that hub
    advanced_broker_relations - skill level, used for relist fee
    expected_relists - expected number of price updates of our order
    max_days - max days to sell the whole batch
    market_share_percent - max share of destination daily volume we expect to sell;
                           lowered to an equal split with competitors (fair_market_share)
    max_competitors - skip items with more active competitors in the destination, None = no limit
    min_investment, max_plan_items, max_margin - as in find_hub_deals
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
        log(f"Finding trading deals {hub_a['name']} <-> {hub_b['name']}")
        log(f"Cargo: {cargo_m3:,.0f} m3, sales tax: {sales_tax_percent:.2f}%, "
            f"market share: {market_share_percent}%, max days: {max_days}, relists: {expected_relists}")
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

        history_days = ensure_market_history([hub_a['region_id'], hub_b['region_id']], log=log)
        log(f"Market history: {history_days}/{HISTORY_DAYS} day(s) available")
        if history_days == 0:
            log("Error: no market history available, can't estimate demand")
            return None
        log("")

        directions = [("A->B", hub_a, hub_b), ("B->A", hub_b, hub_a)]
        deals = []
        plans = {}

        for key, src, dst in directions:
            label = f"{src['name']} -> {dst['name']}"
            broker_fee_pct = broker_fee_percent_by_hub[dst['name']]
            broker_fee_rate = broker_fee_pct / 100.0
            relist = relist_rate(broker_fee_pct, advanced_broker_relations)
            net_factor = 1 - tax_rate - broker_fee_rate - expected_relists * relist
            log(f"[{label}] Broker fee in {dst['name']}: {broker_fee_pct:.3f}%, net after fees: {net_factor * 100:.2f}% of price")

            log(f"[{label}] Searching candidates...")
            candidates = _find_trading_candidates(cursor, src, dst, net_factor, market_group_ids)
            log(f"[{label}] Found {len(candidates)} candidate item(s)")

            type_ids = {c['type_id'] for c in candidates}
            asks = _load_order_books(cursor, src['region_id'], src['station_id'], 0, type_ids)
            market_stats = get_market_stats(dst['region_id'], type_ids)

            # Price our order one tick below the best ask (capped by recent trade prices)
            # and drop items without demand or better sold instantly
            priced = []
            for candidate in candidates:
                stats = market_stats.get(candidate['type_id'])
                if not stats:
                    continue
                if max_competitors is not None and candidate['competitors'] > max_competitors:
                    continue
                sell_price, price_capped = choose_sell_price(candidate['best_ask'], stats['avg_price'])
                net_sell_price = sell_order_net_price(sell_price, tax_rate, broker_fee_rate, relist, expected_relists)
                if candidate['best_bid'] and candidate['best_bid'] * (1 - tax_rate) >= net_sell_price:
                    continue
                chunks = build_sell_order_chunks(asks.get(candidate['type_id'], []), sell_price, net_sell_price)
                if chunks:
                    priced.append((candidate, sell_price, price_capped, stats, chunks))
            log(f"[{label}] {len(priced)} item(s) profitable after fees")

            volumes = get_packaged_volumes(
                conn, {c['type_id']: c['volume'] for c, _, _, _, _ in priced}, log
            )

            direction_deals = []
            for candidate, sell_price, price_capped, stats, chunks in priced:
                type_id = candidate['type_id']
                unit_volume = volumes.get(type_id)
                if not unit_volume or unit_volume <= 0:
                    continue
                daily_volume = stats['daily_volume']
                share = fair_market_share(market_share_percent, candidate['competitors'])
                max_qty = demand_quantity(daily_volume, share, max_days)
                if max_qty <= 0:
                    continue

                row = apply_limits(chunks, unit_volume, cargo_m3, budget, max_cargo_value, max_qty=max_qty)
                if row['qty'] == 0:
                    continue
                apply_min_broker_fee(row, sell_price, broker_fee_rate)
                if row['profit'] < min_profit or row['margin'] < min_margin or row['investment'] < min_investment:
                    continue
                if max_margin is not None and row['margin'] > max_margin:
                    continue

                row.update({
                    'direction': key,
                    'direction_label': label,
                    'type_id': type_id,
                    'typeName': candidate['typeName'],
                    'unit_volume': unit_volume,
                    'profit_per_m3': row['profit'] / row['volume'],
                    'market_chunks': chunks,
                    'max_qty': max_qty,
                    'sell_price': sell_price,
                    'price_capped': price_capped,
                    'avg_price_dst': stats['avg_price'],
                    'best_ask_dst': candidate['best_ask'],
                    'best_bid_dst': candidate['best_bid'],
                    'competitors': candidate['competitors'],
                    'daily_volume': daily_volume,
                    'market_share': share,
                    'days_to_sell': days_to_sell(row['qty'], daily_volume, share),
                    'fees': row['qty'] * sell_price - row['revenue'],
                })
                direction_deals.append(row)

            plan = build_cargo_plan(direction_deals, cargo_m3, budget, max_cargo_value,
                                    min_investment, max_plan_items)
            deal_by_type = {d['type_id']: d for d in direction_deals}
            for item in plan['items']:
                deal = deal_by_type[item['type_id']]
                item['days_to_sell'] = days_to_sell(item['qty'], deal['daily_volume'], deal['market_share'])
            plan['max_days_to_sell'] = max((i['days_to_sell'] for i in plan['items']), default=0)
            plan['direction_label'] = label
            plans[key] = plan

            log(f"[{label}] {len(direction_deals)} deal(s), cargo plan profit: {plan['profit']:,.0f} ISK")
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
