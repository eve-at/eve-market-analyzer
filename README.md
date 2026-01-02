# EVE Online Market History Viewer

A desktop application for viewing historical market data from EVE Online using the ESI API.

## Features

- ✅ Real-time market history data from EVE Online ESI API
- ✅ Autocomplete search for regions and items
- ✅ Data loaded from MySQL database
- ✅ Automatic import of static data from Fuzzwork
- ✅ File monitoring for automatic market log detection
- ✅ Clean and intuitive UI built with Flet

## Prerequisites

- Python 3.8 or higher
- MySQL database (or Docker)
- EVE Online client (for market logs monitoring)

## Installation and Setup

### 1. Database Setup

#### Option A: Using Docker (Recommended)

If you have Docker installed, simply run:

```bash
docker-compose up -d
```

This will start a MySQL container with the required configuration.

#### Option B: Using Existing MySQL

Make sure you have access to a MySQL database server. You'll need:
- Database name
- Username
- Password
- Host address (usually `localhost`)

### 2. Clone Repository and Create Virtual Environment

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

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Application

Copy the example settings file and configure it:

```bash
# Linux/Mac
cp settings.py.example settings.py

# Windows
copy settings.py.example settings.py
```

Edit `settings.py` with your database credentials and EVE market logs path:

```python
DB_CONFIG = {
    'host': 'localhost',
    'database': 'evetrader',
    'user': 'your_username',
    'password': 'your_password'
}

MARKETLOGS_DIR = r'C:\Users\YourName\Documents\EVE\logs\Marketlogs'
```

### 5. Run Application

```bash
python main.py
```

On first run, the application will:
- Check database connection
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
├── main.py                         # Main entry point
├── settings.py.example            # Example configuration file
├── settings.py                    # Your configuration (not in git)
├── requirements.txt               # Python dependencies
├── docker-compose.yml             # Docker MySQL setup (optional)
├── data/                          # Downloaded CSV files (auto-created)
└── src/                           # Source code package
    ├── app.py                     # Main application class
    ├── handlers/                  # Event handlers
    │   ├── market_log_handler.py  # File system monitoring
    │   └── import_static_data.py  # Static data import functionality
    ├── ui/                        # UI components
    │   ├── init_screen.py         # Initialization/setup screen
    │   ├── autocomplete_field.py  # Autocomplete input field
    │   └── suggestion_item.py     # Suggestion list item
    └── database/                  # Database operations
        ├── validator.py           # Database validation
        └── data_loader.py         # Data loading utilities
```

## Troubleshooting

### Database Connection Errors

- Verify your MySQL server is running
- Check credentials in `settings.py`
- Ensure the database exists (create it if needed)

### No Items/Regions in Dropdown

- Run `python import_static_data.py` to populate the database
- Check database connection settings
- Verify tables were created successfully

### Market Log Monitoring Not Working

- Verify `MARKETLOGS_DIR` path is correct
- Check that the directory exists
- Make sure you're exporting market data in EVE Online correctly

## Requirements

See `requirements.txt` for full list. Main dependencies:
- `flet>=0.80.0` - UI framework
- `requests` - API calls
- `mysql-connector-python` - Database connectivity
- `watchdog` - File system monitoring
- `pandas` - Data processing

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This application is not affiliated with or endorsed by CCP Games. EVE Online and all associated logos and designs are the intellectual property of CCP hf.
