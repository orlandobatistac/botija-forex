"""
OANDA API client for Forex trading operations
Supports both Demo (fxpractice) and Live (fxtrade) environments
"""

import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OandaClient:
    """OANDA v20 REST API client for Forex trading"""

    # API endpoints
    ENVIRONMENTS = {
        "demo": "https://api-fxpractice.oanda.com",
        "live": "https://api-fxtrade.oanda.com"
    }

    # Granularity mapping (seconds to OANDA format)
    GRANULARITY_MAP = {
        60: "M1",      # 1 minute
        300: "M5",     # 5 minutes
        900: "M15",    # 15 minutes
        1800: "M30",   # 30 minutes
        3600: "H1",    # 1 hour
        14400: "H4",   # 4 hours
        86400: "D",    # 1 day
        604800: "W",   # 1 week
    }

    def __init__(
        self,
        api_key: str,
        account_id: str,
        environment: str = "demo"
    ):
        """
        Initialize OANDA API client

        Args:
            api_key: OANDA API access token
            account_id: OANDA account ID (e.g., '101-001-xxxxx-001')
            environment: 'demo' for practice, 'live' for real trading
        """
        self.api_key = api_key
        self.account_id = account_id
        self.environment = environment.lower()
        self.base_url = self.ENVIRONMENTS.get(self.environment, self.ENVIRONMENTS["demo"])
        self.logger = logger

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept-Datetime-Format": "RFC3339"
        }

        if api_key:
            self.logger.info(f"OANDA client initialized ({environment}) - Account: {account_id}")

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None
    ) -> Dict:
        """Make API request to OANDA"""
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=data,
                timeout=30
            )

            if response.status_code >= 400:
                self.logger.error(f"OANDA API error {response.status_code}: {response.text}")
                return {"error": response.text, "status_code": response.status_code}

            return response.json()

        except requests.exceptions.Timeout:
            self.logger.error("OANDA API timeout")
            return {"error": "Request timeout"}
        except Exception as e:
            self.logger.error(f"OANDA API error: {e}")
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # ACCOUNT METHODS
    # ═══════════════════════════════════════════════════════════════

    def get_account(self) -> Dict:
        """Get account details including balance"""
        return self._request("GET", f"/v3/accounts/{self.account_id}")

    def get_account_summary(self) -> Dict:
        """Get account summary"""
        return self._request("GET", f"/v3/accounts/{self.account_id}/summary")

    def get_balance(self) -> float:
        """Get account balance in base currency (USD)"""
        response = self.get_account_summary()
        if "error" in response:
            return 0.0
        return float(response.get("account", {}).get("balance", 0))

    def get_nav(self) -> float:
        """Get Net Asset Value (balance + unrealized P/L)"""
        response = self.get_account_summary()
        if "error" in response:
            return 0.0
        return float(response.get("account", {}).get("NAV", 0))

    def get_margin_available(self) -> float:
        """Get available margin for trading"""
        response = self.get_account_summary()
        if "error" in response:
            return 0.0
        return float(response.get("account", {}).get("marginAvailable", 0))

    # ═══════════════════════════════════════════════════════════════
    # PRICING METHODS
    # ═══════════════════════════════════════════════════════════════

    def get_pricing(self, instruments: List[str]) -> Dict:
        """
        Get current prices for instruments

        Args:
            instruments: List of instruments (e.g., ['EUR_USD', 'GBP_USD'])
        """
        params = {"instruments": ",".join(instruments)}
        return self._request("GET", f"/v3/accounts/{self.account_id}/pricing", params=params)

    def get_current_price(self, instrument: str = "EUR_USD") -> Optional[float]:
        """Get current mid price for an instrument"""
        response = self.get_pricing([instrument])
        if "error" in response:
            return None

        prices = response.get("prices", [])
        if not prices:
            return None

        # Calculate mid price from bid/ask
        bid = float(prices[0].get("bids", [{}])[0].get("price", 0))
        ask = float(prices[0].get("asks", [{}])[0].get("price", 0))

        return (bid + ask) / 2

    def get_spread(self, instrument: str = "EUR_USD") -> Optional[Dict]:
        """Get bid, ask, and spread for an instrument"""
        response = self.get_pricing([instrument])
        if "error" in response:
            return None

        prices = response.get("prices", [])
        if not prices:
            return None

        bid = float(prices[0].get("bids", [{}])[0].get("price", 0))
        ask = float(prices[0].get("asks", [{}])[0].get("price", 0))
        spread = ask - bid
        spread_pips = spread * 10000  # For EUR/USD (4 decimal places)

        return {
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "spread_pips": spread_pips,
            "mid": (bid + ask) / 2
        }

    # ═══════════════════════════════════════════════════════════════
    # CANDLE/OHLC METHODS
    # ═══════════════════════════════════════════════════════════════

    def get_candles(
        self,
        instrument: str = "EUR_USD",
        granularity: str = "H4",
        count: int = 100,
        price: str = "M"  # M=mid, B=bid, A=ask, BA=bid+ask, MBA=all
    ) -> List[Dict]:
        """
        Get historical candle data

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            granularity: Timeframe (M1, M5, M15, M30, H1, H4, D, W)
            count: Number of candles (max 5000)
            price: Price type (M=mid, B=bid, A=ask)

        Returns:
            List of candle dicts with OHLC data
        """
        params = {
            "granularity": granularity,
            "count": count,
            "price": price
        }

        response = self._request(
            "GET",
            f"/v3/instruments/{instrument}/candles",
            params=params
        )

        if "error" in response:
            return []

        candles = response.get("candles", [])

        # Convert to simple format
        result = []
        for candle in candles:
            if candle.get("complete", False):  # Only completed candles
                mid = candle.get("mid", {})
                result.append({
                    "time": candle.get("time"),
                    "open": float(mid.get("o", 0)),
                    "high": float(mid.get("h", 0)),
                    "low": float(mid.get("l", 0)),
                    "close": float(mid.get("c", 0)),
                    "volume": int(candle.get("volume", 0))
                })

        return result

    def get_ohlc(
        self,
        instrument: str = "EUR_USD",
        interval: int = 14400  # 4 hours in seconds
    ) -> List:
        """
        Get OHLC data compatible with existing indicator calculations

        Args:
            instrument: Currency pair
            interval: Interval in seconds (maps to OANDA granularity)

        Returns:
            List of [time, open, high, low, close, volume] for compatibility
        """
        granularity = self.GRANULARITY_MAP.get(interval, "H4")
        candles = self.get_candles(instrument, granularity, count=100)

        # Return in format compatible with existing code
        return [
            [c["time"], c["open"], c["high"], c["low"], c["close"], c["volume"]]
            for c in candles
        ]

    # ═══════════════════════════════════════════════════════════════
    # POSITION METHODS
    # ═══════════════════════════════════════════════════════════════

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions"""
        response = self._request("GET", f"/v3/accounts/{self.account_id}/openPositions")
        if "error" in response:
            return []
        return response.get("positions", [])

    def get_position(self, instrument: str = "EUR_USD") -> Optional[Dict]:
        """Get position for specific instrument"""
        response = self._request("GET", f"/v3/accounts/{self.account_id}/positions/{instrument}")
        if "error" in response:
            return None
        return response.get("position")

    def get_position_units(self, instrument: str = "EUR_USD") -> int:
        """
        Get current position units (positive = long, negative = short, 0 = no position)
        """
        position = self.get_position(instrument)
        if not position:
            return 0

        long_units = int(position.get("long", {}).get("units", 0))
        short_units = int(position.get("short", {}).get("units", 0))

        return long_units + short_units  # short_units is negative

    # ═══════════════════════════════════════════════════════════════
    # ORDER METHODS
    # ═══════════════════════════════════════════════════════════════

    def place_market_order(
        self,
        instrument: str,
        units: int,
        stop_loss_pips: Optional[float] = None,
        take_profit_pips: Optional[float] = None
    ) -> Dict:
        """
        Place a market order

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            units: Number of units (positive = buy/long, negative = sell/short)
            stop_loss_pips: Optional stop loss in pips
            take_profit_pips: Optional take profit in pips

        Returns:
            Order result dict with success/error
        """
        order_data = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK",  # Fill or Kill
                "positionFill": "DEFAULT"
            }
        }

        # Add stop loss if specified
        if stop_loss_pips:
            current_price = self.get_current_price(instrument)
            if current_price:
                pip_value = 0.0001  # For EUR/USD
                if units > 0:  # Long position
                    stop_loss_price = current_price - (stop_loss_pips * pip_value)
                else:  # Short position
                    stop_loss_price = current_price + (stop_loss_pips * pip_value)

                order_data["order"]["stopLossOnFill"] = {
                    "price": f"{stop_loss_price:.5f}"
                }

        # Add take profit if specified
        if take_profit_pips:
            current_price = self.get_current_price(instrument)
            if current_price:
                pip_value = 0.0001
                if units > 0:  # Long position
                    take_profit_price = current_price + (take_profit_pips * pip_value)
                else:  # Short position
                    take_profit_price = current_price - (take_profit_pips * pip_value)

                order_data["order"]["takeProfitOnFill"] = {
                    "price": f"{take_profit_price:.5f}"
                }

        response = self._request("POST", f"/v3/accounts/{self.account_id}/orders", data=order_data)

        if "error" in response:
            return {"success": False, "error": response.get("error")}

        # Check if order was filled
        if "orderFillTransaction" in response:
            fill = response["orderFillTransaction"]
            return {
                "success": True,
                "order_id": fill.get("id"),
                "instrument": instrument,
                "units": int(fill.get("units", 0)),
                "price": float(fill.get("price", 0)),
                "pl": float(fill.get("pl", 0))
            }
        elif "orderCancelTransaction" in response:
            cancel = response["orderCancelTransaction"]
            return {"success": False, "error": cancel.get("reason", "Order cancelled")}

        return {"success": False, "error": "Unknown response", "raw": response}

    def place_limit_order(
        self,
        instrument: str,
        units: int,
        price: float,
        stop_loss_pips: Optional[float] = None,
        take_profit_pips: Optional[float] = None
    ) -> Dict:
        """Place a limit order at specified price"""
        order_data = {
            "order": {
                "type": "LIMIT",
                "instrument": instrument,
                "units": str(units),
                "price": f"{price:.5f}",
                "timeInForce": "GTC"  # Good Till Cancelled
            }
        }

        response = self._request("POST", f"/v3/accounts/{self.account_id}/orders", data=order_data)

        if "error" in response:
            return {"success": False, "error": response.get("error")}

        if "orderCreateTransaction" in response:
            order = response["orderCreateTransaction"]
            return {
                "success": True,
                "order_id": order.get("id"),
                "instrument": instrument,
                "units": int(order.get("units", 0)),
                "price": float(order.get("price", 0)),
                "status": "pending"
            }

        return {"success": False, "error": "Unknown response"}

    def close_position(self, instrument: str = "EUR_USD", units: str = "ALL") -> Dict:
        """
        Close position for an instrument

        Args:
            instrument: Currency pair
            units: Number of units to close or "ALL"
        """
        position = self.get_position(instrument)
        if not position:
            return {"success": False, "error": "No position to close"}

        long_units = int(position.get("long", {}).get("units", 0))
        short_units = int(position.get("short", {}).get("units", 0))

        close_data = {}

        if long_units > 0:
            close_data["longUnits"] = units if units == "ALL" else str(units)
        elif short_units < 0:
            close_data["shortUnits"] = units if units == "ALL" else str(abs(int(units)))
        else:
            return {"success": False, "error": "No position to close"}

        response = self._request(
            "PUT",
            f"/v3/accounts/{self.account_id}/positions/{instrument}/close",
            data=close_data
        )

        if "error" in response:
            return {"success": False, "error": response.get("error")}

        if "longOrderFillTransaction" in response:
            fill = response["longOrderFillTransaction"]
            return {
                "success": True,
                "order_id": fill.get("id"),
                "units": int(fill.get("units", 0)),
                "price": float(fill.get("price", 0)),
                "pl": float(fill.get("pl", 0))
            }
        elif "shortOrderFillTransaction" in response:
            fill = response["shortOrderFillTransaction"]
            return {
                "success": True,
                "order_id": fill.get("id"),
                "units": int(fill.get("units", 0)),
                "price": float(fill.get("price", 0)),
                "pl": float(fill.get("pl", 0))
            }

        return {"success": False, "error": "Unknown response"}

    # ═══════════════════════════════════════════════════════════════
    # TRADE METHODS
    # ═══════════════════════════════════════════════════════════════

    def get_open_trades(self) -> List[Dict]:
        """Get all open trades"""
        response = self._request("GET", f"/v3/accounts/{self.account_id}/openTrades")
        if "error" in response:
            return []
        return response.get("trades", [])

    def get_closed_trades(self, count: int = 50) -> List[Dict]:
        """
        Get recently closed trades from OANDA

        Args:
            count: Number of trades to fetch (max 500)
        """
        params = {"state": "CLOSED", "count": min(count, 500)}
        response = self._request("GET", f"/v3/accounts/{self.account_id}/trades", params=params)
        if "error" in response:
            return []
        return response.get("trades", [])

    def get_trade(self, trade_id: str) -> Optional[Dict]:
        """Get specific trade details"""
        response = self._request("GET", f"/v3/accounts/{self.account_id}/trades/{trade_id}")
        if "error" in response:
            return None
        return response.get("trade")

    def close_trade(self, trade_id: str, units: str = "ALL") -> Dict:
        """Close a specific trade"""
        close_data = {"units": units}

        response = self._request(
            "PUT",
            f"/v3/accounts/{self.account_id}/trades/{trade_id}/close",
            data=close_data
        )

        if "error" in response:
            return {"success": False, "error": response.get("error")}

        if "orderFillTransaction" in response:
            fill = response["orderFillTransaction"]
            return {
                "success": True,
                "trade_id": trade_id,
                "units": int(fill.get("units", 0)),
                "price": float(fill.get("price", 0)),
                "pl": float(fill.get("pl", 0))
            }

        return {"success": False, "error": "Unknown response"}

    def modify_trade_sl_tp(
        self,
        trade_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop_distance: Optional[float] = None
    ) -> Dict:
        """
        Modify stop loss, take profit, or trailing stop for a trade

        Args:
            trade_id: Trade ID to modify
            stop_loss: New stop loss price
            take_profit: New take profit price
            trailing_stop_distance: Trailing stop distance in price units
        """
        modify_data = {}

        if stop_loss is not None:
            modify_data["stopLoss"] = {"price": f"{stop_loss:.5f}"}

        if take_profit is not None:
            modify_data["takeProfit"] = {"price": f"{take_profit:.5f}"}

        if trailing_stop_distance is not None:
            modify_data["trailingStopLoss"] = {"distance": f"{trailing_stop_distance:.5f}"}

        response = self._request(
            "PUT",
            f"/v3/accounts/{self.account_id}/trades/{trade_id}/orders",
            data=modify_data
        )

        if "error" in response:
            return {"success": False, "error": response.get("error")}

        return {"success": True, "trade_id": trade_id}

    # ═══════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════

    def calculate_units_from_usd(
        self,
        usd_amount: float,
        instrument: str = "EUR_USD"
    ) -> int:
        """
        Calculate units to trade based on USD amount

        For EUR/USD: units = USD amount (approximately)
        """
        current_price = self.get_current_price(instrument)
        if not current_price:
            return 0

        # For EUR/USD, units ≈ USD amount / price
        # e.g., $1000 at 1.05 = ~952 EUR = 952 units
        units = int(usd_amount / current_price)

        return units

    def pips_to_price(self, pips: float, instrument: str = "EUR_USD") -> float:
        """Convert pips to price movement"""
        # Standard forex pairs have 4 decimal places (0.0001 = 1 pip)
        # JPY pairs have 2 decimal places (0.01 = 1 pip)
        if "JPY" in instrument:
            return pips * 0.01
        return pips * 0.0001

    def price_to_pips(self, price_diff: float, instrument: str = "EUR_USD") -> float:
        """Convert price movement to pips"""
        if "JPY" in instrument:
            return price_diff / 0.01
        return price_diff / 0.0001

    def modify_trade_stop_loss(self, trade_id: str, stop_loss: float) -> Dict:
        """Convenience method to modify only stop loss"""
        return self.modify_trade_sl_tp(trade_id, stop_loss=stop_loss)
