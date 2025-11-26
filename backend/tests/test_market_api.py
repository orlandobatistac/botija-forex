"""
Integration tests for Market API endpoints
Run: python -m pytest backend/tests/test_market_api.py -v
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client"""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def mock_oanda():
    """Mock OANDA client responses"""
    with patch('app.routers.market.get_oanda_client') as mock:
        mock_client = Mock()
        mock_client.get_spread.return_value = {
            "mid": 1.1000,
            "bid": 1.0999,
            "ask": 1.1001,
            "spread_pips": 2.0
        }
        mock_client.get_position_units.return_value = 0
        mock_client.get_candles.return_value = [
            {"close": 1.1 + i * 0.001, "high": 1.101 + i * 0.001, "low": 1.099 + i * 0.001, "time": f"2024-01-{i+1:02d}T00:00:00Z"}
            for i in range(100)
        ]
        mock.return_value = mock_client
        yield mock_client


class TestMarketEndpoints:
    """Tests for /api/v1/market/ endpoints"""

    def test_root_endpoint(self, client):
        """Test root endpoint returns HTML"""
        response = client.get("/")
        # May return HTML or 404 if frontend not available
        assert response.status_code in [200, 404]

    def test_pairs_endpoint_without_oanda(self, client):
        """Test /api/v1/market/pairs without OANDA configured"""
        with patch('app.routers.market.get_multi_pair') as mock:
            mock.return_value = None
            response = client.get("/api/v1/market/pairs")
            assert response.status_code == 503

    def test_pairs_endpoint_with_mock(self, client, mock_oanda):
        """Test /api/v1/market/pairs with mocked OANDA"""
        with patch('app.routers.market.get_multi_pair') as mock_manager:
            mock_mp = Mock()
            mock_mp.get_summary.return_value = {
                "instruments": ["EUR_USD"],
                "total_pairs": 1,
                "active_positions": 0,
                "analyses": []
            }
            mock_manager.return_value = mock_mp

            response = client.get("/api/v1/market/pairs")
            assert response.status_code == 200
            data = response.json()
            assert "instruments" in data

    def test_pair_analysis_endpoint(self, client, mock_oanda):
        """Test /api/v1/market/pairs/{instrument}"""
        with patch('app.routers.market.get_multi_pair') as mock_manager:
            from app.services.multi_pair import PairAnalysis

            mock_mp = Mock()
            mock_mp.analyze_pair.return_value = PairAnalysis(
                instrument="EUR_USD",
                signal="LONG",
                confidence=75,
                mtf_confirmed=True,
                current_price=1.1000,
                spread_pips=2.0,
                position_units=0,
                reason="H1 and H4 aligned"
            )
            mock_manager.return_value = mock_mp

            response = client.get("/api/v1/market/pairs/EUR_USD")
            assert response.status_code == 200
            data = response.json()
            assert data["instrument"] == "EUR_USD"
            assert data["signal"] == "LONG"

    def test_mtf_endpoint(self, client, mock_oanda):
        """Test /api/v1/market/mtf/{instrument}"""
        response = client.get("/api/v1/market/mtf/EUR_USD")
        # Will return 503 if OANDA not configured, or 200 with data
        assert response.status_code in [200, 503]

    def test_opportunity_endpoint(self, client, mock_oanda):
        """Test /api/v1/market/opportunity"""
        with patch('app.routers.market.get_multi_pair') as mock_manager:
            mock_mp = Mock()
            mock_mp.get_best_opportunity.return_value = None
            mock_manager.return_value = mock_mp

            response = client.get("/api/v1/market/opportunity")
            assert response.status_code == 200
            data = response.json()
            assert data["found"] is False

    def test_positions_endpoint(self, client, mock_oanda):
        """Test /api/v1/market/positions"""
        with patch('app.routers.market.get_multi_pair') as mock_manager:
            mock_mp = Mock()
            mock_mp.get_all_positions.return_value = {"EUR_USD": 1000}
            mock_manager.return_value = mock_mp

            response = client.get("/api/v1/market/positions")
            assert response.status_code == 200
            data = response.json()
            assert "EUR_USD" in data

    def test_backtest_endpoint(self, client, mock_oanda):
        """Test /api/v1/market/backtest/{instrument}"""
        response = client.get("/api/v1/market/backtest/EUR_USD?timeframe=H4&candles=100")
        # Will work with mock or return 503
        assert response.status_code in [200, 503]

    def test_backtest_summary_endpoint(self, client, mock_oanda):
        """Test /api/v1/market/backtest-summary"""
        response = client.get("/api/v1/market/backtest-summary?timeframe=H4&candles=100")
        assert response.status_code in [200, 503]


class TestBotEndpoints:
    """Tests for /api/v1/bot/ endpoints"""

    def test_bot_status(self, client):
        """Test /api/v1/bot/status"""
        response = client.get("/api/v1/bot/status")
        assert response.status_code == 200

    def test_bot_dashboard(self, client):
        """Test /api/v1/bot/dashboard"""
        response = client.get("/api/v1/bot/dashboard")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
