import pandas as pd
import mysql.connector
from mysql.connector import Error
from settings import DB_CONFIG, REGIONS_DF, TYPES_DF

def import_csv_to_mysql():
    """
    Imports CSV files regions.csv and types.csv into MySQL tables
    
    Parameters:
    host - MySQL server host (e.g., 'localhost')
    database - database name
    user - MySQL username
    password - user password
    """
    
    try:
        # Connect to MySQL
        connection = mysql.connector.connect(**DB_CONFIG)
        
        if connection.is_connected():
            cursor = connection.cursor()
            print("Successfully connected to MySQL")
            
            # Read CSV files
            regions_df = pd.read_csv(REGIONS_DF)
            types_df = pd.read_csv(TYPES_DF)
            
            print(f"\nColumns in regions.csv: {list(regions_df.columns)}")
            print(f"Columns in types.csv: {list(types_df.columns)}")
            
            # Create regions table based on CSV structure
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
            print("Table regions created or already exists")
            
            # Create types table based on CSV structure
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
            print("Table types created or already exists")
            
            # Clear tables before import (optional)
            cursor.execute("TRUNCATE TABLE regions")
            cursor.execute("TRUNCATE TABLE types")
            print("Tables cleared")
            
            # Import data into regions table
            print("\nImporting data into regions table...")
            for index, row in regions_df.iterrows():
                # Replace None with NULL for MySQL
                values = tuple(None if pd.isna(val) else val for val in row)
                placeholders = ', '.join(['%s'] * len(row))
                columns = ', '.join(row.index)
                sql = f"INSERT INTO regions ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                
                if (index + 1) % 10 == 0:
                    print(f"Imported {index + 1} records into regions...")
            
            # Import data into types table
            print("\nImporting data into types table...")
            for index, row in types_df.iterrows():
                # Replace None with NULL for MySQL
                values = tuple(None if pd.isna(val) else val for val in row)
                placeholders = ', '.join(['%s'] * len(row))
                columns = ', '.join(row.index)
                sql = f"INSERT INTO types ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                
                if (index + 1) % 100 == 0:
                    print(f"Imported {index + 1} records into types...")
            
            connection.commit()
            print(f"\n✓ Successfully imported {len(regions_df)} records into regions table")
            print(f"✓ Successfully imported {len(types_df)} records into types table")
            
    except Error as e:
        print(f"MySQL error: {e}")
        if connection:
            connection.rollback()
        
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("\nMySQL connection closed")

# Usage
if __name__ == "__main__":
    import_csv_to_mysql()