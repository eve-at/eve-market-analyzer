"""Database validation utilities"""
import sqlite3
import os
import importlib


def _get_db_path():
    """Reload and get DB_PATH from settings module"""
    import settings
    importlib.reload(settings)
    return settings.DB_PATH


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
    conn = None
    try:
        db_path = _get_db_path()

        # Create data directory if needed
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Check if DB file exists; if not, create it
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check regions table
        regions_count = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM regions")
            result = cursor.fetchone()
            regions_count = result[0] if result else 0
        except sqlite3.OperationalError:
            # Table doesn't exist
            regions_count = 0

        # Check types table
        types_count = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM types WHERE published = 1")
            result = cursor.fetchone()
            types_count = result[0] if result else 0
        except sqlite3.OperationalError:
            # Table doesn't exist
            types_count = 0

        return DatabaseStatus(
            connected=True,
            regions_exist=regions_count > 0,
            types_exist=types_count > 0,
            regions_count=regions_count,
            types_count=types_count
        )

    except Exception as e:
        return DatabaseStatus(
            connected=False,
            error_message=str(e)
        )
    finally:
        if conn:
            conn.close()
