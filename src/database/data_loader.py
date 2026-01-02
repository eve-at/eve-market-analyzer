"""Database data loading operations"""
import mysql.connector
from mysql.connector import Error
import importlib


def _get_db_config():
    """Reload and get DB_CONFIG from settings module"""
    import settings
    importlib.reload(settings)
    return settings.DB_CONFIG


def load_regions_and_items():
    """Load regions and types data from MySQL database

    Returns:
        tuple: (regions_data, items_data) where:
            - regions_data: dict {regionName: regionID}
            - items_data: dict {typeName: typeID}
    """
    regions_data = {}
    items_data = {}

    try:
        # Reload settings to get fresh DB_CONFIG
        db_config = _get_db_config()
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            # Load regions
            cursor.execute("SELECT regionName, regionID FROM regions ORDER BY regionName")
            regions = cursor.fetchall()
            regions_data = {name: region_id for name, region_id in regions}
            print(f"Loaded {len(regions_data)} regions from database")

            # Load types (only published items)
            cursor.execute("SELECT typeName, typeID FROM types WHERE published = 1 ORDER BY typeName")
            types = cursor.fetchall()
            items_data = {name: type_id for name, type_id in types}
            print(f"Loaded {len(items_data)} items from database")

    except Error as e:
        print(f"Database error: {e}")
        # Return empty dicts if database error
        regions_data = {}
        items_data = {}
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return regions_data, items_data
