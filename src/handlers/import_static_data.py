"""Static data import handler"""
import sqlite3
import os
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
    Download and import static data (regions and types) into SQLite database

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
        stations_file = download_csv(settings.STATIONS_DF, 'staStations.csv', callback)
        solar_systems_file = download_csv(settings.SOLAR_SYSTEMS_DF, 'mapSolarSystems.csv', callback)
        solar_system_jumps_file = download_csv(settings.SOLAR_SYSTEM_JUMPS_DF, 'mapSolarSystemJumps.csv', callback)
    except Exception as e:
        log(f"\nFailed to download files: {e}")
        return False

    log("")

    # Connect to database and import data
    conn = None
    try:
        # Connect to SQLite
        db_path = settings.DB_PATH
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        log("Connecting to SQLite database...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        log("Successfully connected to SQLite")
        log("")

        # Read CSV files
        log("Reading CSV files...")
        # Import pandas only when needed
        import pandas as pd
        regions_df = pd.read_csv(regions_file)
        types_df = pd.read_csv(types_file)
        market_groups_df = pd.read_csv(market_groups_file)
        stations_df = pd.read_csv(stations_file)
        solar_systems_df = pd.read_csv(solar_systems_file)
        solar_system_jumps_df = pd.read_csv(solar_system_jumps_file)
        log(f"Loaded {len(regions_df)} regions")
        log(f"Loaded {len(types_df)} item types")
        log(f"Loaded {len(market_groups_df)} market groups")
        log(f"Loaded {len(stations_df)} stations")
        log(f"Loaded {len(solar_systems_df)} solar systems")
        log(f"Loaded {len(solar_system_jumps_df)} solar system jumps")
        log("")

        # Create regions table
        log("Creating regions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regions (
                regionID INTEGER PRIMARY KEY,
                regionName TEXT,
                x REAL,
                y REAL,
                z REAL,
                xMin REAL,
                xMax REAL,
                yMin REAL,
                yMax REAL,
                zMin REAL,
                zMax REAL,
                factionID INTEGER,
                nebula INTEGER,
                radius TEXT
            )
        """)
        log("Table 'regions' created or already exists")

        # Create types table
        log("Creating types table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS types (
                typeID INTEGER PRIMARY KEY,
                groupID INTEGER,
                typeName TEXT,
                description TEXT,
                mass REAL,
                volume REAL,
                capacity REAL,
                portionSize INTEGER,
                raceID INTEGER,
                basePrice REAL,
                published INTEGER,
                marketGroupID INTEGER,
                iconID INTEGER,
                soundID INTEGER,
                graphicID INTEGER
            )
        """)
        log("Table 'types' created or already exists")
        log("")

        # Create market groups table
        log("Creating market_groups table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_groups (
                marketGroupID INTEGER PRIMARY KEY,
                parentGroupID INTEGER,
                topGroupID INTEGER,
                marketGroupName TEXT,
                description TEXT,
                iconID INTEGER,
                hasTypes INTEGER
            )
        """)
        log("Table 'market_groups' created or already exists")
        log("")

        # Create stations table
        log("Creating stations table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                stationID INTEGER PRIMARY KEY,
                security REAL,
                dockingCostPerVolume REAL,
                maxShipVolumeDockable REAL,
                officeRentalCost INTEGER,
                operationID INTEGER,
                stationTypeID INTEGER,
                corporationID INTEGER,
                solarSystemID INTEGER,
                constellationID INTEGER,
                regionID INTEGER,
                stationName TEXT,
                x REAL,
                y REAL,
                z REAL,
                reprocessingEfficiency REAL,
                reprocessingStationsTake REAL,
                reprocessingHangarFlag INTEGER
            )
        """)
        log("Table 'stations' created or already exists")
        log("")

        # Create solar_systems table
        log("Creating solar_systems table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS solar_systems (
                solarSystemID INTEGER PRIMARY KEY,
                regionID INTEGER,
                constellationID INTEGER,
                solarSystemName TEXT,
                x REAL,
                y REAL,
                z REAL,
                xMin REAL,
                xMax REAL,
                yMin REAL,
                yMax REAL,
                zMin REAL,
                zMax REAL,
                luminosity REAL,
                border INTEGER,
                fringe INTEGER,
                corridor INTEGER,
                hub INTEGER,
                international INTEGER,
                regional INTEGER,
                constellation INTEGER,
                security REAL,
                factionID INTEGER,
                radius REAL,
                sunTypeID INTEGER,
                securityClass TEXT
            )
        """)
        log("Table 'solar_systems' created or already exists")
        log("")

        # Create solar_system_jumps table
        log("Creating solar_system_jumps table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS solar_system_jumps (
                fromRegionID INTEGER,
                fromConstellationID INTEGER,
                fromSolarSystemID INTEGER,
                toSolarSystemID INTEGER,
                toConstellationID INTEGER,
                toRegionID INTEGER,
                PRIMARY KEY (fromSolarSystemID, toSolarSystemID)
            )
        """)
        log("Table 'solar_system_jumps' created or already exists")
        log("")

        # Clear existing data
        log("Clearing existing data...")
        cursor.execute("DELETE FROM regions")
        cursor.execute("DELETE FROM types")
        cursor.execute("DELETE FROM market_groups")
        cursor.execute("DELETE FROM stations")
        cursor.execute("DELETE FROM solar_systems")
        cursor.execute("DELETE FROM solar_system_jumps")
        log("Tables cleared")
        log("")

        # Import regions
        log("Importing regions data...")
        region_count = 0
        for index, row in regions_df.iterrows():
            values = tuple(None if pd.isna(val) else val for val in row)
            placeholders = ', '.join(['?'] * len(row))
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
            placeholders = ', '.join(['?'] * len(row))
            columns = ', '.join(row.index)
            sql = f"INSERT INTO types ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, values)
            type_count += 1

            if type_count % 1000 == 0:
                log(f"  Imported {type_count}/{len(types_df)} types...")

        log(f"Successfully imported {type_count} item types")
        log("")

        # Import market groups
        log("Importing market_groups data...")
        mg_count = 0
        for index, row in market_groups_df.iterrows():
            values = tuple(None if pd.isna(val) else val for val in row)
            placeholders = ', '.join(['?'] * len(row))
            columns = ', '.join(row.index)
            sql = f"INSERT INTO market_groups ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, values)
            mg_count += 1

            if mg_count % 1000 == 0:
                log(f"  Imported {mg_count}/{len(market_groups_df)} market groups...")

        log(f"Successfully imported {mg_count} market groups")
        log("")

        # Import stations
        log("Importing stations data...")
        station_count = 0
        for index, row in stations_df.iterrows():
            values = tuple(None if pd.isna(val) else val for val in row)
            placeholders = ', '.join(['?'] * len(row))
            columns = ', '.join(row.index)
            sql = f"INSERT INTO stations ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, values)
            station_count += 1

            if station_count % 500 == 0:
                log(f"  Imported {station_count}/{len(stations_df)} stations...")

        log(f"Successfully imported {station_count} stations")
        log("")

        # Import solar systems
        log("Importing solar_systems data...")
        solar_system_count = 0
        for index, row in solar_systems_df.iterrows():
            values = tuple(None if pd.isna(val) else val for val in row)
            placeholders = ', '.join(['?'] * len(row))
            columns = ', '.join(row.index)
            sql = f"INSERT INTO solar_systems ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, values)
            solar_system_count += 1

            if solar_system_count % 500 == 0:
                log(f"  Imported {solar_system_count}/{len(solar_systems_df)} solar systems...")

        log(f"Successfully imported {solar_system_count} solar systems")
        log("")

        # Import solar system jumps
        log("Importing solar_system_jumps data...")
        jump_count = 0
        for index, row in solar_system_jumps_df.iterrows():
            values = tuple(None if pd.isna(val) else val for val in row)
            placeholders = ', '.join(['?'] * len(row))
            columns = ', '.join(row.index)
            sql = f"INSERT INTO solar_system_jumps ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, values)
            jump_count += 1

            if jump_count % 1000 == 0:
                log(f"  Imported {jump_count}/{len(solar_system_jumps_df)} jumps...")

        log(f"Successfully imported {jump_count} solar system jumps")
        log("")

        # Commit transaction
        conn.commit()
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
                SET topGroupID = ?
                WHERE marketGroupID = ?
            """, (top_group_id, group_id))
            update_count += 1

            if update_count % 100 == 0:
                log(f"  Updated topGroupID for {update_count}/{len(all_groups)} groups...")

        conn.commit()
        log(f"Successfully updated topGroupID for {update_count} market groups")
        log("")

        log("="*60)
        log("Import completed successfully!")
        log("="*60)
        return True

    except Exception as e:
        log(f"\nError: {e}")
        if conn:
            conn.rollback()
        return False

    finally:
        if conn:
            conn.close()
            log("\nDatabase connection closed")


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
