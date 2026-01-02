import pandas as pd
import mysql.connector
from mysql.connector import Error
import requests
import os
from pathlib import Path
from settings import DB_CONFIG, REGIONS_DF, TYPES_DF


def download_csv(url, filename):
    """
    Download CSV file from URL
    
    Parameters:
    url - URL to download from
    filename - local filename to save
    
    Returns:
    Path to downloaded file
    """
    print(f"Downloading {filename} from {url}...")
    
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
        
        print(f"Successfully downloaded {filename}")
        return filepath
        
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {filename}: {e}")
        raise


def import_static_data():
    """
    Download and import static data (regions and types) into MySQL database
    """
    
    print("="*60)
    print("EVE Online Static Data Import")
    print("="*60)
    print()
    
    # Download CSV files
    try:
        regions_file = download_csv(REGIONS_DF, 'mapRegions.csv')
        types_file = download_csv(TYPES_DF, 'invTypes.csv')
    except Exception as e:
        print(f"\nFailed to download files: {e}")
        return False
    
    print()
    
    # Connect to database and import data
    connection = None
    try:
        # Connect to MySQL
        print("Connecting to MySQL database...")
        connection = mysql.connector.connect(**DB_CONFIG)
        
        if connection.is_connected():
            cursor = connection.cursor()
            print("Successfully connected to MySQL")
            print()
            
            # Read CSV files
            print("Reading CSV files...")
            regions_df = pd.read_csv(regions_file)
            types_df = pd.read_csv(types_file)
            print(f"Loaded {len(regions_df)} regions")
            print(f"Loaded {len(types_df)} item types")
            print()
            
            # Create regions table
            print("Creating regions table...")
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
            print("Table 'regions' created or already exists")
            
            # Create types table
            print("Creating types table...")
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
            print("Table 'types' created or already exists")
            print()
            
            # Clear existing data
            print("Clearing existing data...")
            cursor.execute("TRUNCATE TABLE regions")
            cursor.execute("TRUNCATE TABLE types")
            print("Tables cleared")
            print()
            
            # Import regions
            print("Importing regions data...")
            region_count = 0
            for index, row in regions_df.iterrows():
                values = tuple(None if pd.isna(val) else val for val in row)
                placeholders = ', '.join(['%s'] * len(row))
                columns = ', '.join(row.index)
                sql = f"INSERT INTO regions ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                region_count += 1
                
                if region_count % 10 == 0:
                    print(f"  Imported {region_count}/{len(regions_df)} regions...")
            
            print(f"Successfully imported {region_count} regions")
            print()
            
            # Import types
            print("Importing types data...")
            type_count = 0
            for index, row in types_df.iterrows():
                values = tuple(None if pd.isna(val) else val for val in row)
                placeholders = ', '.join(['%s'] * len(row))
                columns = ', '.join(row.index)
                sql = f"INSERT INTO types ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                type_count += 1
                
                if type_count % 1000 == 0:
                    print(f"  Imported {type_count}/{len(types_df)} types...")
            
            print(f"Successfully imported {type_count} item types")
            print()
            
            # Commit transaction
            connection.commit()
            print("All changes committed to database")
            print()
            
            print("="*60)
            print("Import completed successfully!")
            print("="*60)
            return True
            
    except Error as e:
        print(f"\n✗ MySQL error: {e}")
        if connection:
            connection.rollback()
        return False
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        if connection:
            connection.rollback()
        return False
        
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("\nMySQL connection closed")


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