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


def find_opportunities(region_id, min_sell_price, max_buy_price, min_profit_percent,
                      max_profit_percent, min_daily_quantity, max_competitors=None,
                      selected_market_groups=None, callback=None):
    """
    Find trade opportunities based on filters and save to database

    Parameters:
    region_id - EVE Online region ID
    min_sell_price - Minimum sell price filter
    max_buy_price - Maximum buy price filter
    min_profit_percent - Minimum profit percentage
    max_profit_percent - Maximum profit percentage
    min_daily_quantity - Minimum daily quantity
    max_competitors - Maximum number of competitors (optional)
    selected_market_groups - Optional list of market group IDs to filter by
    callback - optional callback function for progress messages

    Returns:
    list - List of opportunities as dictionaries, or None if failed
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
        log(f"Finding trade opportunities for region {region_id}")
        log("="*60)
        log("")

        # Connect to database
        log("Connecting to MySQL database...")
        connection = mysql.connector.connect(**settings.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)
        log("Successfully connected to MySQL")
        log("")

        orders_table = f"orders_{region_id}"
        opportunities_table = f"opportunities_{region_id}"
        history_table = f"history_{region_id}"

        # Check if orders table exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        """, (settings.DB_CONFIG['database'], orders_table))

        if cursor.fetchone()['COUNT(*)'] == 0:
            log(f"Error: Orders table {orders_table} doesn't exist")
            log("Please click 'Update Orders' first")
            return None

        # Create history table if not exists
        log(f"Creating table {history_table} if not exists...")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {history_table} (
                type_id INT NOT NULL,
                order_count INT DEFAULT NULL,
                volume INT DEFAULT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (type_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
        """)
        log(f"Table {history_table} ready")
        log("")

        # Check if orders table has data
        cursor.execute(f"SELECT COUNT(*) as cnt FROM {orders_table}")
        orders_count = cursor.fetchone()['cnt']

        if orders_count == 0:
            log(f"Error: Orders table {orders_table} is empty")
            log("Please click 'Update Orders' first")
            return None

        log(f"Found {orders_count} orders in table")
        log("")

        # Create opportunities table if not exists
        log(f"Creating table {opportunities_table} if not exists...")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {opportunities_table} (
                type_id INT PRIMARY KEY,
                typeName VARCHAR(255),
                buy_orders_count INT,
                sell_orders_count INT,
                min_sell_price DECIMAL(20, 2),
                max_buy_price DECIMAL(20, 2),
                profit INT,
                competitors INT,
                qty_avg INT,
                daily_orders INT DEFAULT NULL,
                daily_volume INT DEFAULT NULL
            )
        """)
        log(f"Table {opportunities_table} ready")
        log("")

        # Clear opportunities table
        log(f"Clearing existing data from {opportunities_table}...")
        cursor.execute(f"TRUNCATE TABLE {opportunities_table}")
        log("Table cleared")
        log("")

        # Execute the main query
        log("Executing opportunities query...")
        log(f"Selected market groups: {selected_market_groups}")
        log(f"Max competitors: {max_competitors}")

        # Build the query with optional market groups filter
        market_groups_join = ""
        market_groups_filter = ""

        if selected_market_groups and len(selected_market_groups) > 0:
            market_groups_join = "JOIN market_groups mg ON mg.marketGroupID = t.marketGroupID"
            placeholders = ', '.join(['%s'] * len(selected_market_groups))
            market_groups_filter = f"AND mg.topGroupID IN ({placeholders})"
            log(f"Filtering by {len(selected_market_groups)} market group(s): {selected_market_groups}")

        # Build competitors filter
        competitors_filter = ""
        if max_competitors is not None:
            competitors_filter = f"AND competitors < %s"
            log(f"Filtering by max competitors: {max_competitors}")

        query = f"""
            INSERT INTO {opportunities_table}
            (type_id, typeName, buy_orders_count, sell_orders_count,
             min_sell_price, max_buy_price, profit, competitors, qty_avg)
            SELECT
                o.type_id,
                t.typeName,
                COUNT(CASE WHEN o.is_buy_order = 1 THEN 1 END) AS buy_orders_count,
                COUNT(CASE WHEN o.is_buy_order = 0 THEN 1 END) AS sell_orders_count,
                MIN(CASE WHEN o.is_buy_order = 0 THEN o.price END) AS min_sell_price,
                MAX(CASE WHEN o.is_buy_order = 1 THEN o.price END) AS max_buy_price,
                ROUND((MIN(CASE WHEN o.is_buy_order = 0 THEN o.price END) -
                       MAX(CASE WHEN o.is_buy_order = 1 THEN o.price END)) /
                       MIN(CASE WHEN o.is_buy_order = 0 THEN o.price END) * 100) AS profit,
                GREATEST(
                    COUNT(CASE WHEN DATEDIFF(NOW(), issued) < 2 AND is_buy_order = 1 THEN 1 ELSE NULL END),
                    COUNT(CASE WHEN DATEDIFF(NOW(), issued) < 2 AND is_buy_order = 0 THEN 1 ELSE NULL END)
                ) as competitors,
                NULL as qty_avg
            FROM {orders_table} o
            JOIN types t ON t.typeID = o.type_id
            WHERE o.type_id IN (
                SELECT
                    o.type_id
                FROM {orders_table} o
                JOIN types t ON t.typeID = o.type_id
                {market_groups_join}
                WHERE o.duration < 365
                    AND o.is_buy_order = 0
                    {market_groups_filter}
                GROUP BY o.type_id
                HAVING MIN(CASE WHEN o.is_buy_order = 0 THEN price END) > %s
                    AND MIN(CASE WHEN o.is_buy_order = 0 THEN price END) < %s
            )
            GROUP BY o.type_id, t.typeName
            HAVING profit > %s AND profit < %s {competitors_filter}
            ORDER BY o.type_id
        """

        # Build parameters list
        params = []
        if selected_market_groups and len(selected_market_groups) > 0:
            params.extend(selected_market_groups)
        params.extend([min_sell_price, max_buy_price, min_profit_percent, max_profit_percent])
        if max_competitors is not None:
            params.append(max_competitors)

        cursor.execute(query, params)
        connection.commit()

        print(query, min_sell_price, max_buy_price, min_profit_percent, max_profit_percent)

        log("Query executed successfully")
        log("")

        # Populate daily_orders and daily_volume for each opportunity
        log("Fetching type_ids from opportunities...")
        cursor.execute(f"SELECT type_id FROM {opportunities_table}")
        type_ids = [row['type_id'] for row in cursor.fetchall()]
        log(f"Found {len(type_ids)} opportunities to process")
        log("")

        log("Populating daily statistics from history...")
        for idx, type_id in enumerate(type_ids, 1):
            if idx % 10 == 0 or idx == 1:
                log(f"Processing {idx}/{len(type_ids)}: type_id {type_id}")

            # Check if data exists in history table (created within last 3 days)
            cursor.execute(f"""
                SELECT order_count, volume
                FROM {history_table}
                WHERE type_id = %s AND DATEDIFF(NOW(), created_at) < 3
            """, (type_id,))

            history_row = cursor.fetchone()

            if history_row:
                # Use existing history data
                daily_orders = history_row['order_count']
                daily_volume = history_row['volume']
            else:
                # Fetch from API and calculate averages
                try:
                    api_url = f"https://esi.evetech.net/latest/markets/{region_id}/history/?datasource=tranquility&type_id={type_id}"
                    response = requests.get(api_url, timeout=10)

                    if response.status_code == 200:
                        history_data = response.json()

                        # Get last 30 days and calculate averages
                        if len(history_data) > 0:
                            last_30_days = history_data[-30:] if len(history_data) >= 30 else history_data

                            total_orders = sum(day.get('order_count', 0) for day in last_30_days)
                            total_volume = sum(day.get('volume', 0) for day in last_30_days)

                            daily_orders = round(total_orders / len(last_30_days))
                            daily_volume = round(total_volume / len(last_30_days))

                            # Insert or update history table
                            cursor.execute(f"""
                                INSERT INTO {history_table} (type_id, order_count, volume, created_at)
                                VALUES (%s, %s, %s, NOW())
                                ON DUPLICATE KEY UPDATE
                                    order_count = VALUES(order_count),
                                    volume = VALUES(volume),
                                    created_at = NOW()
                            """, (type_id, daily_orders, daily_volume))
                        else:
                            daily_orders = 0
                            daily_volume = 0
                    else:
                        log(f"  Warning: API request failed for type_id {type_id} (status {response.status_code})")
                        daily_orders = 0
                        daily_volume = 0

                    # Small delay to avoid rate limiting
                    time.sleep(0.1)

                except Exception as e:
                    log(f"  Error fetching history for type_id {type_id}: {e}")
                    daily_orders = 0
                    daily_volume = 0

            # Update opportunities table with daily statistics
            cursor.execute(f"""
                UPDATE {opportunities_table}
                SET daily_orders = %s, daily_volume = %s
                WHERE type_id = %s
            """, (daily_orders, daily_volume, type_id))

        connection.commit()
        log("Daily statistics populated successfully")
        log("")

        # Fetch results
        log("Fetching opportunities from database...")
        cursor.execute(f"SELECT * FROM {opportunities_table}")
        opportunities = cursor.fetchall()

        log("")
        log("="*60)
        log(f"Found {len(opportunities)} trade opportunities")
        log("="*60)

        return opportunities

    except Error as e:
        log(f"Database error: {e}")
        if connection:
            connection.rollback()
        return None
    except Exception as e:
        log(f"Error: {e}")
        if connection:
            connection.rollback()
        return None
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            log("MySQL connection closed")


def export_opportunities_to_csv(region_id, callback=None):
    """
    Export opportunities table to CSV file

    Parameters:
    region_id - EVE Online region ID
    callback - optional callback function for progress messages

    Returns:
    str - Path to exported CSV file, or None if failed
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
        log(f"Exporting opportunities for region {region_id} to CSV")
        log("="*60)
        log("")

        # Connect to database
        log("Connecting to MySQL database...")
        connection = mysql.connector.connect(**settings.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)
        log("Successfully connected to MySQL")
        log("")

        opportunities_table = f"opportunities_{region_id}"

        # Check if opportunities table exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        """, (settings.DB_CONFIG['database'], opportunities_table))

        if cursor.fetchone()['COUNT(*)'] == 0:
            log(f"Error: Opportunities table {opportunities_table} doesn't exist")
            log("Please run 'Find Opportunities' first")
            return None

        # Fetch data
        log(f"Fetching data from {opportunities_table}...")
        cursor.execute(f"SELECT * FROM {opportunities_table}")
        opportunities = cursor.fetchall()

        if not opportunities:
            log("No data to export")
            return None

        log(f"Found {len(opportunities)} opportunities")
        log("")

        # Export to CSV
        import csv
        import os
        from datetime import datetime
        from src.database.models import get_setting

        # Get CSV export path from settings (default to 'data' folder)
        csv_export_path = get_setting('csv_export_path', 'data')

        # Create directory if it doesn't exist
        os.makedirs(csv_export_path, exist_ok=True)

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"opportunities_{region_id}_{timestamp}.csv"

        # Create full filepath
        filepath = os.path.join(csv_export_path, filename)

        log(f"Writing to {filepath}...")

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['type_id', 'typeName', 'buy_orders_count', 'sell_orders_count',
                         'min_sell_price', 'max_buy_price', 'profit', 'qty_avg']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for opp in opportunities:
                writer.writerow(opp)

        log("")
        log("="*60)
        log(f"Successfully exported to {filename}")
        log("="*60)

        return filepath

    except Error as e:
        log(f"Database error: {e}")
        return None
    except Exception as e:
        log(f"Error: {e}")
        return None
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
