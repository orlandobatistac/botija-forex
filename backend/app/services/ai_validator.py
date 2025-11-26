"""
OpenAI AI signal validation for Forex Trading
"""

from openai import OpenAI
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class AISignalValidator:
    """AI-based signal validation using OpenAI for Forex"""

    def __init__(self, api_key: str):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=api_key)
        self.logger = logger

    def get_signal(
        self,
        instrument: str,
        price: float,
        ema_fast: float,
        ema_slow: float,
        rsi: float,
        spread_pips: float,
        position_units: int,
        balance: float
    ) -> Dict:
        """Get AI signal for Forex trading decision"""
        try:
            # Calculate context
            ema_trend = "ALCISTA" if ema_fast > ema_slow else "BAJISTA"
            ema_gap_pips = abs(ema_fast - ema_slow) * 10000  # Convert to pips for majors
            has_position = position_units != 0
            position_type = "LONG" if position_units > 0 else "SHORT" if position_units < 0 else "FLAT"

            prompt = f"""
Eres un trader experto en Forex. Tu objetivo es generar ganancias consistentes operando {instrument}.

DATOS ACTUALES:
- Par: {instrument}
- Precio: {price:.5f}
- EMA20: {ema_fast:.5f}
- EMA50: {ema_slow:.5f}
- Gap EMA: {ema_gap_pips:.1f} pips
- Tendencia: {ema_trend}
- RSI14: {rsi:.1f}
- Spread: {spread_pips:.1f} pips
- Posición: {position_type} ({abs(position_units)} units)
- Balance: ${balance:,.2f}

ESTRATEGIA FOREX SWING:
Objetivo: Capturar movimientos de 30-100 pips por operación.

SEÑAL BUY (abrir/mantener largo):
- Tendencia ALCISTA (EMA20 > EMA50)
- RSI entre 40-65 (no sobrecomprado)
- Spread razonable (< 3 pips para majors)
- Sin posición corta abierta

SEÑAL SELL (abrir/mantener corto o cerrar largo):
- Tendencia BAJISTA (EMA20 < EMA50)
- RSI entre 35-60 (no sobrevendido)
- Spread razonable
- O cerrar posición larga existente

SEÑAL HOLD:
- Mercado lateral o indeciso
- Spread muy alto
- RSI en extremos sin confirmación

REGLAS:
1. Protección de capital primero
2. No operar contra la tendencia principal
3. Evitar spreads altos (noticias, baja liquidez)
4. Respetar gestión de riesgo

Responde EXACTAMENTE en este formato:
SIGNAL: BUY/SELL/HOLD
CONFIDENCE: [0.0-1.0]
REASON: [Explicación técnica breve]
"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un trader profesional de Forex. Generas señales precisas basadas en análisis técnico."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )

            content = response.choices[0].message.content.strip()

            # Parse response
            signal = 'HOLD'
            confidence = 0.5
            reason = ''

            lines = content.split('\n')
            for line in lines:
                if line.startswith('SIGNAL:'):
                    signal_text = line.replace('SIGNAL:', '').strip().upper()
                    signal = signal_text if signal_text in ['BUY', 'SELL', 'HOLD'] else 'HOLD'
                elif line.startswith('CONFIDENCE:'):
                    try:
                        confidence = float(line.replace('CONFIDENCE:', '').strip())
                        confidence = min(max(confidence, 0.0), 1.0)
                    except ValueError:
                        confidence = 0.5
                elif line.startswith('REASON:'):
                    reason = line.replace('REASON:', '').strip()

            self.logger.info(f"AI Signal: {signal} (confidence: {confidence:.0%})")

            return {
                'signal': signal,
                'confidence': confidence,
                'reason': reason,
                'raw_response': content
            }

        except Exception as e:
            self.logger.error(f"Error getting AI signal: {e}")
            return {
                'signal': 'HOLD',
                'confidence': 0.0,
                'reason': f'Error: {str(e)}',
                'raw_response': ''
            }
