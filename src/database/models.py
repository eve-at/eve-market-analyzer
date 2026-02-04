"""Database models and migrations"""
import mysql.connector
from mysql.connector import Error
import importlib


def _get_db_config():
    """Reload and get DB_CONFIG from settings module"""
    import settings
    importlib.reload(settings)
    return settings.DB_CONFIG


def create_tables():
    """Create necessary database tables if they don't exist"""
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            # Create characters table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS characters (
                    character_id BIGINT PRIMARY KEY,
                    character_name VARCHAR(255) NOT NULL,
                    character_portrait_url VARCHAR(512),
                    access_token TEXT,
                    refresh_token TEXT,
                    token_expiry DATETIME,
                    broker_fee_sell DECIMAL(5,2) DEFAULT 3.00,
                    broker_fee_buy DECIMAL(5,2) DEFAULT 3.00,
                    sales_tax DECIMAL(5,2) DEFAULT 7.50,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            print("Table 'characters' created or already exists")

            # Create settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            print("Table 'settings' created or already exists")

            connection.commit()
            return True

    except Error as e:
        print(f"Database error while creating tables: {e}")
        return False
    except Exception as e:
        print(f"Error while creating tables: {e}")
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def get_setting(name, default=None):
    """Get a setting value from database"""
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute("SELECT value FROM settings WHERE name = %s", (name,))
            result = cursor.fetchone()

            if result:
                return result[0]
            return default

    except Error as e:
        print(f"Database error while getting setting '{name}': {e}")
        return default
    except Exception as e:
        print(f"Error while getting setting '{name}': {e}")
        return default
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def save_setting(name, value):
    """Save a setting value to database"""
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            # Use INSERT ... ON DUPLICATE KEY UPDATE for upsert
            cursor.execute("""
                INSERT INTO settings (name, value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE value = %s, updated_at = CURRENT_TIMESTAMP
            """, (name, value, value))

            connection.commit()
            return True

    except Error as e:
        print(f"Database error while saving setting '{name}': {e}")
        return False
    except Exception as e:
        print(f"Error while saving setting '{name}': {e}")
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def get_character(character_id):
    """Get character data from database"""
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT character_id, character_name, character_portrait_url,
                       broker_fee_sell, broker_fee_buy, sales_tax, access_token, refresh_token, token_expiry
                FROM characters
                WHERE character_id = %s
            """, (character_id,))

            return cursor.fetchone()

    except Error as e:
        print(f"Database error while getting character {character_id}: {e}")
        return None
    except Exception as e:
        print(f"Error while getting character {character_id}: {e}")
        return None
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def save_character(character_data):
    """Save or update character data in database

    Args:
        character_data (dict): Dictionary with character information
            Required keys: character_id, character_name
            Optional keys: character_portrait_url, access_token, refresh_token,
                          token_expiry, broker_fee_sell, broker_fee_buy, sales_tax
    """
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

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
            placeholders = ', '.join(['%s'] * len(fields))
            fields_str = ', '.join(fields)

            # Create update part for ON DUPLICATE KEY
            update_parts = [f"{field} = VALUES({field})" for field in fields if field != 'character_id']
            update_str = ', '.join(update_parts)

            query = f"""
                INSERT INTO characters ({fields_str})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE {update_str}, updated_at = CURRENT_TIMESTAMP
            """

            cursor.execute(query, values)
            connection.commit()
            return True

    except Error as e:
        print(f"Database error while saving character: {e}")
        return False
    except Exception as e:
        print(f"Error while saving character: {e}")
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def get_current_character_id():
    """Get the currently logged-in character ID from settings"""
    character_id = get_setting('current_character_id')
    return int(character_id) if character_id else None


def create_character_history_table(character_id):
    """Create character order history table if it doesn't exist

    Args:
        character_id: Character ID to create history table for

    Returns:
        bool: True if successful, False otherwise
    """
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            table_name = f"character_history_{character_id}"

            # Create character history table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS `{table_name}` (
                    order_id BIGINT PRIMARY KEY,
                    duration INT NOT NULL,
                    escrow DECIMAL(20,2) NOT NULL,
                    is_buy_order BOOLEAN NOT NULL,
                    is_corporation BOOLEAN NOT NULL,
                    issued DATETIME NOT NULL,
                    location_id BIGINT NOT NULL,
                    min_volume INT NOT NULL,
                    price DECIMAL(20,2) NOT NULL,
                    range_type VARCHAR(50) NOT NULL,
                    region_id INT NOT NULL,
                    state VARCHAR(50) NOT NULL,
                    type_id INT NOT NULL,
                    volume_remain INT NOT NULL,
                    volume_total INT NOT NULL,

                    volume_effective INT NOT NULL,
                    exhausted BOOLEAN NOT NULL DEFAULT FALSE,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_type_id (type_id),
                    INDEX idx_issued (issued),
                    INDEX idx_state (state)
                )
            """)
            print(f"Table '{table_name}' created or already exists")

            connection.commit()
            return True

    except Error as e:
        print(f"Database error while creating character history table: {e}")
        return False
    except Exception as e:
        print(f"Error while creating character history table: {e}")
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def create_character_inventory_table(character_id):
    """Create character inventory table if it doesn't exist

    Args:
        character_id: Character ID to create inventory table for

    Returns:
        bool: True if successful, False otherwise
    """
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            table_name = f"character_inventory_{character_id}"

            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS `{table_name}` (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    type_id INT NOT NULL,
                    quantity INT NOT NULL,
                    purchase_price DECIMAL(20,2) NOT NULL,
                    purchase_order_id BIGINT NOT NULL,
                    purchase_date DATETIME NOT NULL,
                    broker_fee_buy DECIMAL(20,2) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_type_id (type_id),
                    INDEX idx_purchase_date (purchase_date)
                )
            """)
            print(f"Table '{table_name}' created or already exists")

            connection.commit()
            return True

    except Error as e:
        print(f"Database error while creating character inventory table: {e}")
        return False
    except Exception as e:
        print(f"Error while creating character inventory table: {e}")
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def create_character_profit_table(character_id):
    """Create character profit table if it doesn't exist

    Args:
        character_id: Character ID to create profit table for

    Returns:
        bool: True if successful, False otherwise
    """
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            table_name = f"character_profit_{character_id}"

            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS `{table_name}` (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    type_id INT NOT NULL,
                    sell_order_id BIGINT NOT NULL,
                    sell_date DATETIME NOT NULL,
                    quantity INT NOT NULL,
                    purchase_price DECIMAL(20,2) NOT NULL,
                    sell_price DECIMAL(20,2) NOT NULL,
                    broker_fee_buy DECIMAL(20,2) NOT NULL,
                    broker_fee_sell DECIMAL(20,2) NOT NULL,
                    sales_tax DECIMAL(20,2) NOT NULL,
                    gross_profit DECIMAL(20,2) NOT NULL,
                    net_profit DECIMAL(20,2) NOT NULL,
                    purchase_order_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_type_id (type_id),
                    INDEX idx_sell_date (sell_date),
                    INDEX idx_sell_order_id (sell_order_id)
                )
            """)
            print(f"Table '{table_name}' created or already exists")

            connection.commit()
            return True

    except Error as e:
        print(f"Database error while creating character profit table: {e}")
        return False
    except Exception as e:
        print(f"Error while creating character profit table: {e}")
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def save_character_order_history(character_id, orders):
    """Save character order history to database

    Args:
        character_id: Character ID
        orders: List of order dictionaries from ESI API

    Returns:
        tuple: (inserted_count, skipped_count)
    """
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            table_name = f"character_history_{character_id}"
            inserted_count = 0
            skipped_count = 0

            for order in orders:
                try:
                    # Use INSERT IGNORE to skip duplicates
                    # Set default values for optional fields
                    cursor.execute(f"""
                        INSERT IGNORE INTO `{table_name}`
                        (order_id, duration, escrow, is_buy_order, is_corporation, issued,
                         location_id, min_volume, price, range_type, region_id, state,
                         type_id, volume_remain, volume_total, volume_effective)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        order['order_id'],
                        order['duration'],
                        order.get('escrow', 0),  # Default to 0 if missing
                        order.get('is_buy_order', False),  # Default to False if missing
                        order['is_corporation'],
                        order['issued'],
                        order['location_id'],
                        order.get('min_volume', 0),  # Default to 0 if missing
                        order['price'],
                        order['range'],
                        order['region_id'],
                        order['state'],
                        order['type_id'],
                        order['volume_remain'],
                        order['volume_total'],
                        int(order['volume_total']) - int(order['volume_remain'])
                    ))

                    # Check if row was inserted
                    if cursor.rowcount > 0:
                        inserted_count += 1
                    else:
                        skipped_count += 1

                except Error as e:
                    print(f"Error inserting order {order.get('order_id')}: {e}")
                    skipped_count += 1

            connection.commit()
            return (inserted_count, skipped_count)

    except Error as e:
        print(f"Database error while saving order history: {e}")
        return (0, 0)
    except Exception as e:
        print(f"Error while saving order history: {e}")
        return (0, 0)
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


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
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)

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
                SELECT * FROM `{history_table}`
                WHERE exhausted = 0
                ORDER BY issued ASC
            """)

            orders = cursor.fetchall()

            for order in orders:
                if order['is_buy_order']:
                    # Process BUY order - add to inventory
                    if order['volume_effective'] > 0:
                        broker_fee = float(order['price']) * order['volume_effective'] * (broker_fee_buy_rate / 100.0)

                        cursor.execute(f"""
                            INSERT INTO `{inventory_table}`
                            (type_id, quantity, purchase_price, purchase_order_id, purchase_date, broker_fee_buy)
                            VALUES (%s, %s, %s, %s, %s, %s)
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
                            SELECT * FROM `{inventory_table}`
                            WHERE type_id = %s
                            ORDER BY purchase_date ASC, id ASC
                        """, (order['type_id'],))

                        inventory_items = cursor.fetchall()

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
                                INSERT INTO `{profit_table}`
                                (type_id, sell_order_id, sell_date, quantity, purchase_price, sell_price,
                                 broker_fee_buy, broker_fee_sell, sales_tax, gross_profit, net_profit, purchase_order_id)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                                    UPDATE `{inventory_table}`
                                    SET quantity = %s
                                    WHERE id = %s
                                """, (new_quantity, inv_item['id']))
                            else:
                                cursor.execute(f"""
                                    DELETE FROM `{inventory_table}`
                                    WHERE id = %s
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
                                INSERT INTO `{profit_table}`
                                (type_id, sell_order_id, sell_date, quantity, purchase_price, sell_price,
                                 broker_fee_buy, broker_fee_sell, sales_tax, gross_profit, net_profit, purchase_order_id)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                order['type_id'],
                                order['order_id'],
                                order['issued'],
                                remaining_to_sell,
                                0,  # No purchase price
                                order['price'],
                                0,  # No buy broker fee
                                cost_broker_sell,
                                cost_sales_tax,
                                0,  # Zero gross profit
                                0,  # Zero net profit
                                None  # No purchase order
                            ))

                            stats['items_sold_without_purchase'] += remaining_to_sell

                        stats['sell_orders_processed'] += 1

                # Mark order as processed
                cursor.execute(f"""
                    UPDATE `{history_table}`
                    SET exhausted = 1
                    WHERE order_id = %s
                """, (order['order_id'],))

            connection.commit()
            return stats

    except Error as e:
        print(f"Database error while processing orders: {e}")
        if connection:
            connection.rollback()
        return None
    except Exception as e:
        print(f"Error while processing orders: {e}")
        if connection:
            connection.rollback()
        return None
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def get_profit_by_months(character_id):
    """Get profit report aggregated by months

    Args:
        character_id: Character ID

    Returns:
        list: List of dicts with monthly profit data
    """
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)

            history_table = f"character_history_{character_id}"
            profit_table = f"character_profit_{character_id}"

            # Get monthly aggregated data
            # Use separate subqueries to avoid JOIN multiplication issue
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
                        DATE_FORMAT(sell_date, '%Y-%m') as month,
                        COUNT(DISTINCT sell_order_id) as sell_orders,
                        SUM(sell_price * quantity) as total_sales,
                        SUM(broker_fee_sell + sales_tax) as total_taxes,
                        SUM(net_profit) as total_profit
                    FROM `{profit_table}`
                    GROUP BY month
                ) p
                LEFT JOIN (
                    SELECT
                        DATE_FORMAT(issued, '%Y-%m') as month,
                        COUNT(DISTINCT order_id) as buy_orders
                    FROM `{history_table}`
                    WHERE is_buy_order = 1
                    GROUP BY month
                ) h ON h.month = p.month
                ORDER BY p.month DESC
            """)

            return cursor.fetchall()

    except Error as e:
        print(f"Database error while getting profit by months: {e}")
        return []
    except Exception as e:
        print(f"Error while getting profit by months: {e}")
        return []
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def get_profit_by_days(character_id, date_from, date_to):
    """Get profit report aggregated by days for a date range

    Args:
        character_id: Character ID
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)

    Returns:
        list: List of dicts with daily profit data
    """
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)

            history_table = f"character_history_{character_id}"
            profit_table = f"character_profit_{character_id}"

            # Use separate subqueries to avoid JOIN multiplication issue
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
                    FROM `{profit_table}`
                    WHERE DATE(sell_date) BETWEEN %s AND %s
                    GROUP BY day
                ) p
                LEFT JOIN (
                    SELECT
                        DATE(issued) as day,
                        COUNT(DISTINCT order_id) as buy_orders
                    FROM `{history_table}`
                    WHERE is_buy_order = 1
                        AND DATE(issued) BETWEEN %s AND %s
                    GROUP BY day
                ) h ON h.day = p.day
                ORDER BY p.day DESC
            """, (date_from, date_to, date_from, date_to))

            return cursor.fetchall()

    except Error as e:
        print(f"Database error while getting profit by days: {e}")
        return []
    except Exception as e:
        print(f"Error while getting profit by days: {e}")
        return []
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def get_profit_by_items(character_id, date_from, date_to):
    """Get profit report aggregated by items for a date range

    Args:
        character_id: Character ID
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)

    Returns:
        list: List of dicts with item profit data including item names
    """
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)

            history_table = f"character_history_{character_id}"
            profit_table = f"character_profit_{character_id}"

            cursor.execute(f"""
                SELECT
                    p.type_id,
                    t.typeName as item_name,
                    (SELECT COUNT(DISTINCT h2.order_id)
                     FROM `{history_table}` h2
                     WHERE h2.type_id = p.type_id
                       AND h2.is_buy_order = 1
                       AND DATE(h2.issued) BETWEEN %s AND %s) as buy_orders,
                    COUNT(DISTINCT p.sell_order_id) as sell_orders,
                    SUM(p.quantity) as quantity_sold,
                    SUM(p.sell_price * p.quantity) as total_sales,
                    SUM(p.broker_fee_sell + p.sales_tax) as total_taxes,
                    SUM(p.net_profit) as total_profit
                FROM `{profit_table}` p
                LEFT JOIN types t ON t.typeID = p.type_id
                WHERE DATE(p.sell_date) BETWEEN %s AND %s
                GROUP BY p.type_id, t.typeName
                ORDER BY total_profit DESC
            """, (date_from, date_to, date_from, date_to))

            return cursor.fetchall()

    except Error as e:
        print(f"Database error while getting profit by items: {e}")
        return []
    except Exception as e:
        print(f"Error while getting profit by items: {e}")
        return []
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def get_last_buy_price(character_id, type_id):
    """Get last buy order price for a specific item type

    Args:
        character_id: Character ID
        type_id: Item type ID

    Returns:
        float: Price from the most recent buy order, or None if not found
    """
    connection = None
    try:
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            table_name = f"character_history_{character_id}"

            # Get most recent buy order for this type_id
            query = f"""
                SELECT price
                FROM `{table_name}`
                WHERE type_id = %s AND is_buy_order = 1
                ORDER BY issued DESC
                LIMIT 1
            """

            cursor.execute(query, (type_id,))
            result = cursor.fetchone()

            if result:
                return float(result[0])
            return None

    except Error as e:
        print(f"Database error while getting last buy price: {e}")
        return None
    except Exception as e:
        print(f"Error while getting last buy price: {e}")
        return None
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
