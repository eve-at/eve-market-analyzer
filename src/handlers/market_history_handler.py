"""Bulk daily market history from EVE Ref (all regions and types in one file per day)

ESI /markets/{region_id}/history/ returns one type per request and is rate limited
(about 300 requests per minute), which is too slow for thousands of candidates.
EVE Ref publishes the same data as one ~600 KB file per day.
"""
import bz2
import csv
import io
import importlib
import os
import sqlite3
import requests
from datetime import date, timedelta

EVEREF_URL = "https://data.everef.net/market-history/{year}/market-history-{day}.csv.bz2"
HISTORY_DAYS = 30


def _get_settings():
    """Reload and get settings from settings module"""
    import settings
    importlib.reload(settings)
    return settings


def _get_connection(settings):
    """Get a SQLite connection"""
    db_path = settings.DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_tables(cursor):
    """Create market history tables if not exist"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_history_daily (
            region_id INTEGER NOT NULL,
            type_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            volume INTEGER NOT NULL,
            order_count INTEGER NOT NULL,
            average REAL,
            PRIMARY KEY (region_id, type_id, date)
        )
    """)
    # Which (day, region) pairs are already loaded; a day file may lack a quiet region
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_history_loaded (
            date TEXT NOT NULL,
            region_id INTEGER NOT NULL,
            PRIMARY KEY (date, region_id)
        )
    """)


def _history_dates(days, today=None):
    """Dates of the last `days` complete days, oldest first"""
    today = today or date.today()
    return [today - timedelta(days=offset) for offset in range(days, 0, -1)]


def ensure_market_history(region_ids, days=HISTORY_DAYS, log=None):
    """
    Download missing days of market history for the given regions

    Returns:
    int - number of days that are available for all regions (missing files are skipped)
    """
    def _log(message):
        if log:
            log(message)

    settings = _get_settings()
    conn = _get_connection(settings)
    region_ids = sorted(set(region_ids))
    try:
        cursor = conn.cursor()
        _create_tables(cursor)
        conn.commit()

        placeholders = ', '.join(['?'] * len(region_ids))
        cursor.execute(f"""
            SELECT date FROM market_history_loaded
            WHERE region_id IN ({placeholders})
            GROUP BY date HAVING COUNT(*) = ?
        """, (*region_ids, len(region_ids)))
        loaded = {row[0] for row in cursor.fetchall()}

        dates = _history_dates(days)
        missing = [d for d in dates if d.isoformat() not in loaded]
        if missing:
            _log(f"Downloading market history for {len(missing)} day(s) from EVE Ref...")

        available = len(dates) - len(missing)
        wanted = {str(r) for r in region_ids}
        for idx, day in enumerate(missing, 1):
            url = EVEREF_URL.format(year=day.year, day=day.isoformat())
            try:
                response = requests.get(url, timeout=60)
            except requests.exceptions.RequestException as e:
                _log(f"  {day}: download failed ({e})")
                continue
            if response.status_code == 404:
                _log(f"  {day}: not published yet")
                continue
            if response.status_code != 200:
                _log(f"  {day}: HTTP {response.status_code}")
                continue

            rows = [
                (int(r['region_id']), int(r['type_id']), r['date'], int(r['volume']),
                 int(r['order_count']), float(r['average']) if r['average'] else None)
                for r in csv.DictReader(io.StringIO(bz2.decompress(response.content).decode('utf-8')))
                if r['region_id'] in wanted
            ]
            cursor.executemany("""
                INSERT OR REPLACE INTO market_history_daily
                (region_id, type_id, date, volume, order_count, average)
                VALUES (?, ?, ?, ?, ?, ?)
            """, rows)
            cursor.executemany("""
                INSERT OR REPLACE INTO market_history_loaded (date, region_id) VALUES (?, ?)
            """, [(day.isoformat(), r) for r in region_ids])
            conn.commit()
            available += 1
            if idx % 5 == 0 or idx == len(missing):
                _log(f"  Loaded {idx}/{len(missing)} day(s)")

        # Drop days that fell out of the window
        oldest = dates[0].isoformat()
        cursor.execute("DELETE FROM market_history_daily WHERE date < ?", (oldest,))
        cursor.execute("DELETE FROM market_history_loaded WHERE date < ?", (oldest,))
        conn.commit()
        return available

    finally:
        conn.close()


def get_market_stats(region_id, type_ids, days=HISTORY_DAYS):
    """
    Average units traded per calendar day and volume-weighted average price
    over the last `days` days

    Days without trades count as zero, so rarely traded items are not overestimated.

    Returns:
    dict {type_id: {'daily_volume': float, 'avg_price': float}} - types without trades are absent
    """
    settings = _get_settings()
    conn = _get_connection(settings)
    try:
        cursor = conn.cursor()
        _create_tables(cursor)
        oldest = _history_dates(days)[0].isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM market_history_loaded WHERE region_id = ? AND date >= ?
        """, (region_id, oldest))
        loaded_days = cursor.fetchone()[0]
        if loaded_days == 0:
            return {}

        cursor.execute("""
            SELECT type_id, SUM(volume), SUM(volume * average) FROM market_history_daily
            WHERE region_id = ? AND date >= ? AND volume > 0
            GROUP BY type_id
        """, (region_id, oldest))
        type_ids = set(type_ids)
        return {
            type_id: {'daily_volume': total / loaded_days, 'avg_price': turnover / total}
            for type_id, total, turnover in cursor.fetchall()
            if type_id in type_ids and turnover is not None
        }
    finally:
        conn.close()
