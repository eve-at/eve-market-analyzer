"""Price calculation utilities for EVE Online market"""
import math
from datetime import datetime, timedelta


def calculate_tick_size(price):
    """
    Calculate tick size based on EVE Online's 4-significant-digit rule.

    EVE allows changing only the 4th significant digit of a price.
    The tick = 10^(floor(log10(price)) - 3), minimum 0.01 (sub-cent not supported).

    Examples:
      87.21  -> magnitude=1, tick=10^-2=0.01   (digits: 8,7,2,1)
     734.56  -> magnitude=2, tick=10^-1=0.1    (digits: 7,3,4,5)
    7344.0   -> magnitude=3, tick=10^0 =1      (digits: 7,3,4,4)
    73440    -> magnitude=4, tick=10^1 =10
      5.23   -> magnitude=0, tick=10^-3→0.01   (clamped to minimum)
    """
    if price <= 0:
        return 0.01
    magnitude = math.floor(math.log10(abs(price)))
    tick = 10 ** (magnitude - 3)
    return max(tick, 0.01)


def get_next_sell_tick(current_price):
    """Next lower tick for sell orders (undercut current best sell by one tick)."""
    tick = calculate_tick_size(current_price)
    if tick >= 1:
        # Integer prices: snap to tick boundary then subtract one tick
        rounded = (int(current_price) // int(tick)) * int(tick)
        return float(rounded - tick)
    else:
        return round(current_price - tick, 2)


def get_next_buy_tick(current_price):
    """Next higher tick for buy orders (overbid current best buy by one tick)."""
    tick = calculate_tick_size(current_price)
    if tick >= 1:
        current_int = int(current_price)
        tick_int = int(tick)
        if current_int % tick_int == 0:
            return float(current_int + tick_int)
        return float(((current_int // tick_int) + 1) * tick_int)
    else:
        return round(current_price + tick, 2)


def format_price_display(price):
    """Format price for UI display. Shows cents when price < 1000."""
    if price is None:
        return "N/A"
    if price < 1000:
        return f"{price:,.2f}"
    return f"{int(price):,}"


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


def round_to_valid_price(price):
    """
    Round price to valid EVE Online price (only first 4 significant digits can be non-zero)

    Examples:
    - 123456789 -> 123400000 (only first 4 digits: 1,2,3,4)
    - 734567 -> 734500 (only first 4 digits: 7,3,4,5)
    - 999 -> 999 (less than 4 digits, no change)
    - 1001 -> 1001 (exactly 4 digits, no change)

    Args:
        price: Price to round

    Returns:
        float: Rounded price
    """
    if price < 1000:
        # Less than 4 digits, no rounding needed
        return price

    import math

    # Get number of digits
    num_digits = int(math.log10(price)) + 1

    # Round to 4 significant figures
    # Calculate the divisor to keep only 4 significant digits
    divisor = 10 ** (num_digits - 4)

    # Round down to the divisor
    rounded = (int(price / divisor)) * divisor

    return rounded


def adjust_price_by_scroll(current_price, scroll_delta):
    """
    Adjust price by scroll wheel delta, changing the 4th significant digit

    Args:
        current_price: Current price value
        scroll_delta: Positive for scroll up (increase), negative for scroll down (decrease)

    Returns:
        float: New adjusted price
    """
    if scroll_delta == 0:
        return current_price

    tick_size = calculate_tick_size(current_price)

    if scroll_delta > 0:
        # Scroll up - increase price
        new_price = current_price + tick_size
    else:
        # Scroll down - decrease price
        new_price = current_price - tick_size
        if new_price < 0.01:
            new_price = 0.01

    return round_to_valid_price(new_price)
