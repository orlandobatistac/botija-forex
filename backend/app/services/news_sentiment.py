"""
News Sentiment Analyzer for Forex Trading
Fetches and analyzes forex news headlines
"""

import logging
import requests
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """Single news item"""
    title: str
    source: str
    published: datetime
    url: Optional[str]
    sentiment_score: float  # -1.0 to 1.0
    currencies_mentioned: List[str]


class NewsSentimentAnalyzer:
    """
    Fetches forex news and performs basic sentiment analysis.
    Uses keyword-based NLP (no external API needed).
    """

    # RSS Feeds for forex news
    RSS_FEEDS = {
        "forexlive": "https://www.forexlive.com/feed",
        "dailyfx": "https://www.dailyfx.com/feeds/market-news",
        "fxstreet": "https://www.fxstreet.com/rss/news"
    }

    # Bullish keywords and their weights
    BULLISH_WORDS = {
        "rally": 0.8, "surge": 0.9, "jump": 0.7, "gain": 0.6,
        "rise": 0.5, "climb": 0.6, "advance": 0.5, "bullish": 0.9,
        "strong": 0.6, "strength": 0.6, "up": 0.3, "higher": 0.4,
        "positive": 0.5, "growth": 0.6, "improve": 0.5, "recovery": 0.6,
        "beat": 0.7, "exceed": 0.6, "outperform": 0.7, "breakout": 0.8,
        "hawkish": 0.7, "hike": 0.5, "support": 0.4, "buy": 0.6
    }

    # Bearish keywords and their weights
    BEARISH_WORDS = {
        "fall": 0.6, "drop": 0.7, "decline": 0.6, "slide": 0.7,
        "plunge": 0.9, "crash": 0.95, "tumble": 0.8, "bearish": 0.9,
        "weak": 0.6, "weakness": 0.6, "down": 0.3, "lower": 0.4,
        "negative": 0.5, "contraction": 0.6, "slowdown": 0.5, "recession": 0.8,
        "miss": 0.6, "disappoint": 0.6, "underperform": 0.7, "breakdown": 0.8,
        "dovish": 0.6, "cut": 0.5, "risk": 0.4, "sell": 0.6,
        "concern": 0.5, "fear": 0.6, "uncertainty": 0.5, "crisis": 0.9
    }

    # Currency patterns
    CURRENCY_PATTERNS = {
        "USD": r"\b(USD|dollar|greenback|buck|US\s*\$)\b",
        "EUR": r"\b(EUR|euro|single\s+currency)\b",
        "GBP": r"\b(GBP|pound|sterling|cable)\b",
        "JPY": r"\b(JPY|yen)\b",
        "CHF": r"\b(CHF|franc|swiss)\b",
        "CAD": r"\b(CAD|loonie|canadian)\b",
        "AUD": r"\b(AUD|aussie|australian)\b",
        "NZD": r"\b(NZD|kiwi|new\s+zealand)\b"
    }

    def __init__(self):
        self.logger = logger
        self._cache: List[NewsItem] = []
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=30)

    def _analyze_sentiment(self, text: str) -> float:
        """
        Analyze sentiment of text using keyword matching.

        Returns:
            Score from -1.0 (bearish) to 1.0 (bullish)
        """
        text_lower = text.lower()

        bullish_score = 0.0
        bearish_score = 0.0

        # Count bullish keywords
        for word, weight in self.BULLISH_WORDS.items():
            if word in text_lower:
                bullish_score += weight

        # Count bearish keywords
        for word, weight in self.BEARISH_WORDS.items():
            if word in text_lower:
                bearish_score += weight

        # Calculate net sentiment
        total = bullish_score + bearish_score
        if total == 0:
            return 0.0

        # Normalize to -1 to 1
        sentiment = (bullish_score - bearish_score) / total

        return round(max(-1.0, min(1.0, sentiment)), 2)

    def _extract_currencies(self, text: str) -> List[str]:
        """Extract mentioned currencies from text"""
        currencies = []

        for currency, pattern in self.CURRENCY_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                currencies.append(currency)

        return currencies

    def fetch_news(self, max_items: int = 20) -> List[NewsItem]:
        """
        Fetch forex news from RSS feeds.

        Returns:
            List of NewsItem with sentiment analysis
        """
        # Check cache
        if self._cache and self._cache_time:
            if datetime.now() - self._cache_time < self._cache_duration:
                return self._cache[:max_items]

        news_items = []

        for source, feed_url in self.RSS_FEEDS.items():
            try:
                items = self._parse_rss_feed(feed_url, source)
                news_items.extend(items)
            except Exception as e:
                self.logger.warning(f"Could not fetch from {source}: {e}")

        # Sort by date (newest first)
        news_items.sort(key=lambda x: x.published, reverse=True)

        # Cache results
        self._cache = news_items
        self._cache_time = datetime.now()

        self.logger.info(f"📰 Fetched {len(news_items)} news items")

        return news_items[:max_items]

    def _parse_rss_feed(self, url: str, source: str) -> List[NewsItem]:
        """Parse RSS feed and extract news items"""
        items = []

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # Simple RSS parsing (for common RSS/Atom formats)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)

            # Handle different RSS formats
            for item in root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry'):
                title = ""
                pub_date = datetime.now()
                link = ""

                # Get title
                title_elem = item.find('title') or item.find('{http://www.w3.org/2005/Atom}title')
                if title_elem is not None and title_elem.text:
                    title = title_elem.text.strip()

                # Get date
                date_elem = item.find('pubDate') or item.find('{http://www.w3.org/2005/Atom}published')
                if date_elem is not None and date_elem.text:
                    try:
                        # Parse various date formats
                        pub_date = self._parse_date(date_elem.text)
                    except:
                        pub_date = datetime.now()

                # Get link
                link_elem = item.find('link') or item.find('{http://www.w3.org/2005/Atom}link')
                if link_elem is not None:
                    link = link_elem.text or link_elem.get('href', '')

                if title:
                    sentiment = self._analyze_sentiment(title)
                    currencies = self._extract_currencies(title)

                    items.append(NewsItem(
                        title=title,
                        source=source,
                        published=pub_date,
                        url=link,
                        sentiment_score=sentiment,
                        currencies_mentioned=currencies
                    ))

        except Exception as e:
            self.logger.debug(f"RSS parse error for {source}: {e}")

        return items

    def _parse_date(self, date_str: str) -> datetime:
        """Parse various date formats"""
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except:
                continue

        return datetime.now()

    def get_sentiment_for_pair(
        self,
        instrument: str = "EUR_USD",
        hours_back: int = 24
    ) -> Dict:
        """
        Get aggregated sentiment for a currency pair.

        Returns:
            Dict with sentiment score, summary, and relevant headlines
        """
        # Extract currencies from pair
        parts = instrument.replace("_", "/").split("/")
        base_currency = parts[0] if parts else "EUR"
        quote_currency = parts[1] if len(parts) > 1 else "USD"

        # Fetch news
        news = self.fetch_news(50)

        # Filter by time and relevance
        cutoff = datetime.now() - timedelta(hours=hours_back)
        relevant_news = []

        for item in news:
            # Check if news mentions either currency
            if base_currency in item.currencies_mentioned or quote_currency in item.currencies_mentioned:
                if item.published >= cutoff:
                    relevant_news.append(item)

        if not relevant_news:
            return {
                "instrument": instrument,
                "sentiment_score": 0.0,
                "sentiment_label": "NEUTRAL",
                "news_count": 0,
                "summary": "No relevant news found",
                "headlines": []
            }

        # Calculate weighted sentiment (newer = more weight)
        total_score = 0.0
        total_weight = 0.0

        for item in relevant_news:
            # Weight by recency (newer = higher weight)
            hours_old = (datetime.now() - item.published).total_seconds() / 3600
            weight = max(0.1, 1.0 - (hours_old / hours_back))

            total_score += item.sentiment_score * weight
            total_weight += weight

        avg_sentiment = total_score / total_weight if total_weight > 0 else 0.0

        # Determine label
        if avg_sentiment >= 0.3:
            label = "BULLISH"
        elif avg_sentiment <= -0.3:
            label = "BEARISH"
        else:
            label = "NEUTRAL"

        # Generate summary
        summary = self._generate_summary(relevant_news, base_currency, quote_currency)

        # Get top headlines
        top_headlines = [
            {
                "title": n.title,
                "sentiment": n.sentiment_score,
                "source": n.source
            }
            for n in sorted(relevant_news, key=lambda x: abs(x.sentiment_score), reverse=True)[:5]
        ]

        return {
            "instrument": instrument,
            "sentiment_score": round(avg_sentiment, 2),
            "sentiment_label": label,
            "news_count": len(relevant_news),
            "summary": summary,
            "headlines": top_headlines
        }

    def _generate_summary(
        self,
        news: List[NewsItem],
        base: str,
        quote: str
    ) -> str:
        """Generate a brief summary of news sentiment"""
        if not news:
            return "No recent news"

        bullish = sum(1 for n in news if n.sentiment_score > 0.2)
        bearish = sum(1 for n in news if n.sentiment_score < -0.2)
        neutral = len(news) - bullish - bearish

        if bullish > bearish:
            return f"Mostly bullish news for {base}/{quote} ({bullish} positive, {bearish} negative headlines)"
        elif bearish > bullish:
            return f"Mostly bearish news for {base}/{quote} ({bearish} negative, {bullish} positive headlines)"
        else:
            return f"Mixed sentiment for {base}/{quote} ({bullish} positive, {bearish} negative, {neutral} neutral)"

    def to_dict(self, item: NewsItem) -> Dict:
        """Convert NewsItem to dict"""
        return {
            "title": item.title,
            "source": item.source,
            "published": item.published.isoformat(),
            "url": item.url,
            "sentiment_score": item.sentiment_score,
            "currencies_mentioned": item.currencies_mentioned
        }
