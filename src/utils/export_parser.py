"""Parser for exported market files"""
import csv
from pathlib import Path

# Our trading location constants
OUR_STATION_ID = '60003760'
OUR_SOLAR_SYSTEM_ID = '30000142'


def is_buy_order_competitive(order_data, our_station_id=OUR_STATION_ID, our_solar_system_id=OUR_SOLAR_SYSTEM_ID):
    """
    Check if a buy order is competitive based on location rules

    Rules:
    1. If order is at our station - always competitive
    2. If order is in our solar system but different station - competitive only if jumps >= 1
    3. If order is in different solar system - competitive only if range >= jumps

    Args:
        order_data: dict with keys: stationID, solarSystemID, jumps, range
        our_station_id: our station ID
        our_solar_system_id: our solar system ID

    Returns:
        bool: True if order is competitive
    """
    station_id = order_data.get('stationID', '')
    solar_system_id = order_data.get('solarSystemID', '')

    try:
        jumps = int(order_data.get('jumps', 0))
        order_range = int(order_data.get('range', -1))
    except (ValueError, TypeError):
        # If we can't parse jumps/range, assume not competitive
        return False

    # Rule 1: Same station - always competitive
    if station_id == our_station_id:
        return True

    # Rule 2: Same solar system, different station - competitive if jumps >= 1
    if solar_system_id == our_solar_system_id:
        return jumps >= 1

    # Rule 3: Different solar system - competitive if range >= jumps
    # range -1 means station only, so not competitive for other systems
    if order_range == -1:
        return False

    # range 32767 means region-wide
    if order_range == 32767:
        return True

    return order_range >= jumps


def parse_export_file(file_path):
    """
    Parse exported market file and extract relevant data

    Returns dict with:
    - type_id: int
    - min_sell_price: float (minimum price for sell orders at station 60003760)
    - max_buy_price: float (maximum competitive price for buy orders)
    - sell_orders: list of sell order dicts
    - buy_orders: list of buy order dicts
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Export file not found: {file_path}")

    result = {
        'type_id': None,
        'min_sell_price': None,
        'max_buy_price': None,
        'sell_orders': [],
        'buy_orders': []
    }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Skip empty rows
                if not row.get('price'):
                    continue

                # Extract type_id (same for all orders)
                if result['type_id'] is None:
                    try:
                        result['type_id'] = int(row['typeID'])
                    except (ValueError, KeyError):
                        pass

                try:
                    price = float(row['price'])
                    is_buy_order = row.get('bid', 'False') == 'True'
                    station_id = row.get('stationID', '')

                    # Store all data for competitor counting and location filtering
                    order_data = {
                        'price': price,
                        'bid': row.get('bid', 'False'),
                        'issueDate': row.get('issueDate', ''),
                        'stationID': station_id,
                        'solarSystemID': row.get('solarSystemID', ''),
                        'jumps': row.get('jumps', '0'),
                        'range': row.get('range', '-1')
                    }

                    if is_buy_order:
                        result['buy_orders'].append(order_data)

                        # Only consider competitive buy orders for max price
                        if is_buy_order_competitive(order_data):
                            if result['max_buy_price'] is None or price > result['max_buy_price']:
                                result['max_buy_price'] = price
                                print(f"DEBUG: Competitive buy order found: price={price}, station={station_id}, solar_system={order_data['solarSystemID']}, jumps={order_data['jumps']}, range={order_data['range']}")
                        else:
                            print(f"DEBUG: Non-competitive buy order ignored: price={price}, station={station_id}, solar_system={order_data['solarSystemID']}, jumps={order_data['jumps']}, range={order_data['range']}")
                    else:
                        result['sell_orders'].append(order_data)
                        # Track min sell price (only station 60003760)
                        if station_id == OUR_STATION_ID:
                            if result['min_sell_price'] is None or price < result['min_sell_price']:
                                result['min_sell_price'] = price

                except (ValueError, KeyError) as e:
                    # Skip rows with invalid data
                    print(f"Warning: Skipping invalid row: {e}")
                    continue

    except Exception as e:
        print(f"Error parsing export file: {e}")
        raise

    return result
