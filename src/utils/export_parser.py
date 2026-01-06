"""Parser for exported market files"""
import csv
from pathlib import Path


def parse_export_file(file_path):
    """
    Parse exported market file and extract relevant data

    Returns dict with:
    - type_id: int
    - min_sell_price: float (minimum price for sell orders at station 60003760)
    - max_buy_price: float (maximum price for buy orders, any station)
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

                    # Store all data for competitor counting
                    order_data = {
                        'price': price,
                        'bid': row.get('bid', 'False'),
                        'issueDate': row.get('issueDate', ''),
                        'stationID': station_id
                    }

                    if is_buy_order:
                        result['buy_orders'].append(order_data)
                        # Track max buy price (any station)
                        if result['max_buy_price'] is None or price > result['max_buy_price']:
                            result['max_buy_price'] = price
                    else:
                        result['sell_orders'].append(order_data)
                        # Track min sell price (only station 60003760)
                        if station_id == '60003760':
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
