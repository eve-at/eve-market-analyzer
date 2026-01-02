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

### 5. Import Static Data

Run the import script to download and populate the database with regions and item types:

```bash
python import_static_data.py
```

This script will:
- Download the latest region data from Fuzzwork
- Download the latest item types data from Fuzzwork
- Create necessary database tables (`regions` and `types`)
- Import all data into your MySQL database

**Note:** You should periodically re-run this script to update static data, especially after major EVE Online patches or updates.

### 6. Run Application

```bash
python eve_market_history.py
```

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

EVE Online frequently adds new items, regions, and makes balance changes. To keep your data current:

```bash
python import_static_data.py
```

**When to update:**
- After major EVE Online expansions
- When new items are added to the game
- If you notice missing items in the autocomplete
- At least once every few months for general maintenance

## Project Structure

```
eve-market-history/
├── eve_market_history.py    # Main application
├── import_static_data.py    # Static data import script
├── settings.py.example      # Example configuration file
├── settings.py              # Your configuration (not in git)
├── requirements.txt         # Python dependencies
├── docker-compose.yml       # Docker MySQL setup (optional)
└── README.md               # This file
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
