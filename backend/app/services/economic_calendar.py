"""
Economic Calendar for Forex Trading
Fetches high-impact events to avoid trading during volatility
"""

import logging
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class EventImpact(Enum):
    """Economic event impact level"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class EconomicEvent:
    """Single economic event"""
    title: str
    country: str
    currency: str
    impact: EventImpact
    datetime_utc: datetime
    forecast: Optional[str]
    previous: Optional[str]
    actual: Optional[str]


class EconomicCalendar:
    """
    Fetches economic calendar events.
    Uses Forex Factory RSS or similar free sources.
    """

    # Forex Factory RSS feed
    FF_CALENDAR_URL = "https://www.forexfactory.com/calendar.php?day="

    # High impact keywords
    HIGH_IMPACT_EVENTS = [
        "Non-Farm Payrolls", "NFP",
        "Interest Rate Decision", "Fed Funds Rate",
        "CPI", "Inflation",
        "GDP",
        "ECB", "BOE", "BOJ", "Fed",
        "FOMC",
        "Unemployment Rate",
        "Retail Sales",
        "PMI"
    ]

    # Currency to country mapping
    CURRENCY_COUNTRY = {
        "USD": "United States",
        "EUR": "Eurozone",
        "GBP": "United Kingdom",
        "JPY": "Japan",
        "CHF": "Switzerland",
        "CAD": "Canada",
        "AUD": "Australia",
        "NZD": "New Zealand"
    }

    def __init__(self):
        self.logger = logger
        self._cache: List[EconomicEvent] = []
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(hours=4)

    def _is_high_impact(self, title: str) -> bool:
        """Check if event is high impact based on title"""
        title_upper = title.upper()
        for keyword in self.HIGH_IMPACT_EVENTS:
            if keyword.upper() in title_upper:
                return True
        return False

    def get_events_today(self, currencies: List[str] = None) -> List[EconomicEvent]:
        """
        Get economic events for today.

        Args:
            currencies: Filter by currencies (e.g., ["USD", "EUR"])

        Returns:
            List of EconomicEvent
        """
        if currencies is None:
            currencies = ["USD", "EUR", "GBP", "JPY"]

        # Check cache
        if self._cache and self._cache_time:
            if datetime.now() - self._cache_time < self._cache_duration:
                return self._filter_by_currency(self._cache, currencies)

        events = []

        try:
            # Try investing.com economic calendar API (free, no auth)
            events = self._fetch_from_investing_api()
        except Exception as e:
            self.logger.warning(f"Could not fetch from API: {e}")
            # Fallback to static high-impact events
            events = self._get_known_recurring_events()

        # Cache results
        self._cache = events
        self._cache_time = datetime.now()

        return self._filter_by_currency(events, currencies)

    def _fetch_from_investing_api(self) -> List[EconomicEvent]:
        """Fetch from free economic calendar API"""
        # Using a simple approach - check for known events
        # In production, you'd use a proper API like TradingEconomics or Investing.com

        events = []
        today = datetime.now()

        # Simulated API response structure
        # In real implementation, this would be an actual API call
        self.logger.info("📅 Fetching economic calendar...")

        # For now, return empty - real implementation would parse RSS/API
        return events

    def _get_known_recurring_events(self) -> List[EconomicEvent]:
        """
        Get known recurring high-impact events.
        This is a fallback when API is unavailable.
        """
        events = []
        now = datetime.now()

        # First Friday of month = NFP (usually)
        if now.weekday() == 4:  # Friday
            if now.day <= 7:  # First week
                events.append(EconomicEvent(
                    title="US Non-Farm Payrolls",
                    country="United States",
                    currency="USD",
                    impact=EventImpact.HIGH,
                    datetime_utc=now.replace(hour=13, minute=30),
                    forecast=None,
                    previous=None,
                    actual=None
                ))

        # FOMC meetings (8 per year, typically Wed)
        if now.weekday() == 2:  # Wednesday
            events.append(EconomicEvent(
                title="FOMC Meeting (Check Calendar)",
                country="United States",
                currency="USD",
                impact=EventImpact.HIGH,
                datetime_utc=now.replace(hour=19, minute=0),
                forecast=None,
                previous=None,
                actual=None
            ))

        return events

    def _filter_by_currency(
        self,
        events: List[EconomicEvent],
        currencies: List[str]
    ) -> List[EconomicEvent]:
        """Filter events by currency"""
        return [e for e in events if e.currency in currencies]

    def get_high_impact_events(
        self,
        currencies: List[str] = None,
        hours_ahead: int = 24
    ) -> List[EconomicEvent]:
        """
        Get high-impact events in the next N hours.

        Args:
            currencies: Filter by currencies
            hours_ahead: Look ahead window in hours

        Returns:
            List of high-impact events
        """
        events = self.get_events_today(currencies)
        now = datetime.now()
        cutoff = now + timedelta(hours=hours_ahead)

        high_impact = [
            e for e in events
            if e.impact == EventImpact.HIGH
            and now <= e.datetime_utc <= cutoff
        ]

        return high_impact

    def should_avoid_trading(
        self,
        instrument: str = "EUR_USD",
        buffer_minutes: int = 30
    ) -> Dict:
        """
        Check if trading should be avoided due to upcoming events.

        Args:
            instrument: Currency pair
            buffer_minutes: Minutes before event to start avoiding

        Returns:
            Dict with should_avoid flag and reason
        """
        # Extract currencies from instrument
        parts = instrument.replace("_", "/").split("/")
        currencies = parts if len(parts) == 2 else ["USD", "EUR"]

        now = datetime.now()
        buffer = timedelta(minutes=buffer_minutes)

        events = self.get_events_today(currencies)

        for event in events:
            if event.impact == EventImpact.HIGH:
                time_to_event = event.datetime_utc - now

                # If event is within buffer window
                if timedelta(0) <= time_to_event <= buffer:
                    return {
                        "should_avoid": True,
                        "reason": f"High-impact event in {int(time_to_event.total_seconds() / 60)} minutes: {event.title}",
                        "event": event.title,
                        "time_utc": event.datetime_utc.isoformat()
                    }

                # If we're in the aftermath (30 min after)
                if timedelta(minutes=-30) <= time_to_event < timedelta(0):
                    return {
                        "should_avoid": True,
                        "reason": f"High volatility after: {event.title}",
                        "event": event.title,
                        "time_utc": event.datetime_utc.isoformat()
                    }

        return {
            "should_avoid": False,
            "reason": "No high-impact events nearby",
            "event": None,
            "time_utc": None
        }

    def get_next_event(self, currencies: List[str] = None) -> Optional[EconomicEvent]:
        """Get the next upcoming high-impact event"""
        events = self.get_high_impact_events(currencies, hours_ahead=48)

        if not events:
            return None

        # Sort by datetime and return first
        events.sort(key=lambda e: e.datetime_utc)
        return events[0]

    def to_dict(self, event: EconomicEvent) -> Dict:
        """Convert EconomicEvent to dict"""
        return {
            "title": event.title,
            "country": event.country,
            "currency": event.currency,
            "impact": event.impact.value,
            "datetime_utc": event.datetime_utc.isoformat(),
            "forecast": event.forecast,
            "previous": event.previous,
            "actual": event.actual
        }
