"""Database models and migrations"""
import sqlite3
import os
import importlib


def _get_db_path():
    """Reload and get DB_PATH from settings module"""
    import settings
    importlib.reload(settings)
    return settings.DB_PATH


def _get_connection():
    """Get a SQLite connection with row_factory set"""
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_tables():
    """Create necessary database tables if they don't exist"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # Create characters table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                character_id INTEGER PRIMARY KEY,
                character_name TEXT NOT NULL,
                character_portrait_url TEXT,
                access_token TEXT,
                refresh_token TEXT,
                token_expiry TEXT,
                broker_fee_sell REAL DEFAULT 3.00,
                broker_fee_buy REAL DEFAULT 3.00,
                sales_tax REAL DEFAULT 7.50,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        print("Table 'characters' created or already exists")

        # Create settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                value TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        print("Table 'settings' created or already exists")

        conn.commit()
        return True

    except Exception as e:
        print(f"Error while creating tables: {e}")
        return False
    finally:
        conn.close()


def get_setting(name, default=None):
    """Get a setting value from database"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE name = ?", (name,))
        result = cursor.fetchone()

        if result:
            return result[0]
        return default

    except Exception as e:
        print(f"Error while getting setting '{name}': {e}")
        return default
    finally:
        conn.close()


def save_setting(name, value):
    """Save a setting value to database"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO settings (name, value)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
        """, (name, value))

        conn.commit()
        return True

    except Exception as e:
        print(f"Error while saving setting '{name}': {e}")
        return False
    finally:
        conn.close()


def get_character(character_id):
    """Get character data from database"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT character_id, character_name, character_portrait_url,
                   broker_fee_sell, broker_fee_buy, sales_tax, access_token, refresh_token, token_expiry
            FROM characters
            WHERE character_id = ?
        """, (character_id,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    except Exception as e:
        print(f"Error while getting character {character_id}: {e}")
        return None
    finally:
        conn.close()


def save_character(character_data):
    """Save or update character data in database

    Args:
        character_data (dict): Dictionary with character information
            Required keys: character_id, character_name
            Optional keys: character_portrait_url, access_token, refresh_token,
                          token_expiry, broker_fee_sell, broker_fee_buy, sales_tax
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # Build dynamic query based on provided fields
        fields = ['character_id', 'character_name']
        values = [character_data['character_id'], character_data['character_name']]

        optional_fields = ['character_portrait_url', 'access_token', 'refresh_token',
                         'token_expiry', 'broker_fee_sell', 'broker_fee_buy', 'sales_tax']

        for field in optional_fields:
            if field in character_data:
                fields.append(field)
                values.append(character_data[field])

        # Create placeholders
        placeholders = ', '.join(['?'] * len(fields))
        fields_str = ', '.join(fields)

        # Create update part for ON CONFLICT
        update_parts = [f"{field} = excluded.{field}" for field in fields if field != 'character_id']
        update_str = ', '.join(update_parts)

        query = f"""
            INSERT INTO characters ({fields_str})
            VALUES ({placeholders})
            ON CONFLICT(character_id) DO UPDATE SET {update_str}, updated_at = datetime('now')
        """

        cursor.execute(query, values)
        conn.commit()
        return True

    except Exception as e:
        print(f"Error while saving character: {e}")
        return False
    finally:
        conn.close()


def get_current_character_id():
    """Get the currently logged-in character ID from settings"""
    character_id = get_setting('current_character_id')
    return int(character_id) if character_id else None


def create_character_history_table(character_id):
    """Create character order history table if it doesn't exist"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        table_name = f"character_history_{character_id}"

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS [{table_name}] (
                order_id INTEGER PRIMARY KEY,
                duration INTEGER NOT NULL,
                escrow REAL NOT NULL,
                is_buy_order INTEGER NOT NULL,
                is_corporation INTEGER NOT NULL,
                issued TEXT NOT NULL,
                location_id INTEGER NOT NULL,
                min_volume INTEGER NOT NULL,
                price REAL NOT NULL,
                range_type TEXT NOT NULL,
                region_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                type_id INTEGER NOT NULL,
                volume_remain INTEGER NOT NULL,
                volume_total INTEGER NOT NULL,
                volume_effective INTEGER NOT NULL,
                exhausted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_type_id ON [{table_name}] (type_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_issued ON [{table_name}] (issued)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_state ON [{table_name}] (state)")

        print(f"Table '{table_name}' created or already exists")

        conn.commit()
        return True

    except Exception as e:
        print(f"Error while creating character history table: {e}")
        return False
    finally:
        conn.close()


def create_character_inventory_table(character_id):
    """Create character inventory table if it doesn't exist"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        table_name = f"character_inventory_{character_id}"

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS [{table_name}] (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                purchase_price REAL NOT NULL,
                purchase_order_id INTEGER NOT NULL,
                purchase_date TEXT NOT NULL,
                broker_fee_buy REAL NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_type_id ON [{table_name}] (type_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_purchase_date ON [{table_name}] (purchase_date)")

        print(f"Table '{table_name}' created or already exists")

        conn.commit()
        return True

    except Exception as e:
        print(f"Error while creating character inventory table: {e}")
        return False
    finally:
        conn.close()


def create_character_profit_table(character_id):
    """Create character profit table if it doesn't exist"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        table_name = f"character_profit_{character_id}"

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS [{table_name}] (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_id INTEGER NOT NULL,
                sell_order_id INTEGER NOT NULL,
                sell_date TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                purchase_price REAL NOT NULL,
                sell_price REAL NOT NULL,
                broker_fee_buy REAL NOT NULL,
                broker_fee_sell REAL NOT NULL,
                sales_tax REAL NOT NULL,
                gross_profit REAL NOT NULL,
                net_profit REAL NOT NULL,
                purchase_order_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_type_id ON [{table_name}] (type_id)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_sell_date ON [{table_name}] (sell_date)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_sell_order_id ON [{table_name}] (sell_order_id)")

        print(f"Table '{table_name}' created or already exists")

        conn.commit()
        return True

    except Exception as e:
        print(f"Error while creating character profit table: {e}")
        return False
    finally:
        conn.close()


def save_character_order_history(character_id, orders):
    """Save character order history to database

    Args:
        character_id: Character ID
        orders: List of order dictionaries from ESI API

    Returns:
        tuple: (inserted_count, skipped_count)
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        table_name = f"character_history_{character_id}"
        inserted_count = 0
        skipped_count = 0

        for order in orders:
            try:
                cursor.execute(f"""
                    INSERT OR IGNORE INTO [{table_name}]
                    (order_id, duration, escrow, is_buy_order, is_corporation, issued,
                     location_id, min_volume, price, range_type, region_id, state,
                     type_id, volume_remain, volume_total, volume_effective)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order['order_id'],
                    order['duration'],
                    order.get('escrow', 0),
                    1 if order.get('is_buy_order', False) else 0,
                    1 if order['is_corporation'] else 0,
                    order['issued'],
                    order['location_id'],
                    order.get('min_volume', 0),
                    order['price'],
                    order['range'],
                    order['region_id'],
                    order['state'],
                    order['type_id'],
                    order['volume_remain'],
                    order['volume_total'],
                    int(order['volume_total']) - int(order['volume_remain'])
                ))

                if cursor.rowcount > 0:
                    inserted_count += 1
                else:
                    skipped_count += 1

            except Exception as e:
                print(f"Error inserting order {order.get('order_id')}: {e}")
                skipped_count += 1

        conn.commit()
        return (inserted_count, skipped_count)

    except Exception as e:
        print(f"Error while saving order history: {e}")
        return (0, 0)
    finally:
        conn.close()


def process_character_orders(character_id, broker_fee_buy_rate, broker_fee_sell_rate, sales_tax_rate):
    """Process character orders to calculate profits using FIFO method

    Args:
        character_id: Character ID
        broker_fee_buy_rate: Broker fee rate for buy orders (e.g., 3.00 for 3%)
        broker_fee_sell_rate: Broker fee rate for sell orders (e.g., 3.00 for 3%)
        sales_tax_rate: Sales tax rate (e.g., 7.50 for 7.5%)

    Returns:
        dict: Statistics about processed orders
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        history_table = f"character_history_{character_id}"
        inventory_table = f"character_inventory_{character_id}"
        profit_table = f"character_profit_{character_id}"

        stats = {
            'buy_orders_processed': 0,
            'sell_orders_processed': 0,
            'items_added_to_inventory': 0,
            'items_sold': 0,
            'items_sold_without_purchase': 0
        }

        # Get all unprocessed orders sorted by issued date (FIFO)
        cursor.execute(f"""
            SELECT * FROM [{history_table}]
            WHERE exhausted = 0
            ORDER BY issued ASC
        """)

        orders = [dict(row) for row in cursor.fetchall()]

        for order in orders:
            if order['is_buy_order']:
                # Process BUY order - add to inventory
                if order['volume_effective'] > 0:
                    broker_fee = float(order['price']) * order['volume_effective'] * (broker_fee_buy_rate / 100.0)

                    cursor.execute(f"""
                        INSERT INTO [{inventory_table}]
                        (type_id, quantity, purchase_price, purchase_order_id, purchase_date, broker_fee_buy)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        order['type_id'],
                        order['volume_effective'],
                        order['price'],
                        order['order_id'],
                        order['issued'],
                        broker_fee
                    ))

                    stats['items_added_to_inventory'] += order['volume_effective']
                    stats['buy_orders_processed'] += 1

            else:
                # Process SELL order - calculate profit using FIFO
                remaining_to_sell = order['volume_effective']

                if remaining_to_sell > 0:
                    # Get inventory items for this type_id, sorted by purchase date (FIFO)
                    cursor.execute(f"""
                        SELECT * FROM [{inventory_table}]
                        WHERE type_id = ?
                        ORDER BY purchase_date ASC, id ASC
                    """, (order['type_id'],))

                    inventory_items = [dict(row) for row in cursor.fetchall()]

                    for inv_item in inventory_items:
                        if remaining_to_sell <= 0:
                            break

                        # How much can we sell from this inventory item
                        qty_to_sell = min(remaining_to_sell, inv_item['quantity'])

                        # Calculate costs
                        cost_base = float(inv_item['purchase_price']) * qty_to_sell
                        cost_broker_buy = float(inv_item['broker_fee_buy']) * (qty_to_sell / inv_item['quantity'])
                        cost_total = cost_base + cost_broker_buy

                        # Calculate revenue
                        revenue_base = float(order['price']) * qty_to_sell
                        cost_broker_sell = revenue_base * (broker_fee_sell_rate / 100.0)
                        cost_sales_tax = revenue_base * (sales_tax_rate / 100.0)
                        revenue_net = revenue_base - cost_broker_sell - cost_sales_tax

                        # Calculate profit
                        gross_profit = revenue_base - cost_base
                        net_profit = revenue_net - cost_total

                        # Save profit record
                        cursor.execute(f"""
                            INSERT INTO [{profit_table}]
                            (type_id, sell_order_id, sell_date, quantity, purchase_price, sell_price,
                             broker_fee_buy, broker_fee_sell, sales_tax, gross_profit, net_profit, purchase_order_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            order['type_id'],
                            order['order_id'],
                            order['issued'],
                            qty_to_sell,
                            inv_item['purchase_price'],
                            order['price'],
                            cost_broker_buy,
                            cost_broker_sell,
                            cost_sales_tax,
                            gross_profit,
                            net_profit,
                            inv_item['purchase_order_id']
                        ))

                        # Update inventory
                        new_quantity = inv_item['quantity'] - qty_to_sell
                        if new_quantity > 0:
                            cursor.execute(f"""
                                UPDATE [{inventory_table}]
                                SET quantity = ?
                                WHERE id = ?
                            """, (new_quantity, inv_item['id']))
                        else:
                            cursor.execute(f"""
                                DELETE FROM [{inventory_table}]
                                WHERE id = ?
                            """, (inv_item['id'],))

                        remaining_to_sell -= qty_to_sell
                        stats['items_sold'] += qty_to_sell

                    # If we still have items to sell but no inventory (sold without purchase)
                    if remaining_to_sell > 0:
                        # Record with zero profit
                        revenue_base = float(order['price']) * remaining_to_sell
                        cost_broker_sell = revenue_base * (broker_fee_sell_rate / 100.0)
                        cost_sales_tax = revenue_base * (sales_tax_rate / 100.0)

                        cursor.execute(f"""
                            INSERT INTO [{profit_table}]
                            (type_id, sell_order_id, sell_date, quantity, purchase_price, sell_price,
                             broker_fee_buy, broker_fee_sell, sales_tax, gross_profit, net_profit, purchase_order_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            order['type_id'],
                            order['order_id'],
                            order['issued'],
                            remaining_to_sell,
                            0,
                            order['price'],
                            0,
                            cost_broker_sell,
                            cost_sales_tax,
                            0,
                            0,
                            None
                        ))

                        stats['items_sold_without_purchase'] += remaining_to_sell

                    stats['sell_orders_processed'] += 1

            # Mark order as processed
            cursor.execute(f"""
                UPDATE [{history_table}]
                SET exhausted = 1
                WHERE order_id = ?
            """, (order['order_id'],))

        conn.commit()
        return stats

    except Exception as e:
        print(f"Error while processing orders: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        conn.close()


def get_profit_by_months(character_id):
    """Get profit report aggregated by months"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        history_table = f"character_history_{character_id}"
        profit_table = f"character_profit_{character_id}"

        cursor.execute(f"""
            SELECT
                p.month,
                COALESCE(h.buy_orders, 0) as buy_orders,
                p.sell_orders,
                p.total_sales,
                p.total_taxes,
                p.total_profit
            FROM (
                SELECT
                    strftime('%Y-%m', sell_date) as month,
                    COUNT(DISTINCT sell_order_id) as sell_orders,
                    SUM(sell_price * quantity) as total_sales,
                    SUM(broker_fee_sell + sales_tax) as total_taxes,
                    SUM(net_profit) as total_profit
                FROM [{profit_table}]
                GROUP BY month
            ) p
            LEFT JOIN (
                SELECT
                    strftime('%Y-%m', issued) as month,
                    COUNT(DISTINCT order_id) as buy_orders
                FROM [{history_table}]
                WHERE is_buy_order = 1
                GROUP BY month
            ) h ON h.month = p.month
            ORDER BY p.month DESC
        """)

        return [dict(row) for row in cursor.fetchall()]

    except Exception as e:
        print(f"Error while getting profit by months: {e}")
        return []
    finally:
        conn.close()


def get_profit_by_days(character_id, date_from, date_to):
    """Get profit report aggregated by days for a date range"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        history_table = f"character_history_{character_id}"
        profit_table = f"character_profit_{character_id}"

        cursor.execute(f"""
            SELECT
                p.day,
                COALESCE(h.buy_orders, 0) as buy_orders,
                p.sell_orders,
                p.total_sales,
                p.total_taxes,
                p.total_profit
            FROM (
                SELECT
                    DATE(sell_date) as day,
                    COUNT(DISTINCT sell_order_id) as sell_orders,
                    SUM(sell_price * quantity) as total_sales,
                    SUM(broker_fee_sell + sales_tax) as total_taxes,
                    SUM(net_profit) as total_profit
                FROM [{profit_table}]
                WHERE DATE(sell_date) BETWEEN ? AND ?
                GROUP BY day
            ) p
            LEFT JOIN (
                SELECT
                    DATE(issued) as day,
                    COUNT(DISTINCT order_id) as buy_orders
                FROM [{history_table}]
                WHERE is_buy_order = 1
                    AND DATE(issued) BETWEEN ? AND ?
                GROUP BY day
            ) h ON h.day = p.day
            ORDER BY p.day DESC
        """, (date_from, date_to, date_from, date_to))

        return [dict(row) for row in cursor.fetchall()]

    except Exception as e:
        print(f"Error while getting profit by days: {e}")
        return []
    finally:
        conn.close()


def get_profit_by_items(character_id, date_from, date_to):
    """Get profit report aggregated by items for a date range"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        history_table = f"character_history_{character_id}"
        profit_table = f"character_profit_{character_id}"

        cursor.execute(f"""
            SELECT
                p.type_id,
                t.typeName as item_name,
                (SELECT COUNT(DISTINCT h2.order_id)
                 FROM [{history_table}] h2
                 WHERE h2.type_id = p.type_id
                   AND h2.is_buy_order = 1
                   AND DATE(h2.issued) BETWEEN ? AND ?) as buy_orders,
                COUNT(DISTINCT p.sell_order_id) as sell_orders,
                SUM(p.quantity) as quantity_sold,
                SUM(p.sell_price * p.quantity) as total_sales,
                SUM(p.broker_fee_sell + p.sales_tax) as total_taxes,
                SUM(p.net_profit) as total_profit
            FROM [{profit_table}] p
            LEFT JOIN types t ON t.typeID = p.type_id
            WHERE DATE(p.sell_date) BETWEEN ? AND ?
            GROUP BY p.type_id, t.typeName
            ORDER BY total_profit DESC
        """, (date_from, date_to, date_from, date_to))

        return [dict(row) for row in cursor.fetchall()]

    except Exception as e:
        print(f"Error while getting profit by items: {e}")
        return []
    finally:
        conn.close()


def get_last_buy_price(character_id, type_id):
    """Get last buy order price for a specific item type"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        table_name = f"character_history_{character_id}"

        cursor.execute(f"""
            SELECT price
            FROM [{table_name}]
            WHERE type_id = ? AND is_buy_order = 1
            ORDER BY issued DESC
            LIMIT 1
        """, (type_id,))

        result = cursor.fetchone()

        if result:
            return float(result[0])
        return None

    except Exception as e:
        print(f"Error while getting last buy price: {e}")
        return None
    finally:
        conn.close()
