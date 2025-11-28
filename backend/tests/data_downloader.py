"""
Historical Data Downloader
==========================
Downloads and stores historical OANDA data for backtesting.
Supports multi-year data by making multiple API requests.

Run: cd backend && python -m tests.data_downloader
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

from app.services.oanda_client import OandaClient
from app.config import Config


class HistoricalDataDownloader:
    """Download and store historical OANDA data."""

    def __init__(self, db_path: str = "historical_data.db"):
        self.db_path = db_path
        self.oanda = OandaClient(
            api_key=Config.OANDA_API_KEY,
            account_id=Config.OANDA_ACCOUNT_ID,
            environment=Config.OANDA_ENVIRONMENT
        )
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                time TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER DEFAULT 0,
                UNIQUE(instrument, timeframe, time)
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_candles_lookup
            ON candles(instrument, timeframe, time)
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                candles_count INTEGER,
                downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        print(f"📁 Database initialized: {self.db_path}")

    def _get_candles_per_day(self, timeframe: str) -> int:
        """Get number of candles per day for a timeframe."""
        mapping = {
            "M1": 1440,
            "M5": 288,
            "M15": 96,
            "M30": 48,
            "H1": 24,
            "H4": 6,
            "D": 1,
            "W": 0.14,  # ~1 per week
            "M": 0.033  # ~1 per month
        }
        return mapping.get(timeframe, 24)

    def download_historical(
        self,
        instrument: str,
        timeframe: str,
        years: int = 5,
        batch_size: int = 5000
    ) -> int:
        """
        Download historical data in batches.

        Args:
            instrument: Currency pair (EUR_USD, GBP_USD, etc.)
            timeframe: Candle granularity (H1, H4, D, etc.)
            years: Number of years to download
            batch_size: Candles per API request (max 5000)

        Returns:
            Total candles downloaded
        """
        print(f"\n{'='*60}")
        print(f"📥 Downloading {years} years of {instrument} {timeframe}")
        print(f"{'='*60}")

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=years * 365)

        candles_per_day = self._get_candles_per_day(timeframe)
        total_days = years * 365
        estimated_candles = int(total_days * candles_per_day)
        num_batches = max(1, (estimated_candles // batch_size) + 1)

        print(f"   Period: {start_date.date()} → {end_date.date()}")
        print(f"   Estimated candles: ~{estimated_candles:,}")
        print(f"   Batches needed: {num_batches}")

        total_downloaded = 0
        current_end = end_date
        batch_num = 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        while current_end > start_date:
            batch_num += 1
            print(f"\n   📦 Batch {batch_num}/{num_batches}...", end=" ")

            try:
                # Fetch candles ending at current_end
                candles = self.oanda.get_candles(
                    instrument=instrument,
                    granularity=timeframe,
                    count=batch_size
                )

                if not candles:
                    print("No data")
                    break

                # Insert into database
                inserted = 0
                for candle in candles:
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO candles
                            (instrument, timeframe, time, open, high, low, close, volume)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            instrument,
                            timeframe,
                            candle['time'],
                            float(candle['open']),
                            float(candle['high']),
                            float(candle['low']),
                            float(candle['close']),
                            candle.get('volume', 0)
                        ))
                        if cursor.rowcount > 0:
                            inserted += 1
                    except Exception as e:
                        pass

                conn.commit()
                total_downloaded += inserted

                # Get earliest candle time for next batch
                earliest_time = candles[0]['time']
                current_end = datetime.fromisoformat(earliest_time.replace('Z', '+00:00')).replace(tzinfo=None)

                print(f"{inserted} new candles (until {earliest_time[:10]})")

                # Rate limiting
                time.sleep(0.5)

                # Check if we've gone back far enough
                if current_end <= start_date:
                    break

                # OANDA only returns recent data with count parameter
                # For historical data, we need to use 'from' parameter
                # Breaking after first batch for now - will enhance
                if batch_num >= 1:
                    print("\n   ⚠️ Note: OANDA API limits historical access with count parameter.")
                    print("   For deeper history, use 'from/to' date parameters.")
                    break

            except Exception as e:
                print(f"Error: {e}")
                break

        # Log download
        cursor.execute('''
            INSERT INTO download_log (instrument, timeframe, start_date, end_date, candles_count)
            VALUES (?, ?, ?, ?, ?)
        ''', (instrument, timeframe, str(start_date.date()), str(end_date.date()), total_downloaded))

        conn.commit()
        conn.close()

        print(f"\n   ✅ Total new candles: {total_downloaded:,}")
        return total_downloaded

    def download_with_dates(
        self,
        instrument: str,
        timeframe: str,
        from_date: str,
        to_date: Optional[str] = None
    ) -> int:
        """
        Download data using specific date range.

        Args:
            instrument: Currency pair
            timeframe: Granularity
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD), defaults to now
        """
        print(f"\n{'='*60}")
        print(f"📥 Downloading {instrument} {timeframe} from {from_date}")
        print(f"{'='*60}")

        # Parse dates
        start = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.strptime(to_date, "%Y-%m-%d") if to_date else datetime.utcnow()

        total_downloaded = 0
        current_start = start
        batch_num = 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        while current_start < end:
            batch_num += 1
            from_str = current_start.strftime("%Y-%m-%dT00:00:00Z")

            print(f"   📦 Batch {batch_num} from {current_start.date()}...", end=" ")

            try:
                candles = self.oanda.get_candles_from_date(
                    instrument=instrument,
                    granularity=timeframe,
                    from_time=from_str,
                    count=5000
                )

                if not candles:
                    print("No more data")
                    break

                # Insert into database
                inserted = 0
                latest_time = None

                for candle in candles:
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO candles
                            (instrument, timeframe, time, open, high, low, close, volume)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            instrument,
                            timeframe,
                            candle['time'],
                            float(candle['open']),
                            float(candle['high']),
                            float(candle['low']),
                            float(candle['close']),
                            candle.get('volume', 0)
                        ))
                        if cursor.rowcount > 0:
                            inserted += 1
                        latest_time = candle['time']
                    except:
                        pass

                conn.commit()
                total_downloaded += inserted

                if latest_time:
                    current_start = datetime.fromisoformat(
                        latest_time.replace('Z', '+00:00')
                    ).replace(tzinfo=None) + timedelta(seconds=1)
                    print(f"{inserted} candles (to {latest_time[:10]})")
                else:
                    break

                # Rate limiting
                time.sleep(0.3)

                # Safety check
                if len(candles) < 100:
                    break

            except Exception as e:
                print(f"Error: {e}")
                break

        conn.commit()
        conn.close()

        print(f"\n   ✅ Total downloaded: {total_downloaded:,}")
        return total_downloaded

    def get_data_summary(self) -> Dict:
        """Get summary of stored data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                instrument,
                timeframe,
                COUNT(*) as count,
                MIN(time) as start,
                MAX(time) as end
            FROM candles
            GROUP BY instrument, timeframe
            ORDER BY instrument, timeframe
        ''')

        results = cursor.fetchall()
        conn.close()

        summary = {}
        for row in results:
            key = f"{row[0]}_{row[1]}"
            summary[key] = {
                "instrument": row[0],
                "timeframe": row[1],
                "count": row[2],
                "start": row[3][:10] if row[3] else None,
                "end": row[4][:10] if row[4] else None
            }

        return summary

    def print_summary(self):
        """Print data summary."""
        summary = self.get_data_summary()

        print(f"\n{'='*70}")
        print("📊 STORED HISTORICAL DATA")
        print(f"{'='*70}")
        print(f"{'Instrument':<12} {'TF':<5} {'Candles':>10} {'From':<12} {'To':<12}")
        print(f"{'-'*70}")

        for key, data in summary.items():
            print(f"{data['instrument']:<12} {data['timeframe']:<5} {data['count']:>10,} {data['start']:<12} {data['end']:<12}")

        if not summary:
            print("   No data stored yet.")

    def load_data(self, instrument: str, timeframe: str) -> List[Dict]:
        """Load stored data for backtesting."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT time, open, high, low, close, volume
            FROM candles
            WHERE instrument = ? AND timeframe = ?
            ORDER BY time ASC
        ''', (instrument, timeframe))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "time": row[0],
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5]
            }
            for row in rows
        ]


def main():
    print("📥 Historical Data Downloader")
    print("=" * 60)

    downloader = HistoricalDataDownloader(
        db_path="tests/historical_data.db"
    )

    # Show current data
    downloader.print_summary()

    # Download 5 years of data for key pairs
    pairs = ["EUR_USD", "USD_JPY", "GBP_USD"]
    timeframes = ["H1", "H4"]

    # Calculate 5 years ago
    five_years_ago = (datetime.utcnow() - timedelta(days=5*365)).strftime("%Y-%m-%d")

    print(f"\n🎯 Downloading data from {five_years_ago} to today...")

    for pair in pairs:
        for tf in timeframes:
            try:
                downloader.download_with_dates(
                    instrument=pair,
                    timeframe=tf,
                    from_date=five_years_ago
                )
            except Exception as e:
                print(f"   ❌ Error downloading {pair} {tf}: {e}")

    # Final summary
    downloader.print_summary()

    print("\n✅ Download complete!")


if __name__ == "__main__":
    main()
