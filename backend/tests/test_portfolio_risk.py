"""Test Portfolio Risk Management"""
import sys
sys.path.insert(0, '..')

from app.services.risk_manager import RiskManager

rm = RiskManager()

# Test 1: Open EUR_USD (1% risk)
print('=== Test 1: Open EUR_USD ===')
result = rm.can_open_position('EUR_USD', 1.0)
print(f"Can open: {result['can_open']} | Available: {result['available_risk']:.1f}%")
rm.register_position('EUR_USD', 10000, 1.0)

# Test 2: Open USD_JPY (1% risk)
print('\n=== Test 2: Open USD_JPY ===')
result = rm.can_open_position('USD_JPY', 1.0)
print(f"Can open: {result['can_open']} | Available: {result['available_risk']:.1f}%")
rm.register_position('USD_JPY', 10000, 1.0)

# Test 3: Try to open GBP_USD (1% risk) - should work
print('\n=== Test 3: Open GBP_USD ===')
result = rm.can_open_position('GBP_USD', 1.0)
print(f"Can open: {result['can_open']} | Available: {result['available_risk']:.1f}%")
rm.register_position('GBP_USD', 10000, 1.0)

# Test 4: Try to open AUD_USD - should FAIL (excluded)
print('\n=== Test 4: Try AUD_USD (excluded) ===')
result = rm.can_open_position('AUD_USD', 1.0)
print(f"Can open: {result['can_open']} | Reason: {result['reason']}")

# Test 5: Try to open another position - should FAIL (3% limit reached)
print('\n=== Test 5: Try extra position (limit reached) ===')
result = rm.can_open_position('NZD_USD', 1.0)
print(f"Can open: {result['can_open']} | Reason: {result['reason']}")

# Test 6: Check breakout allowed
print('\n=== Test 6: Breakout permissions ===')
print(f"EUR_USD breakout allowed: {rm.is_breakout_allowed('EUR_USD')}")
print(f"GBP_USD breakout allowed: {rm.is_breakout_allowed('GBP_USD')}")

# Portfolio status
print('\n=== Portfolio Status ===')
status = rm.get_portfolio_status()
print(f"Aggregate Risk: {status['aggregate_risk_percent']}% / {status['max_aggregate_risk']}%")
print(f"Positions: {list(status['positions'].keys())}")

# Test 7: Close one position and try again
print('\n=== Test 7: Close EUR_USD and retry ===')
rm.close_position('EUR_USD')
result = rm.can_open_position('NZD_USD', 1.0)
print(f"Can open NZD_USD now: {result['can_open']} | Available: {result['available_risk']:.1f}%")
