"""Static data import handler"""
import pandas as pd
import mysql.connector
from mysql.connector import Error
import requests
from pathlib import Path
import importlib


def _get_settings():
    """Reload and get settings from settings module"""
    import settings
    importlib.reload(settings)
    return settings


def download_csv(url, filename, callback=None):
    """
    Download CSV file from URL

    Parameters:
    url - URL to download from
    filename - local filename to save
    callback - optional callback function for progress messages

    Returns:
    Path to downloaded file
    """
    msg = f"Downloading {filename} from {url}..."
    print(msg)
    if callback:
        callback(msg)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Create data directory if it doesn't exist
        data_dir = Path('data')
        data_dir.mkdir(exist_ok=True)

        # Save file
        filepath = data_dir / filename
        with open(filepath, 'wb') as f:
            f.write(response.content)

        msg = f"Successfully downloaded {filename}"
        print(msg)
        if callback:
            callback(msg)
        return filepath

    except requests.exceptions.RequestException as e:
        msg = f"Error downloading {filename}: {e}"
        print(msg)
        if callback:
            callback(msg)
        raise


def import_static_data(callback=None):
    """
    Download and import static data (regions and types) into MySQL database

    Parameters:
    callback - optional callback function to receive progress messages

    Returns:
    bool - True if successful, False otherwise
    """

    def log(message):
        """Helper to log message to console and callback"""
        print(message)
        if callback:
            callback(message)

    # Reload settings to get fresh configuration
    settings = _get_settings()

    log("="*60)
    log("EVE Online Static Data Import")
    log("="*60)
    log("")

    # Download CSV files
    try:
        regions_file = download_csv(settings.REGIONS_DF, 'mapRegions.csv', callback)
        types_file = download_csv(settings.TYPES_DF, 'invTypes.csv', callback)
        market_groups_file = download_csv(settings.MARKET_GROUPS_DF, 'invMarketGroups.csv', callback)
    except Exception as e:
        log(f"\nFailed to download files: {e}")
        return False

    log("")

    # Connect to database and import data
    connection = None
    try:
        # Connect to MySQL
        log("Connecting to MySQL database...")
        connection = mysql.connector.connect(**settings.DB_CONFIG)

        if connection.is_connected():
            cursor = connection.cursor()
            log("Successfully connected to MySQL")
            log("")

            # Read CSV files
            log("Reading CSV files...")
            regions_df = pd.read_csv(regions_file)
            types_df = pd.read_csv(types_file)
            market_groups_df = pd.read_csv(market_groups_file)
            log(f"Loaded {len(regions_df)} regions")
            log(f"Loaded {len(types_df)} item types")
            log(f"Loaded {len(market_groups_df)} item types")
            log("")

            # Create regions table
            log("Creating regions table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS regions (
                    regionID BIGINT PRIMARY KEY,
                    regionName VARCHAR(255),
                    x DOUBLE,
                    y DOUBLE,
                    z DOUBLE,
                    xMin DOUBLE,
                    xMax DOUBLE,
                    yMin DOUBLE,
                    yMax DOUBLE,
                    zMin DOUBLE,
                    zMax DOUBLE,
                    factionID INT,
                    nebula INT,
                    radius VARCHAR(50)
                )
            """)
            log("Table 'regions' created or already exists")

            # Create types table
            log("Creating types table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS types (
                    typeID INT PRIMARY KEY,
                    groupID INT,
                    typeName VARCHAR(255),
                    description TEXT,
                    mass DOUBLE,
                    volume DOUBLE,
                    capacity DOUBLE,
                    portionSize INT,
                    raceID INT,
                    basePrice DOUBLE,
                    published TINYINT,
                    marketGroupID INT,
                    iconID INT,
                    soundID INT,
                    graphicID INT
                )
            """)
            log("Table 'types' created or already exists")
            log("")


            # Create market groups table
            log("Creating market_groups table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_groups (
                    marketGroupID INT PRIMARY KEY,
                    parentGroupID INT,
                    topGroupID INT,
                    marketGroupName VARCHAR(255),
                    description TEXT,
                    iconID INT,
                    hasTypes TINYINT(1)                    
                )
            """)
            log("Table 'market_groups' created or already exists")
            log("")

            # Clear existing data
            log("Clearing existing data...")
            cursor.execute("TRUNCATE TABLE regions")
            cursor.execute("TRUNCATE TABLE types")
            cursor.execute("TRUNCATE TABLE market_groups")
            log("Tables cleared")
            log("")

            # Import regions
            log("Importing regions data...")
            region_count = 0
            for index, row in regions_df.iterrows():
                values = tuple(None if pd.isna(val) else val for val in row)
                placeholders = ', '.join(['%s'] * len(row))
                columns = ', '.join(row.index)
                sql = f"INSERT INTO regions ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                region_count += 1

                if region_count % 10 == 0:
                    log(f"  Imported {region_count}/{len(regions_df)} regions...")

            log(f"Successfully imported {region_count} regions")
            log("")

            # Import types
            log("Importing types data...")
            type_count = 0
            for index, row in types_df.iterrows():
                values = tuple(None if pd.isna(val) else val for val in row)
                placeholders = ', '.join(['%s'] * len(row))
                columns = ', '.join(row.index)
                sql = f"INSERT INTO types ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                type_count += 1

                if type_count % 1000 == 0:
                    log(f"  Imported {type_count}/{len(types_df)} types...")

            log(f"Successfully imported {type_count} item types")
            log("")

            # Import types
            log("Importing market_groups data...")
            type_count = 0
            for index, row in market_groups_df.iterrows():
                values = tuple(None if pd.isna(val) else val for val in row)
                placeholders = ', '.join(['%s'] * len(row))
                columns = ', '.join(row.index)
                sql = f"INSERT INTO market_groups ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                type_count += 1

                if type_count % 1000 == 0:
                    log(f"  Imported {type_count}/{len(types_df)} market groups...")

            log(f"Successfully imported {type_count} market groups")
            log("")

            # Commit transaction
            connection.commit()
            log("All changes committed to database")
            log("")

            # Fill topGroupID - find the root group for each market group
            log("Calculating topGroupID for market groups...")

            # Get all groups with their parent relationships
            cursor.execute("""
                SELECT marketGroupID, parentGroupID
                FROM market_groups
            """)
            all_groups = {row[0]: row[1] for row in cursor.fetchall()}

            # Function to find top group for a given group
            def find_top_group(group_id, visited=None):
                if visited is None:
                    visited = set()

                # Prevent infinite loops
                if group_id in visited:
                    return group_id
                visited.add(group_id)

                parent_id = all_groups.get(group_id)

                # If no parent, this is the top group
                if parent_id is None:
                    return group_id

                # Recursively find the top group
                return find_top_group(parent_id, visited)

            # Update topGroupID for each group
            update_count = 0
            for group_id in all_groups.keys():
                top_group_id = find_top_group(group_id)
                cursor.execute("""
                    UPDATE market_groups
                    SET topGroupID = %s
                    WHERE marketGroupID = %s
                """, (top_group_id, group_id))
                update_count += 1

                if update_count % 100 == 0:
                    log(f"  Updated topGroupID for {update_count}/{len(all_groups)} groups...")

            connection.commit()
            log(f"Successfully updated topGroupID for {update_count} market groups")
            log("")

            log("="*60)
            log("Import completed successfully!")
            log("="*60)
            return True

    except Error as e:
        log(f"\n✗ MySQL error: {e}")
        if connection:
            connection.rollback()
        return False

    except Exception as e:
        log(f"\n✗ Error: {e}")
        if connection:
            connection.rollback()
        return False

    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            log("\nMySQL connection closed")


if __name__ == "__main__":
    try:
        success = import_static_data()
        if not success:
            print("\nImport failed. Please check the errors above.")
            exit(1)
    except KeyboardInterrupt:
        print("\n\nImport cancelled by user")
        exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        exit(1)
