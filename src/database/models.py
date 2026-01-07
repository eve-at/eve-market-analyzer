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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    
                    volume_effective INT NOT NULL,
                    exhausted BOOLEAN NOT NULL DEFAULT FALSE,
                    
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
                         type_id, volume_remain, volume_total)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        order['volume_total']
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
