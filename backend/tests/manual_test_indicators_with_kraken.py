import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "app"))

from services.kraken_client import KrakenClient  # type: ignore
from services.technical_indicators import TechnicalIndicators  # type: ignore


def main() -> None:
    """Manual test: fetch OHLC from Kraken and compute indicators."""
    api_key = os.getenv("KRAKEN_API_KEY", "")
    api_secret = os.getenv("KRAKEN_API_SECRET", "")

    client = KrakenClient(api_key, api_secret)

    ohlc = client.get_ohlc()
    print("OHLC candles received:", len(ohlc))
    if not ohlc:
        print("No OHLC data returned from Kraken")
        return

    closes = [float(c[4]) for c in ohlc]
    print("Last 5 closes:", closes[-5:])

    signals = TechnicalIndicators.analyze_signals(closes)
    print("Signals:", signals)


if __name__ == "__main__":
    main()
