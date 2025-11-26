"""
Test OANDA API Connection
Run: python -m backend.tests.test_oanda_connection
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_oanda_connection():
    """Test OANDA API connection and basic operations"""

    print("=" * 60)
    print("🧪 OANDA API Connection Test")
    print("=" * 60)

    # Get credentials from environment
    api_key = os.getenv('OANDA_API_KEY', '')
    account_id = os.getenv('OANDA_ACCOUNT_ID', '')
    environment = os.getenv('OANDA_ENVIRONMENT', 'demo')

    if not api_key or not account_id:
        print("❌ ERROR: Missing OANDA credentials in .env file")
        print("   Required: OANDA_API_KEY, OANDA_ACCOUNT_ID")
        return False

    print(f"\n📋 Configuration:")
    print(f"   Environment: {environment}")
    print(f"   Account ID: {account_id}")
    print(f"   API Key: {api_key[:10]}...{api_key[-4:]}")

    # Import OANDA client
    from app.services.oanda_client import OandaClient

    client = OandaClient(api_key, account_id, environment)

    # Test 1: Account Summary
    print("\n🔍 Test 1: Account Summary")
    try:
        summary = client.get_account_summary()
        if "error" in summary:
            print(f"   ❌ Error: {summary['error']}")
            return False

        account = summary.get('account', {})
        print(f"   ✅ Balance: ${float(account.get('balance', 0)):,.2f}")
        print(f"   ✅ NAV: ${float(account.get('NAV', 0)):,.2f}")
        print(f"   ✅ Margin Available: ${float(account.get('marginAvailable', 0)):,.2f}")
        print(f"   ✅ Open Trades: {account.get('openTradeCount', 0)}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

    # Test 2: Current Price EUR/USD
    print("\n🔍 Test 2: EUR/USD Pricing")
    try:
        spread = client.get_spread("EUR_USD")
        if not spread:
            print("   ❌ Error: Could not get pricing")
            return False

        print(f"   ✅ Bid: {spread['bid']:.5f}")
        print(f"   ✅ Ask: {spread['ask']:.5f}")
        print(f"   ✅ Spread: {spread['spread_pips']:.1f} pips")
        print(f"   ✅ Mid: {spread['mid']:.5f}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

    # Test 3: OHLC Data
    print("\n🔍 Test 3: OHLC Candles (H4)")
    try:
        candles = client.get_candles("EUR_USD", "H4", count=10)
        if not candles:
            print("   ❌ Error: Could not get candles")
            return False

        print(f"   ✅ Retrieved {len(candles)} candles")
        last_candle = candles[-1]
        print(f"   ✅ Last candle: O={last_candle['open']:.5f} H={last_candle['high']:.5f} L={last_candle['low']:.5f} C={last_candle['close']:.5f}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

    # Test 4: Open Positions
    print("\n🔍 Test 4: Open Positions")
    try:
        positions = client.get_open_positions()
        print(f"   ✅ Open positions: {len(positions)}")

        for pos in positions:
            instrument = pos.get('instrument')
            long_units = pos.get('long', {}).get('units', 0)
            short_units = pos.get('short', {}).get('units', 0)
            print(f"      - {instrument}: Long={long_units}, Short={short_units}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

    # Test 5: Calculate Units
    print("\n🔍 Test 5: Calculate Trade Units")
    try:
        units = client.calculate_units_from_usd(1000, "EUR_USD")
        print(f"   ✅ $1000 USD = {units:,} units EUR_USD")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

    print("\n" + "=" * 60)
    print("✅ All tests passed! OANDA API connection is working.")
    print("=" * 60)

    return True


def test_forex_bot():
    """Test ForexTradingBot initialization"""

    print("\n" + "=" * 60)
    print("🤖 Forex Trading Bot Test")
    print("=" * 60)

    api_key = os.getenv('OANDA_API_KEY', '')
    account_id = os.getenv('OANDA_ACCOUNT_ID', '')
    environment = os.getenv('OANDA_ENVIRONMENT', 'demo')
    openai_key = os.getenv('OPENAI_API_KEY', '')

    from app.services.forex_trading_bot import ForexTradingBot

    print("\n🔧 Initializing ForexTradingBot...")

    bot = ForexTradingBot(
        oanda_api_key=api_key,
        oanda_account_id=account_id,
        oanda_environment=environment,
        openai_api_key=openai_key,
        instrument="EUR_USD",
        trade_amount_percent=10,
        stop_loss_pips=50,
        take_profit_pips=100
    )

    print("   ✅ Bot initialized successfully")

    # Test market analysis
    print("\n📊 Testing market analysis...")
    import asyncio

    async def run_analysis():
        analysis = await bot.analyze_market()
        return analysis

    analysis = asyncio.run(run_analysis())

    if analysis:
        print(f"   ✅ Current Price: {analysis.get('current_price', 0):.5f}")
        print(f"   ✅ Balance: ${analysis.get('balance', 0):,.2f}")
        print(f"   ✅ Position: {analysis.get('position_units', 0)} units")

        tech = analysis.get('tech_signals', {})
        if tech:
            print(f"   ✅ EMA20: {tech.get('ema20', 0):.5f}")
            print(f"   ✅ EMA50: {tech.get('ema50', 0):.5f}")
            print(f"   ✅ RSI: {tech.get('rsi14', 0):.1f}")

        ai = analysis.get('ai_signal', {})
        if ai:
            print(f"   ✅ AI Signal: {ai.get('signal', 'N/A')} ({ai.get('confidence', 0):.0%})")
    else:
        print("   ⚠️ Analysis returned empty (check API credentials)")

    print("\n" + "=" * 60)
    print("✅ Bot test completed!")
    print("=" * 60)


if __name__ == "__main__":
    success = test_oanda_connection()

    if success:
        test_forex_bot()
