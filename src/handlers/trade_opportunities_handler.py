"""Trade opportunities handler for fetching and managing market orders"""
import mysql.connector
from mysql.connector import Error
import requests
import time
import importlib
from datetime import datetime


def _get_settings():
    """Reload and get settings from settings module"""
    import settings
    importlib.reload(settings)
    return settings


def check_orders_count(region_id, callback=None):
    """
    Check if orders table exists for region and return count

    Parameters:
    region_id - EVE Online region ID
    callback - optional callback function for progress messages

    Returns:
    int - number of orders in table, or -1 if table doesn't exist
    """
    settings = _get_settings()
    connection = None

    try:
        connection = mysql.connector.connect(**settings.DB_CONFIG)
        cursor = connection.cursor()

        table_name = f"orders_{region_id}"

        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        """, (settings.DB_CONFIG['database'], table_name))

        table_exists = cursor.fetchone()[0] > 0

        if not table_exists:
            return -1

        # Get count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]

        return count

    except Error as e:
        if callback:
            callback(f"Database error: {e}")
        return -1
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


def update_orders(region_id, callback=None):
    """
    Fetch all market orders for a region from ESI API and store in database

    Parameters:
    region_id - EVE Online region ID
    callback - optional callback function for progress messages

    Returns:
    bool - True if successful, False otherwise
    """

    def log(message):
        """Helper to log message to console and callback"""
        print(message)
        if callback:
            callback(message)

    settings = _get_settings()
    connection = None

    try:
        log("="*60)
        log(f"Fetching market orders for region {region_id}")
        log("="*60)
        log("")

        # Connect to database
        log("Connecting to MySQL database...")
        connection = mysql.connector.connect(**settings.DB_CONFIG)
        cursor = connection.cursor()
        log("Successfully connected to MySQL")
        log("")

        table_name = f"orders_{region_id}"

        # Create table if doesn't exist
        log(f"Creating table {table_name} if not exists...")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                order_id BIGINT PRIMARY KEY,
                duration INT,
                is_buy_order BOOLEAN,
                issued DATETIME,
                location_id BIGINT,
                min_volume INT,
                price DECIMAL(20, 2),
                `range` VARCHAR(50),
                system_id INT,
                type_id INT,
                volume_remain INT,
                volume_total INT
            )
        """)
        log(f"Table {table_name} ready")
        log("")

        # Truncate table
        log(f"Clearing existing data from {table_name}...")
        cursor.execute(f"TRUNCATE TABLE {table_name}")
        log("Table cleared")
        log("")

        # Fetch orders from ESI API
        log("Fetching orders from ESI API...")
        base_url = f"https://esi.evetech.net/latest/markets/{region_id}/orders/"
        page = 1
        total_orders = 0

        while True:
            url = f"{base_url}?order_type=all&page={page}"
            log(f"Fetching page {page}...")

            try:
                response = requests.get(url, timeout=30)

                # Check if page doesn't exist
                if response.status_code == 404:
                    error_data = response.json()
                    if "error" in error_data and "does not exist" in error_data["error"]:
                        log(f"Reached last page (page {page} does not exist)")
                        break

                response.raise_for_status()
                orders = response.json()

                if not orders:
                    log(f"No more orders on page {page}")
                    break

                # Insert orders into database
                log(f"  Inserting {len(orders)} orders from page {page}...")
                for order in orders:
                    # Convert ISO 8601 datetime format to MySQL datetime format
                    issued_dt = datetime.fromisoformat(order['issued'].replace('Z', '+00:00'))

                    cursor.execute(f"""
                        INSERT INTO {table_name}
                        (order_id, duration, is_buy_order, issued, location_id,
                         min_volume, price, `range`, system_id, type_id,
                         volume_remain, volume_total)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            duration = VALUES(duration),
                            is_buy_order = VALUES(is_buy_order),
                            issued = VALUES(issued),
                            location_id = VALUES(location_id),
                            min_volume = VALUES(min_volume),
                            price = VALUES(price),
                            `range` = VALUES(`range`),
                            system_id = VALUES(system_id),
                            type_id = VALUES(type_id),
                            volume_remain = VALUES(volume_remain),
                            volume_total = VALUES(volume_total)
                    """, (
                        order['order_id'],
                        order['duration'],
                        order['is_buy_order'],
                        issued_dt,
                        order['location_id'],
                        order['min_volume'],
                        order['price'],
                        order['range'],
                        order['system_id'],
                        order['type_id'],
                        order['volume_remain'],
                        order['volume_total']
                    ))

                total_orders += len(orders)
                log(f"  Total orders fetched: {total_orders}")

                # Commit after each page
                connection.commit()

                page += 1

                # Pause between requests (1 second)
                time.sleep(1)

            except requests.exceptions.RequestException as e:
                log(f"Error fetching page {page}: {e}")
                break

        log("")
        log("="*60)
        log(f"Successfully fetched {total_orders} orders")
        log("="*60)
        return True

    except Error as e:
        log(f"Database error: {e}")
        if connection:
            connection.rollback()
        return False
    except Exception as e:
        log(f"Error: {e}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            log("MySQL connection closed")


if __name__ == "__main__":
    # Test with The Forge region (ID: 10000002)
    region_id = 10000002

    print(f"Checking orders count for region {region_id}...")
    count = check_orders_count(region_id)

    if count == -1:
        print("Table doesn't exist or is empty")
    else:
        print(f"Found {count} orders")

    print("\nUpdating orders...")
    success = update_orders(region_id)

    if success:
        print("\nUpdate successful!")
        count = check_orders_count(region_id)
        print(f"New count: {count} orders")
    else:
        print("\nUpdate failed!")
