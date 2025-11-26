"""
Enhanced AI Signal Validator with Sentiment Analysis
Integrates technical analysis, market sentiment, news, and economic calendar
"""

from openai import OpenAI
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MarketContext:
    """Complete market context for AI analysis"""
    # Technical
    instrument: str
    price: float
    ema_fast: float
    ema_slow: float
    rsi: float
    spread_pips: float
    position_units: int
    balance: float

    # Sentiment
    fear_greed_index: int = 50
    fear_greed_label: str = "Neutral"
    oanda_long_percent: float = 50.0
    oanda_short_percent: float = 50.0

    # News
    news_sentiment: float = 0.0
    news_summary: str = ""

    # Calendar
    has_high_impact_event: bool = False
    next_event: str = ""
    should_avoid_trading: bool = False
    avoid_reason: str = ""


class EnhancedAIValidator:
    """
    Enhanced AI signal validation with sentiment integration.
    Combines technical analysis + market sentiment + news + calendar.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize OpenAI client"""
        self.api_key = api_key
        self.client = None
        self.logger = logger

        if api_key and api_key.strip():
            try:
                self.client = OpenAI(api_key=api_key)
                self.logger.info("✅ Enhanced AI Validator initialized")
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize OpenAI: {e}")
        else:
            self.logger.warning("⚠️ AI Validator: No OPENAI_API_KEY - AI signals disabled")

    @property
    def is_configured(self) -> bool:
        """Check if AI is properly configured"""
        return self.client is not None

    def get_enhanced_signal(self, context: MarketContext) -> Dict:
        """
        Get AI signal with full market context.

        Args:
            context: MarketContext with all data

        Returns:
            Dict with signal, confidence, and detailed reasoning
        """
        # Check if AI is configured
        if not self.is_configured:
            return {
                'signal': 'HOLD',
                'confidence': 0.0,
                'reason': '⚠️ OPENAI_API_KEY not configured',
                'technical_score': 0,
                'sentiment_score': 0,
                'risk_score': 0,
                'ai_enabled': False
            }

        # Check if we should avoid trading (high-impact event)
        if context.should_avoid_trading:
            return {
                'signal': 'HOLD',
                'confidence': 0.9,
                'reason': f'⚠️ Evitar trading: {context.avoid_reason}',
                'technical_score': 0,
                'sentiment_score': 0,
                'risk_score': 100,
                'ai_enabled': True,
                'event_warning': True
            }

        try:
            prompt = self._build_enhanced_prompt(context)

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=300
            )

            content = response.choices[0].message.content.strip()
            return self._parse_enhanced_response(content)

        except Exception as e:
            self.logger.error(f"Error in enhanced AI signal: {e}")
            return {
                'signal': 'HOLD',
                'confidence': 0.0,
                'reason': f'Error: {str(e)}',
                'ai_enabled': True
            }

    def _get_system_prompt(self) -> str:
        """System prompt for enhanced analysis"""
        return """Eres un trader institucional de Forex con 20 años de experiencia.
Tu objetivo es generar señales de alta probabilidad combinando:

1. ANÁLISIS TÉCNICO (40% peso)
   - Tendencia (EMA crossover)
   - Momentum (RSI)
   - Spread y liquidez

2. SENTIMIENTO DE MERCADO (30% peso)
   - Fear & Greed Index (contrarian en extremos)
   - Posicionamiento OANDA (contrarian cuando extremo)
   - Flujo de noticias

3. GESTIÓN DE RIESGO (30% peso)
   - Eventos económicos próximos
   - Volatilidad esperada
   - Tamaño de posición

Generas señales conservadoras. Prefieres HOLD cuando hay duda.
Nunca recomiendas operar antes de eventos de alto impacto."""

    def _build_enhanced_prompt(self, ctx: MarketContext) -> str:
        """Build comprehensive prompt with all context"""

        ema_trend = "ALCISTA" if ctx.ema_fast > ctx.ema_slow else "BAJISTA"
        ema_gap = abs(ctx.ema_fast - ctx.ema_slow) * 10000
        position_type = "LONG" if ctx.position_units > 0 else "SHORT" if ctx.position_units < 0 else "FLAT"

        # Sentiment interpretation
        fng_signal = self._interpret_fear_greed(ctx.fear_greed_index)
        oanda_signal = self._interpret_oanda_sentiment(ctx.oanda_long_percent)

        prompt = f"""
═══════════════════════════════════════════════════════════
ANÁLISIS FOREX: {ctx.instrument}
═══════════════════════════════════════════════════════════

📊 ANÁLISIS TÉCNICO
───────────────────
• Precio actual: {ctx.price:.5f}
• EMA20: {ctx.ema_fast:.5f}
• EMA50: {ctx.ema_slow:.5f}
• Gap EMAs: {ema_gap:.1f} pips
• Tendencia: {ema_trend}
• RSI(14): {ctx.rsi:.1f}
• Spread: {ctx.spread_pips:.1f} pips

📈 SENTIMIENTO DE MERCADO
───────────────────
• Fear & Greed: {ctx.fear_greed_index}/100 ({ctx.fear_greed_label})
  → Señal: {fng_signal}
• OANDA Positions: {ctx.oanda_long_percent:.0f}% Long / {ctx.oanda_short_percent:.0f}% Short
  → Señal contrarian: {oanda_signal}
• News Sentiment: {ctx.news_sentiment:+.2f} (-1 bearish, +1 bullish)
  → {ctx.news_summary if ctx.news_summary else 'Sin datos'}

📅 CALENDARIO ECONÓMICO
───────────────────
• Evento alto impacto próximo: {'⚠️ SÍ' if ctx.has_high_impact_event else '✅ NO'}
• Próximo evento: {ctx.next_event if ctx.next_event else 'Ninguno en 24h'}

💰 POSICIÓN ACTUAL
───────────────────
• Estado: {position_type} ({abs(ctx.position_units)} units)
• Balance: ${ctx.balance:,.2f}

═══════════════════════════════════════════════════════════
DECISIÓN REQUERIDA
═══════════════════════════════════════════════════════════

Basándote en TODO el contexto anterior, proporciona tu análisis:

Responde EXACTAMENTE en este formato:
SIGNAL: BUY/SELL/HOLD
CONFIDENCE: [0.0-1.0]
TECHNICAL_SCORE: [0-100]
SENTIMENT_SCORE: [-100 bearish to +100 bullish]
RISK_LEVEL: LOW/MEDIUM/HIGH
REASON: [Tu análisis detallado en 2-3 oraciones]
ACTION: [Qué hacer específicamente con la posición]
"""
        return prompt

    def _interpret_fear_greed(self, value: int) -> str:
        """Interpret Fear & Greed for trading"""
        if value <= 20:
            return "🟢 Extreme Fear = Contrarian BUY"
        elif value <= 35:
            return "🟡 Fear = Posible BUY"
        elif value <= 65:
            return "⚪ Neutral = Sin sesgo"
        elif value <= 80:
            return "🟡 Greed = Posible SELL"
        else:
            return "🔴 Extreme Greed = Contrarian SELL"

    def _interpret_oanda_sentiment(self, long_percent: float) -> str:
        """Interpret OANDA positioning"""
        if long_percent >= 70:
            return "🔴 Crowd muy LONG = Contrarian SELL"
        elif long_percent >= 60:
            return "🟡 Crowd LONG = Cautela con BUY"
        elif long_percent <= 30:
            return "🟢 Crowd muy SHORT = Contrarian BUY"
        elif long_percent <= 40:
            return "🟡 Crowd SHORT = Cautela con SELL"
        else:
            return "⚪ Crowd balanceado = Sin sesgo"

    def _parse_enhanced_response(self, content: str) -> Dict:
        """Parse AI response with enhanced fields"""
        result = {
            'signal': 'HOLD',
            'confidence': 0.5,
            'technical_score': 50,
            'sentiment_score': 0,
            'risk_level': 'MEDIUM',
            'reason': '',
            'action': '',
            'raw_response': content,
            'ai_enabled': True
        }

        lines = content.split('\n')
        for line in lines:
            line = line.strip()

            if line.startswith('SIGNAL:'):
                sig = line.replace('SIGNAL:', '').strip().upper()
                result['signal'] = sig if sig in ['BUY', 'SELL', 'HOLD'] else 'HOLD'

            elif line.startswith('CONFIDENCE:'):
                try:
                    conf = float(line.replace('CONFIDENCE:', '').strip())
                    result['confidence'] = min(max(conf, 0.0), 1.0)
                except:
                    pass

            elif line.startswith('TECHNICAL_SCORE:'):
                try:
                    score = int(line.replace('TECHNICAL_SCORE:', '').strip())
                    result['technical_score'] = min(max(score, 0), 100)
                except:
                    pass

            elif line.startswith('SENTIMENT_SCORE:'):
                try:
                    score = int(line.replace('SENTIMENT_SCORE:', '').strip())
                    result['sentiment_score'] = min(max(score, -100), 100)
                except:
                    pass

            elif line.startswith('RISK_LEVEL:'):
                risk = line.replace('RISK_LEVEL:', '').strip().upper()
                result['risk_level'] = risk if risk in ['LOW', 'MEDIUM', 'HIGH'] else 'MEDIUM'

            elif line.startswith('REASON:'):
                result['reason'] = line.replace('REASON:', '').strip()

            elif line.startswith('ACTION:'):
                result['action'] = line.replace('ACTION:', '').strip()

        self.logger.info(
            f"🧠 Enhanced AI: {result['signal']} "
            f"(conf: {result['confidence']:.0%}, "
            f"tech: {result['technical_score']}, "
            f"sent: {result['sentiment_score']:+d})"
        )

        return result

    def get_signal(
        self,
        instrument: str,
        price: float,
        ema_fast: float,
        ema_slow: float,
        rsi: float,
        spread_pips: float,
        position_units: int,
        balance: float,
        sentiment_data: Dict = None,
        calendar_data: Dict = None,
        news_data: Dict = None
    ) -> Dict:
        """
        Backward-compatible get_signal with optional sentiment.
        Falls back to basic signal if sentiment not provided.
        """
        # Build context
        context = MarketContext(
            instrument=instrument,
            price=price,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi,
            spread_pips=spread_pips,
            position_units=position_units,
            balance=balance
        )

        # Add sentiment if provided
        if sentiment_data:
            context.fear_greed_index = sentiment_data.get('fear_greed_index', 50)
            context.fear_greed_label = sentiment_data.get('fear_greed_label', 'Neutral')
            context.oanda_long_percent = sentiment_data.get('oanda_long_percent', 50.0)
            context.oanda_short_percent = sentiment_data.get('oanda_short_percent', 50.0)

        # Add news if provided
        if news_data:
            context.news_sentiment = news_data.get('sentiment_score', 0.0)
            context.news_summary = news_data.get('summary', '')

        # Add calendar if provided
        if calendar_data:
            context.has_high_impact_event = calendar_data.get('has_event', False)
            context.next_event = calendar_data.get('next_event', '')
            context.should_avoid_trading = calendar_data.get('should_avoid', False)
            context.avoid_reason = calendar_data.get('avoid_reason', '')

        return self.get_enhanced_signal(context)
