"""
OpenAI AI signal validation
"""

from openai import OpenAI
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class AISignalValidator:
    """AI-based signal validation using OpenAI"""
    
    def __init__(self, api_key: str):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=api_key)
        self.logger = logger
    
    def get_signal(
        self,
        price: float,
        ema20: float,
        ema50: float,
        rsi: float,
        btc_balance: float,
        usd_balance: float
    ) -> Dict:
        """Get AI signal for trading decision"""
        try:
            # Calculate additional context
            ema_trend = "ALCISTA" if ema20 > ema50 else "BAJISTA"
            # Avoid division by zero
            ema_gap = abs(ema20 - ema50) / ema50 * 100 if ema50 > 0 else 0
            
            prompt = f"""
Eres un trader experto en Bitcoin swing trading. Tu objetivo es generar ganancias consistentes operando cada 1-24 horas.

DATOS ACTUALES:
- Precio BTC: ${price:,.2f}
- EMA20: ${ema20:,.2f}
- EMA50: ${ema50:,.2f}
- Gap EMA: {ema_gap:.2f}%
- Tendencia: {ema_trend}
- RSI14: {rsi:.2f}
- Balance BTC: {btc_balance:.8f}
- Balance USD: ${usd_balance:,.2f}

ESTRATEGIA SWING TRADING:
Objetivo: Capturar movimientos del 2-8% cada operación, acumulando ganancias mensuales del 15-30%.

SEÑAL BUY (comprar para swing):
- Tendencia ALCISTA (EMA20 > EMA50) con momentum
- RSI entre 40-65 (no sobrecomprado)
- Confirmación de rebote o inicio de tendencia alcista
- Evitar comprar en máximos históricos recientes

SEÑAL SELL (tomar ganancias):
- Indicios de reversión de tendencia
- RSI > 70 (sobrecomprado) o señales de debilidad
- Trailing stop manejará ventas automáticas por caída

SEÑAL HOLD:
- Condiciones no claras o mercado lateral
- Mejor esperar oportunidad con mayor probabilidad

INSTRUCCIONES:
Analiza los datos con criterio de trader profesional. Prioriza:
1. Protección de capital (no entrar en caídas)
2. Timing óptimo (esperar confirmaciones)
3. Gestión de riesgo (solo trades con buena relación riesgo/recompensa)

Responde en formato:
SIGNAL: BUY/SELL/HOLD
CONFIDENCE: [0.0-1.0]
REASON: [Explicación técnica breve del por qué]
"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Mejor análisis que gpt-3.5-turbo
                messages=[
                    {"role": "system", "content": "Eres un trader profesional especializado en Bitcoin swing trading. Generas señales precisas y rentables basadas en análisis técnico."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,  # Balance entre consistencia y adaptabilidad
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
                    signal_text = line.replace('SIGNAL:', '').strip()
                    signal = signal_text if signal_text in ['BUY', 'SELL', 'HOLD'] else 'HOLD'
                elif line.startswith('CONFIDENCE:'):
                    try:
                        confidence = float(line.replace('CONFIDENCE:', '').strip())
                        confidence = min(max(confidence, 0.0), 1.0)
                    except ValueError:
                        confidence = 0.5
                elif line.startswith('REASON:'):
                    reason = line.replace('REASON:', '').strip()
            
            self.logger.info(f"AI Signal: {signal} (confidence: {confidence})")
            
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
