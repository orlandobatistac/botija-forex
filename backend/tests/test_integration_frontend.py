"""
Integration tests for Frontend + Backend
Tests all frontend functionality including buttons, tables, actions, calculations
"""

import pytest
import requests
import time
from typing import Dict, Any


# Base URL for API
BASE_URL = "http://localhost:8002"


@pytest.fixture
def api_client():
    """Fixture to provide API client"""
    return requests.Session()


@pytest.fixture
def reset_paper_wallet(api_client):
    """Reset paper wallet before each test"""
    response = api_client.post(f"{BASE_URL}/api/v1/paper/reset", params={"initial_usd": 1000.0})
    assert response.status_code == 200
    yield
    # Cleanup after test
    api_client.post(f"{BASE_URL}/api/v1/paper/reset", params={"initial_usd": 1000.0})


class TestHealthEndpoints:
    """Test basic health and status endpoints"""
    
    def test_health_endpoint(self, api_client):
        """Test /health endpoint"""
        response = api_client.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
    
    def test_root_endpoint(self, api_client):
        """Test root endpoint serves frontend"""
        response = api_client.get(f"{BASE_URL}/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Kraken AI Trading Bot" in response.text or "Trading Dashboard" in response.text


class TestBotStatusEndpoints:
    """Test bot status endpoints (Dashboard Status Card)"""
    
    def test_get_bot_status(self, api_client):
        """Test GET /api/v1/bot/status"""
        response = api_client.get(f"{BASE_URL}/api/v1/bot/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "is_running" in data
        assert "trading_mode" in data
        assert "btc_balance" in data
        assert "usd_balance" in data
        assert isinstance(data["is_running"], bool)
    
    def test_start_bot(self, api_client):
        """Test POST /api/v1/bot/start (Start button)"""
        response = api_client.post(f"{BASE_URL}/api/v1/bot/start")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        
        # Verify status changed
        status = api_client.get(f"{BASE_URL}/api/v1/bot/status").json()
        assert status["is_running"] is True
    
    def test_stop_bot(self, api_client):
        """Test POST /api/v1/bot/stop (Stop button)"""
        # First start
        api_client.post(f"{BASE_URL}/api/v1/bot/start")
        
        # Then stop
        response = api_client.post(f"{BASE_URL}/api/v1/bot/stop")
        assert response.status_code == 200
        
        # Verify response indicates stop
        data = response.json()
        assert "message" in data
        assert "stopped" in data["message"].lower() or data.get("status") == "stopped"


class TestPaperTradingEndpoints:
    """Test paper trading endpoints (Paper Trading Card)"""
    
    def test_get_paper_wallet(self, api_client, reset_paper_wallet):
        """Test GET /api/v1/paper/wallet"""
        response = api_client.get(f"{BASE_URL}/api/v1/paper/wallet")
        assert response.status_code == 200
        
        data = response.json()
        assert "usd_balance" in data
        assert "btc_balance" in data
        assert "mode" in data
        assert data["mode"] == "paper"
        assert data["usd_balance"] == 1000.0
    
    def test_reset_paper_wallet_button(self, api_client):
        """Test POST /api/v1/paper/reset (Reset button)"""
        # Make some trades first
        api_client.post(f"{BASE_URL}/api/v1/paper/simulate-buy", 
                       params={"price": 50000.0, "usd_amount": 200.0})
        
        # Reset
        response = api_client.post(f"{BASE_URL}/api/v1/paper/reset", 
                                   params={"initial_usd": 1500.0})
        assert response.status_code == 200
        
        data = response.json()
        assert "wallet" in data
        assert data["wallet"]["usd_balance"] == 1500.0
        assert data["wallet"]["btc_balance"] == 0.0
    
    def test_simulate_buy_action(self, api_client, reset_paper_wallet):
        """Test POST /api/v1/paper/simulate-buy (Manual Buy button)"""
        response = api_client.post(
            f"{BASE_URL}/api/v1/paper/simulate-buy",
            params={"price": 50000.0, "usd_amount": 300.0}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "message" in data
        assert "wallet" in data
        
        # Verify wallet updated
        wallet = data["wallet"]
        assert wallet["usd_balance"] == 700.0  # 1000 - 300
        assert wallet["btc_balance"] > 0
        assert wallet["btc_balance"] == pytest.approx(300.0 / 50000.0, rel=1e-8)
    
    def test_simulate_sell_action(self, api_client, reset_paper_wallet):
        """Test POST /api/v1/paper/simulate-sell (Manual Sell button)"""
        # First buy
        buy_response = api_client.post(
            f"{BASE_URL}/api/v1/paper/simulate-buy",
            params={"price": 50000.0, "usd_amount": 300.0}
        )
        btc_bought = buy_response.json()["wallet"]["btc_balance"]
        
        # Then sell
        response = api_client.post(
            f"{BASE_URL}/api/v1/paper/simulate-sell",
            params={"price": 51000.0, "btc_amount": btc_bought}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        
        # Verify profit
        wallet = data["wallet"]
        assert wallet["btc_balance"] == 0.0
        assert wallet["usd_balance"] > 1000.0  # Made profit
    
    def test_get_paper_stats(self, api_client, reset_paper_wallet):
        """Test GET /api/v1/paper/stats (Statistics display)"""
        # Make some trades
        api_client.post(f"{BASE_URL}/api/v1/paper/simulate-buy",
                       params={"price": 50000.0, "usd_amount": 200.0})
        api_client.post(f"{BASE_URL}/api/v1/paper/simulate-sell",
                       params={"price": 51000.0, "btc_amount": 200.0/50000.0})
        
        response = api_client.get(f"{BASE_URL}/api/v1/paper/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "wallet" in data
        assert "stats" in data
        
        stats = data["stats"]
        assert "total_trades" in stats
        assert "buy_trades" in stats
        assert "sell_trades" in stats
        assert stats["total_trades"] >= 2


class TestTradesEndpoints:
    """Test trades endpoints (Recent Trades table)"""
    
    def test_get_trades_default(self, api_client):
        """Test GET /api/v1/trades (Trades table)"""
        response = api_client.get(f"{BASE_URL}/api/v1/trades")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_trades_with_mode_filter(self, api_client, reset_paper_wallet):
        """Test GET /api/v1/trades?mode=PAPER (Mode filter)"""
        # Create paper trade
        api_client.post(f"{BASE_URL}/api/v1/paper/simulate-buy",
                       params={"price": 50000.0, "usd_amount": 100.0})
        
        response = api_client.get(f"{BASE_URL}/api/v1/trades", params={"mode": "PAPER"})
        assert response.status_code == 200
        
        trades = response.json()
        assert isinstance(trades, list)
        
        if len(trades) > 0:
            # Verify all trades are PAPER mode
            for trade in trades:
                assert trade["trading_mode"] == "PAPER"
    
    def test_get_trades_with_limit(self, api_client):
        """Test GET /api/v1/trades?limit=5 (Pagination)"""
        response = api_client.get(f"{BASE_URL}/api/v1/trades", params={"limit": 5})
        assert response.status_code == 200
        
        trades = response.json()
        assert len(trades) <= 5


class TestIndicatorsEndpoints:
    """Test technical indicators endpoints (Indicators Card)"""
    
    def test_get_current_indicators(self, api_client):
        """Test GET /api/v1/indicators/current"""
        response = api_client.get(f"{BASE_URL}/api/v1/indicators/current")
        assert response.status_code == 200
        
        data = response.json()
        assert "price" in data
        assert "ema_20" in data
        assert "ema_50" in data
        assert "rsi_14" in data
        
        # Validate data types
        assert isinstance(data["price"], (int, float))
        if data["ema_20"] is not None:
            assert isinstance(data["ema_20"], (int, float))


class TestManualCycleEndpoint:
    """Test manual cycle execution (Manual Cycle button)"""
    
    def test_manual_cycle_execution(self, api_client):
        """Test POST /api/v1/bot/cycle"""
        response = api_client.post(f"{BASE_URL}/api/v1/bot/cycle")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "cycle_result" in data or "result" in data


class TestTradingCyclesEndpoints:
    """Test trading cycles endpoints (Trading Cycles table)"""
    
    def test_get_trading_cycles(self, api_client):
        """Test GET /api/v1/cycles"""
        response = api_client.get(f"{BASE_URL}/api/v1/cycles")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)


class TestIntegrationScenarios:
    """End-to-end integration scenarios"""
    
    def test_complete_trading_flow(self, api_client, reset_paper_wallet):
        """Test complete trading flow: status → buy → check trades → sell"""
        # 1. Check initial status
        status = api_client.get(f"{BASE_URL}/api/v1/bot/status").json()
        initial_usd = status["usd_balance"]
        
        # 2. Execute buy
        buy_response = api_client.post(
            f"{BASE_URL}/api/v1/paper/simulate-buy",
            params={"price": 50000.0, "usd_amount": 300.0}
        )
        assert buy_response.json()["success"] is True
        
        # 3. Check trades table updated
        trades = api_client.get(f"{BASE_URL}/api/v1/trades", params={"mode": "PAPER"}).json()
        buy_trades = [t for t in trades if t["order_type"] == "BUY"]
        assert len(buy_trades) > 0
        
        # 4. Check wallet updated
        wallet = api_client.get(f"{BASE_URL}/api/v1/paper/wallet").json()
        assert wallet["usd_balance"] == initial_usd - 300.0
        assert wallet["btc_balance"] > 0
        
        # 5. Execute sell
        sell_response = api_client.post(
            f"{BASE_URL}/api/v1/paper/simulate-sell",
            params={"price": 52000.0, "btc_amount": wallet["btc_balance"]}
        )
        assert sell_response.json()["success"] is True
        
        # 6. Verify profit
        final_wallet = api_client.get(f"{BASE_URL}/api/v1/paper/wallet").json()
        assert final_wallet["usd_balance"] > initial_usd
    
    def test_statistics_calculation(self, api_client, reset_paper_wallet):
        """Test statistics calculations across multiple trades"""
        # Execute multiple trades
        trades_count = 3
        for i in range(trades_count):
            price = 50000.0 + (i * 100)
            api_client.post(
                f"{BASE_URL}/api/v1/paper/simulate-buy",
                params={"price": price, "usd_amount": 100.0}
            )
            time.sleep(0.1)  # Small delay
            api_client.post(
                f"{BASE_URL}/api/v1/paper/simulate-sell",
                params={"price": price + 500, "btc_amount": 100.0 / price}
            )
            time.sleep(0.1)
        
        # Check stats
        stats = api_client.get(f"{BASE_URL}/api/v1/paper/stats").json()
        assert stats["stats"]["total_trades"] >= trades_count * 2
        assert stats["stats"]["buy_trades"] >= trades_count
        assert stats["stats"]["sell_trades"] >= trades_count
    
    def test_error_handling_insufficient_balance(self, api_client, reset_paper_wallet):
        """Test error handling when insufficient balance"""
        response = api_client.post(
            f"{BASE_URL}/api/v1/paper/simulate-buy",
            params={"price": 50000.0, "usd_amount": 5000.0}  # More than available
        )
        
        data = response.json()
        assert data["success"] is False
        assert "Insufficient" in data.get("error", "") or "Insufficient" in data.get("message", "")
    
    def test_precision_calculations(self, api_client, reset_paper_wallet):
        """Test precision in BTC calculations (8 decimals)"""
        # Buy with exact amount
        price = 97234.56
        usd_amount = 92.50 * 0.30  # 30% of $92.50
        
        response = api_client.post(
            f"{BASE_URL}/api/v1/paper/simulate-buy",
            params={"price": price, "usd_amount": usd_amount}
        )
        
        wallet = response.json()["wallet"]
        expected_btc = usd_amount / price
        
        # Verify 8 decimal precision
        assert wallet["btc_balance"] == pytest.approx(expected_btc, rel=1e-8)


class TestUIDataValidation:
    """Test data validation for UI display"""
    
    def test_wallet_data_structure(self, api_client):
        """Verify wallet data structure for UI"""
        response = api_client.get(f"{BASE_URL}/api/v1/paper/wallet")
        data = response.json()
        
        # Required fields for UI
        required_fields = ["mode", "usd_balance", "btc_balance"]
        for field in required_fields:
            assert field in data
        
        # Data types
        assert isinstance(data["usd_balance"], (int, float))
        assert isinstance(data["btc_balance"], (int, float))
        assert data["usd_balance"] >= 0
        assert data["btc_balance"] >= 0
    
    def test_trades_table_data_structure(self, api_client, reset_paper_wallet):
        """Verify trades data structure for table display"""
        # Create a trade
        api_client.post(
            f"{BASE_URL}/api/v1/paper/simulate-buy",
            params={"price": 50000.0, "usd_amount": 100.0}
        )
        
        response = api_client.get(f"{BASE_URL}/api/v1/trades", params={"mode": "PAPER"})
        trades = response.json()
        
        if len(trades) > 0:
            trade = trades[0]
            
            # Required fields for table
            required_fields = [
                "trade_id", "order_type", "symbol", 
                "entry_price", "quantity", "status", 
                "trading_mode", "created_at"
            ]
            for field in required_fields:
                assert field in trade
            
            # Validate data
            assert trade["order_type"] in ["BUY", "SELL"]
            assert trade["trading_mode"] == "PAPER"
            assert isinstance(trade["entry_price"], (int, float))
            assert isinstance(trade["quantity"], (int, float))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
