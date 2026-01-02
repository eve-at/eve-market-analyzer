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
                    broker_fee DECIMAL(5,2) DEFAULT 3.00,
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
                       broker_fee, sales_tax, access_token, refresh_token, token_expiry
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
                          token_expiry, broker_fee, sales_tax
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
                             'token_expiry', 'broker_fee', 'sales_tax']

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
