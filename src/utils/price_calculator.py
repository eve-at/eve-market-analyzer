"""Price calculation utilities for EVE Online market"""
from datetime import datetime, timedelta


def calculate_tick_size(price):
    """
    Calculate tick size based on price according to EVE Online tick size system
    Introduced: 2020-02-24
    Reference: https://www.eveonline.com/news/view/broker-relations

    Logic: Change only the 4th significant digit
    - Numbers < 1000 (less than 4 digits): can change last digit
    - Numbers >= 1000 (4+ digits): change 4th digit, rest are zeros

    Examples:
    - 734400 -> tick is 100 (4th digit position)
    - 1493000 -> tick is 1000 (4th digit position)
    - 500 -> tick is 1 (last digit)
    """
    if price < 1000:
        # Less than 4 digits - change last digit
        # Find the order of magnitude
        if price < 10:
            return 0.01
        elif price < 100:
            return 0.1
        else:  # 100-999
            return 1
    else:
        # 4+ digits - change the 4th significant digit
        # Calculate the magnitude: number of digits
        import math
        magnitude = int(math.log10(price))

        # The tick is 10^(magnitude - 3)
        # For 1493000 (7 digits): magnitude=6, tick=10^(6-3)=1000
        # For 734400 (6 digits): magnitude=5, tick=10^(5-3)=100
        tick = 10 ** (magnitude - 3)
        return tick


def get_next_sell_tick(current_price):
    """
    Calculate next lower tick for sell orders (to undercut current best sell)

    For numbers >= 1000: round down to tick boundary, then subtract one tick
    For numbers < 1000: simply subtract tick size
    """
    tick_size = calculate_tick_size(current_price)

    if current_price >= 1000:
        # Round current price down to nearest tick boundary
        rounded_down = (int(current_price) // int(tick_size)) * int(tick_size)
        # Subtract one tick
        next_price = rounded_down - tick_size
        return float(next_price)
    else:
        return round(current_price - tick_size, 2)


def get_next_buy_tick(current_price):
    """
    Calculate next higher tick for buy orders (to overbid current best buy)

    For numbers >= 1000: round up to next tick boundary
    For numbers < 1000: simply add tick size
    """
    tick_size = calculate_tick_size(current_price)

    if current_price >= 1000:
        # Round current price up to next tick boundary
        current_int = int(current_price)
        tick_int = int(tick_size)

        # If already on boundary, add one tick; otherwise round up
        if current_int % tick_int == 0:
            next_price = current_int + tick_int
        else:
            next_price = ((current_int // tick_int) + 1) * tick_int

        return float(next_price)
    else:
        return round(current_price + tick_size, 2)


def calculate_broker_fee(price, broker_fee_percent):
    """
    Calculate broker fee in ISK
    broker_fee_percent: percentage (e.g., 3.0 for 3%)
    """
    return round(price * (broker_fee_percent / 100.0), 2)


def calculate_sales_tax(price, sales_tax_percent):
    """
    Calculate sales tax in ISK
    sales_tax_percent: percentage (e.g., 7.5 for 7.5%)
    """
    return round(price * (sales_tax_percent / 100.0), 2)


def calculate_profit(sell_price, buy_price, broker_fee_sell_percent, broker_fee_buy_percent, sales_tax_percent):
    """
    Calculate profit from station trading

    When buying:
    - Pay buy_price
    - Pay broker fee on buy order

    When selling:
    - Receive sell_price
    - Pay broker fee on sell order
    - Pay sales tax

    Profit = sell_price - buy_price - broker_fee_buy - broker_fee_sell - sales_tax
    """
    broker_fee_buy = calculate_broker_fee(buy_price, broker_fee_buy_percent)
    broker_fee_sell = calculate_broker_fee(sell_price, broker_fee_sell_percent)
    sales_tax = calculate_sales_tax(sell_price, sales_tax_percent)

    profit_isk = sell_price - buy_price - broker_fee_buy - broker_fee_sell - sales_tax

    # Calculate profit percentage based on investment (buy price + fees)
    investment = buy_price + broker_fee_buy
    profit_percent = (profit_isk / investment * 100.0) if investment > 0 else 0.0

    return {
        'profit_isk': round(profit_isk, 2),
        'profit_percent': round(profit_percent, 2),
        'broker_fee_buy': broker_fee_buy,
        'broker_fee_sell': broker_fee_sell,
        'sales_tax': sales_tax
    }


def count_competitors(orders, is_sell_order, days_threshold=2):
    """
    Count competitors based on recent orders (within last N days)

    orders: list of order dicts with 'issueDate' field
    is_sell_order: True if counting sell orders, False for buy orders
    days_threshold: consider orders from last N days
    """
    cutoff_date = datetime.now() - timedelta(days=days_threshold)
    count = 0

    for order in orders:
        try:
            # Parse issueDate (format: "2026-01-06 20:29:22.000")
            issue_date_str = order.get('issueDate', '').split('.')[0]  # Remove milliseconds
            issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d %H:%M:%S")

            # Check if order is within threshold
            if issue_date >= cutoff_date:
                # Check if order type matches
                is_buy_order = order.get('bid', 'False') == 'True'
                if is_sell_order and not is_buy_order:
                    count += 1
                elif not is_sell_order and is_buy_order:
                    count += 1
        except (ValueError, AttributeError):
            # Skip orders with invalid date format
            continue

    return count
