"""
Tests for trading calculations (P/L, fees, trailing stop, etc.)
"""

import pytest
from app.services.modes.paper import PaperTradingEngine
from app.database import SessionLocal
from app.models import BotStatus, Trade


@pytest.fixture
def paper_engine():
    """Fixture para crear instancia de PaperTradingEngine"""
    from app.database import engine, Base
    Base.metadata.create_all(bind=engine)
    
    engine = PaperTradingEngine()
    engine.reset_wallet(1000.0)
    return engine


def test_profit_calculation():
    """Test cálculo de profit en operación completa"""
    engine = PaperTradingEngine()
    engine.reset_wallet(1000.0)
    
    # Buy at $50,000
    buy_price = 50000.0
    usd_to_invest = 300.0
    success, msg = engine.buy(buy_price, usd_to_invest)
    assert success
    
    # BTC comprados
    btc_bought = usd_to_invest / buy_price
    
    # Sell at $51,000 (+2%)
    sell_price = 51000.0
    success, msg = engine.sell(sell_price, btc_bought)
    assert success
    
    # Profit esperado: (51000 - 50000) * btc_bought = $6
    expected_profit = (sell_price - buy_price) * btc_bought
    
    # Verificar balance final
    wallet = engine.get_wallet_summary()
    final_usd = wallet['usd_balance']
    
    # Should have: initial (1000) - invested (300) + proceeds (51000 * btc_bought)
    expected_final = 1000.0 - usd_to_invest + (sell_price * btc_bought)
    
    assert final_usd == pytest.approx(expected_final, rel=1e-5)
    assert final_usd > 1000.0  # Made profit


def test_loss_calculation():
    """Test cálculo de pérdida en operación"""
    engine = PaperTradingEngine()
    engine.reset_wallet(1000.0)
    
    # Buy at $50,000
    buy_price = 50000.0
    usd_to_invest = 300.0
    success, msg = engine.buy(buy_price, usd_to_invest)
    assert success
    
    btc_bought = usd_to_invest / buy_price
    
    # Sell at $48,000 (-4%)
    sell_price = 48000.0
    success, msg = engine.sell(sell_price, btc_bought)
    assert success
    
    # Loss esperado: (48000 - 50000) * btc_bought = -$12
    expected_loss = (sell_price - buy_price) * btc_bought
    
    wallet = engine.get_wallet_summary()
    final_usd = wallet['usd_balance']
    
    expected_final = 1000.0 - usd_to_invest + (sell_price * btc_bought)
    
    assert final_usd == pytest.approx(expected_final, rel=1e-5)
    assert final_usd < 1000.0  # Made loss


def test_trailing_stop_calculation():
    """Test cálculo de trailing stop"""
    engine = PaperTradingEngine()
    engine.reset_wallet(1000.0)
    
    # Buy at $50,000
    entry_price = 50000.0
    engine.buy(entry_price, 300.0)
    
    # Initial stop should be at 99% of entry
    wallet = engine.get_wallet_summary()
    expected_initial_stop = entry_price * 0.99
    assert wallet['trailing_stop'] == pytest.approx(expected_initial_stop, rel=1e-5)
    
    # Price goes up to $52,000
    new_price = 52000.0
    result = engine.update_trailing_stop(new_price)
    
    # Stop should move up to 99% of new price
    expected_new_stop = new_price * 0.99
    assert result['trailing_stop'] == pytest.approx(expected_new_stop, rel=1e-5)
    assert result['should_sell'] is False
    
    # Price drops to $51,500 (still above stop of $51,480)
    drop_price = 51500.0
    result = engine.update_trailing_stop(drop_price)
    
    # Stop should NOT move down
    assert result['trailing_stop'] == pytest.approx(expected_new_stop, rel=1e-5)
    assert result['should_sell'] is False
    
    # Price drops below stop
    trigger_price = new_price * 0.98  # Below 99% stop
    result = engine.update_trailing_stop(trigger_price)
    
    assert result['should_sell'] is True


def test_multiple_trades_cumulative():
    """Test cálculos acumulativos de múltiples trades"""
    engine = PaperTradingEngine()
    initial_balance = 1000.0
    engine.reset_wallet(initial_balance)
    
    # Trade 1: Buy $300 at $50k, sell at $51k (+2%)
    engine.buy(50000.0, 300.0)
    btc1 = 300.0 / 50000.0
    engine.sell(51000.0, btc1)
    
    balance_after_trade1 = engine.get_wallet_summary()['usd_balance']
    profit_trade1 = balance_after_trade1 - initial_balance
    
    # Trade 2: Buy $300 at $49k, sell at $50k (+2.04%)
    engine.buy(49000.0, 300.0)
    btc2 = 300.0 / 49000.0
    engine.sell(50000.0, btc2)
    
    balance_after_trade2 = engine.get_wallet_summary()['usd_balance']
    profit_trade2 = balance_after_trade2 - balance_after_trade1
    
    # Verificar que el balance final = inicial + profit1 + profit2
    total_profit = balance_after_trade2 - initial_balance
    assert total_profit == pytest.approx(profit_trade1 + profit_trade2, rel=1e-5)
    assert balance_after_trade2 > initial_balance


def test_percentage_based_trading():
    """Test trading con porcentajes del balance"""
    engine = PaperTradingEngine()
    initial_balance = 1000.0
    engine.reset_wallet(initial_balance)
    
    # Trade with 30% of balance
    percentage = 0.30
    usd_to_invest = initial_balance * percentage
    
    price = 50000.0
    engine.buy(price, usd_to_invest)
    
    wallet = engine.get_wallet_summary()
    
    # Should have 70% of initial balance left
    assert wallet['usd_balance'] == pytest.approx(initial_balance * 0.70, rel=1e-5)
    
    # BTC balance should match investment
    expected_btc = usd_to_invest / price
    assert wallet['btc_balance'] == pytest.approx(expected_btc, rel=1e-5)


def test_full_balance_trade():
    """Test usando todo el balance disponible"""
    engine = PaperTradingEngine()
    initial_balance = 100.0  # Usar balance pequeño para test
    engine.reset_wallet(initial_balance)
    
    price = 50000.0
    
    # Usar todo el balance
    wallet_before = engine.get_wallet_summary()
    engine.buy(price, wallet_before['usd_balance'])
    
    wallet_after = engine.get_wallet_summary()
    
    # USD debe ser 0
    assert wallet_after['usd_balance'] == pytest.approx(0.0, abs=1e-5)
    
    # BTC debe corresponder a todo el balance inicial
    expected_btc = initial_balance / price
    assert wallet_after['btc_balance'] == pytest.approx(expected_btc, rel=1e-5)


def test_insufficient_balance_scenarios():
    """Test escenarios con balance insuficiente"""
    engine = PaperTradingEngine()
    engine.reset_wallet(100.0)
    
    # Intentar comprar más de lo disponible
    success, msg = engine.buy(50000.0, 200.0)
    assert success is False
    assert "Insufficient" in msg
    
    # Balance no debe cambiar
    wallet = engine.get_wallet_summary()
    assert wallet['usd_balance'] == 100.0
    
    # Intentar vender sin BTC
    success, msg = engine.sell(50000.0, 0.001)
    assert success is False
    assert "Insufficient" in msg


def test_precision_edge_cases():
    """Test casos edge de precisión decimal"""
    engine = PaperTradingEngine()
    engine.reset_wallet(92.50)  # Balance actual del bot
    
    # Trade con 30% ($27.75)
    usd_to_invest = 92.50 * 0.30
    price = 97234.56  # Precio real de BTC
    
    success, msg = engine.buy(price, usd_to_invest)
    assert success
    
    wallet = engine.get_wallet_summary()
    
    # Verificar precisión de 8 decimales en BTC (estándar Bitcoin)
    btc_balance = wallet['btc_balance']
    assert btc_balance > 0
    assert btc_balance == pytest.approx(usd_to_invest / price, rel=1e-8)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
