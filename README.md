# EVE Online Market Analyzer

A comprehensive desktop application for EVE Online traders featuring market analysis, historical data viewing, and trade opportunity finding.

![Profit by Month](static/interface/profit_by_month_page.png)

## Features

- ✅ **Menu-driven interface** with multiple tools for traders
- ✅ **Market History Viewer** - Real-time historical data from EVE Online ESI API
- ✅ **Trade Opportunities Finder** - Search for profitable trades between regions
- ✅ **Accounting Tool** - Opens in a dedicated window; monitors market log exports and calculates profit/spread in real time
- ✅ **Wallet Transactions Import** - Fetches trading history directly from ESI, with incremental updates (no duplicates)
- ✅ **Profit Reports** - By month, by day, by item; calculated via FIFO from real wallet transactions
- ✅ **Transactions Tab** - Browse the last 200 individual buy/sell events with item names and totals
- ✅ **Courier Path Finder** - Optimal delivery route planner with in-game route setting via API
- ✅ **Integrated Settings** - Customize broker fees, taxes, and paths
- ✅ **Automatic Data Import** - Built-in static data management from Fuzzwork
- ✅ **Smart Autocomplete** - Fast region and item search
- ✅ **File Monitoring** - Automatic market log detection
- ✅ **Clean UI** built with Flet framework

## Prerequisites

- Python 3.8 or higher
- EVE Online client (for market logs monitoring)

## Installation and Setup

### 1. Clone Repository and Create Virtual Environment

**Windows (PowerShell):**
```powershell
git clone <repository-url>
cd eve-market-history
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
git clone <repository-url>
cd eve-market-history
python -m venv .venv
.venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
git clone <repository-url>
cd eve-market-history
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Application

Copy the example settings file and configure it:

```bash
# Linux/Mac
cp settings.py.example settings.py

# Windows
copy settings.py.example settings.py
```

Edit `settings.py` with your EVE market logs path:

```python
MARKETLOGS_DIR = r'C:\Users\YourName\Documents\EVE\logs\Marketlogs'
```

### 4. Run Application

```bash
python main.py
```

On first run, the application will:
- Create SQLite database file at `data/evetrader.db` if it doesn't exist
- Check if static data (regions and items) is present
- If data is missing, offer to import it with a button
- Show import progress in real-time

**Note:** The import process is now integrated into the application. You no longer need to run a separate import script!

## Usage

1. **Select Region**: Start typing a region name (e.g., "The Forge", "Jita") and select from the dropdown
2. **Select Item**: Start typing an item name (e.g., "PLEX", "Tritanium") and select from the dropdown
3. **Click "Get History"**: The application will fetch historical market data from the ESI API
4. **View Results**: Browse the table with dates, volumes, and price information

### Automatic Market Log Detection

If you configure `MARKETLOGS_DIR` correctly, the application will automatically:
- Monitor your EVE Online market logs directory
- Detect when you export market data in-game
- Auto-populate region and item fields
- Automatically fetch the history data

## Updating Static Data

EVE Online frequently adds new items, regions, and makes balance changes. To update your data:

1. Delete the existing data from database tables (or use database management tool)
2. Restart the application - it will detect empty tables and offer to re-import

**When to update:**
- After major EVE Online expansions
- When new items are added to the game
- If you notice missing items in the autocomplete
- At least once every few months for general maintenance

## Project Structure

```
historical_prices/
├── main.py                              # Main entry point and navigation controller
├── accounting_tool_app.py               # Standalone Accounting Tool window (separate process)
├── settings.py.example                  # Example configuration file
├── settings.py                          # Your configuration (not in git)
├── requirements.txt                     # Python dependencies
├── data/                                # SQLite database (auto-created, not in git)
└── src/
    ├── app.py                           # Market History screen logic
    ├── auth/
    │   ├── eve_sso.py                   # EVE Online SSO authentication
    │   └── esi_api.py                   # ESI API client (orders history, wallet transactions)
    ├── handlers/
    │   ├── export_file_handler.py       # Watchdog handler for market log exports
    │   └── import_static_data.py        # Static data import from Fuzzwork
    ├── ui/
    │   ├── init_screen.py               # Initialization / static data import screen
    │   ├── welcome_screen.py            # Welcome screen
    │   ├── main_menu.py                 # Main menu with tool cards
    │   ├── app_bar.py                   # Top navigation bar
    │   ├── character_screen.py          # Character login, wallet import, profit reports
    │   ├── accounting_tool_screen.py    # Real-time spread/profit calculator
    │   ├── market_history_screen.py     # Historical price chart and table
    │   ├── trade_opportunities_screen.py# Cross-region trade opportunity finder
    │   ├── courier_path_finder_screen.py# Optimal delivery route planner
    │   ├── settings_screen.py           # Application settings
    │   ├── autocomplete_field.py        # Autocomplete input component
    │   └── suggestion_item.py           # Suggestion list item component
    ├── database/
    │   └── models.py                    # All DB schema, CRUD, and profit calculation logic
    └── utils/
        ├── export_parser.py             # Market log export file parser
        └── price_calculator.py          # Tick size, profit, and competitor calculations
```

## Screenshots

### Welcome Page

Initial page that checks database connection. If the database doesn't exist, it will be created automatically. If static data is missing, you'll be prompted to import it.

![Welcome Page](static/interface/welcome_page.png)

### Main Menu

The main page where you can select the section you need.

![Main Page](static/interface/main_page.png)

### Character & Profit Reports

Log in with your EVE character and set your Sales Tax and Broker Fee values for buying and selling (if you buy on a citadel and sell at an NPC station, these values may differ). These values are used when calculating profitability.

Click **Pull Wallet Transactions** to import your trading history from the ESI API:
- **First run** - downloads the full available history (up to ~6 000+ transactions) and builds profit data from scratch
- **Subsequent runs** - fetches only new transactions since the last import (incremental, no duplicates)

Profit is calculated using **FIFO** (first in, first out) across four tabs: by month, by day, by item, and a raw **Transactions** tab showing individual buy/sell events.

![Profit by Month](static/interface/profit_by_month_page.png)

![Profit by Days](static/interface/profit_by_days_page.png)

![Profit by Items](static/interface/profit_by_items_page.png)

### Accounting Tool

Opens in a **separate window** - the main application stays fully usable while it's open. Monitors your EVE market log exports in real time and shows:
- Current item spread, min sell / max buy prices
- Profit % and ISK amount
- Competitor count on both sides
- Last buy price from your wallet transaction history

Re-clicking the menu button focuses the existing window instead of opening a second one.

### Trade Opportunities Finder

Set your parameters and the application will fetch all orders for the selected region and find suitable trade positions. This may take a while - Jita has around 500,000 orders, which can take about 15 minutes to process.

![Trade Opportunities - Fetching](static/interface/trade_opportunities_finder_page_fetching.png)

![Trade Opportunities - Results](static/interface/trade_opportunities_finder_page_result.png)

### Courier Path Finder

To reduce Broker Fee you need to grind standings with a faction and corporation. One way to do this is courier missions. I used to take missions in bulk and then deliver goods. To plan an optimal route, the Courier Path Finder was developed - the application detects your character's current location, you specify the list of stations to visit, and it calculates the optimal path. This path is set in-game via the API. Currently the application does not account for security level and plots the shortest route. Be careful!

![Courier Path Finder](static/interface/courrier_path_finder_page.png)

## Troubleshooting

### Database Errors

- The SQLite database is stored at `data/evetrader.db` and is created automatically on first run
- If the database is corrupted, delete `data/evetrader.db` and restart the application

### No Items/Regions in Dropdown

- Use "Update Static Data" from the main menu to populate the database
- Verify tables were created successfully

### Market Log Monitoring Not Working

- Verify `MARKETLOGS_DIR` path is correct
- Check that the directory exists
- Make sure you're exporting market data in EVE Online correctly

## Requirements

See `requirements.txt` for full list. Main dependencies:
- `flet>=0.80.0` - UI framework
- `requests` - API calls
- `watchdog` - File system monitoring
- `pandas` - Data processing

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This application is not affiliated with or endorsed by CCP Games. EVE Online and all associated logos and designs are the intellectual property of CCP hf.
