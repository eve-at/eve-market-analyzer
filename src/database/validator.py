"""Database validation utilities"""
import mysql.connector
from mysql.connector import Error
import importlib


def _get_db_config():
    """Reload and get DB_CONFIG from settings module"""
    import settings
    importlib.reload(settings)
    return settings.DB_CONFIG


class DatabaseStatus:
    """Database validation status"""
    def __init__(self, connected=False, regions_exist=False, types_exist=False,
                 regions_count=0, types_count=0, error_message=None):
        self.connected = connected
        self.regions_exist = regions_exist
        self.types_exist = types_exist
        self.regions_count = regions_count
        self.types_count = types_count
        self.error_message = error_message

    @property
    def is_ready(self):
        """Check if database is ready for use"""
        return self.connected and self.regions_exist and self.types_exist

    def __str__(self):
        if not self.connected:
            return f"Database connection failed: {self.error_message}"
        if not self.regions_exist:
            return "Regions table is empty"
        if not self.types_exist:
            return "Types table is empty"
        return f"Database ready: {self.regions_count} regions, {self.types_count} types"


def validate_database():
    """
    Validate database connection and check if required tables have data

    Returns:
        DatabaseStatus object with validation results
    """
    connection = None
    try:
        # Reload settings to get fresh DB_CONFIG
        db_config = _get_db_config()

        # Try to connect to database
        connection = mysql.connector.connect(**db_config)

        if not connection.is_connected():
            return DatabaseStatus(
                connected=False,
                error_message="Failed to connect to database"
            )

        cursor = connection.cursor()

        # Check regions table
        regions_count = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM regions")
            result = cursor.fetchone()
            regions_count = result[0] if result else 0
        except Error as e:
            # Table might not exist
            print(f"Error checking regions table: {e}")
            regions_count = 0

        # Check types table
        types_count = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM types WHERE published = 1")
            result = cursor.fetchone()
            types_count = result[0] if result else 0
        except Error as e:
            # Table might not exist
            print(f"Error checking types table: {e}")
            types_count = 0

        return DatabaseStatus(
            connected=True,
            regions_exist=regions_count > 0,
            types_exist=types_count > 0,
            regions_count=regions_count,
            types_count=types_count
        )

    except Error as e:
        return DatabaseStatus(
            connected=False,
            error_message=str(e)
        )
    except Exception as e:
        return DatabaseStatus(
            connected=False,
            error_message=str(e)
        )
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
