"""Database data loading operations"""
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
    return conn


def load_regions_and_items():
    """Load regions and types data from database

    Returns:
        tuple: (regions_data, items_data) where:
            - regions_data: dict {regionName: regionID}
            - items_data: dict {typeName: typeID}
    """
    regions_data = {}
    items_data = {}
    conn = None

    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # Load regions
        cursor.execute("SELECT regionName, regionID FROM regions ORDER BY regionName")
        regions = cursor.fetchall()
        regions_data = {row['regionName']: row['regionID'] for row in regions}
        print(f"Loaded {len(regions_data)} regions from database")

        # Load types (only published items)
        cursor.execute("SELECT typeName, typeID FROM types WHERE published = 1 ORDER BY typeName")
        types = cursor.fetchall()
        items_data = {row['typeName']: row['typeID'] for row in types}
        print(f"Loaded {len(items_data)} items from database")

    except Exception as e:
        print(f"Database error: {e}")
        regions_data = {}
        items_data = {}
    finally:
        if conn:
            conn.close()

    return regions_data, items_data


def load_top_market_groups():
    """Load top-level market groups from database

    Returns:
        list: List of dicts with keys: marketGroupID, iconID, marketGroupName
    """
    market_groups = []
    conn = None

    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # Load top market groups
        cursor.execute("""
            SELECT marketGroupID, iconID, marketGroupName
            FROM market_groups
            WHERE marketGroupID IN (SELECT DISTINCT topGroupID FROM market_groups)
            ORDER BY marketGroupName
        """)
        market_groups = [dict(row) for row in cursor.fetchall()]
        print(f"Loaded {len(market_groups)} top market groups from database")

    except Exception as e:
        print(f"Database error: {e}")
        market_groups = []
    finally:
        if conn:
            conn.close()

    return market_groups
