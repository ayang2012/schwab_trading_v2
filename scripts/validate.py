#!/usr/bin/env python3
"""Quick validation script for key trading metrics."""

import sys
from pathlib import Path
from decimal import Decimal

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.client import RealBrokerClient
from utils.config_schwab import SchwabConfig
from core.orchestrator import run_once


def quick_validation():
    """Run a quick validation of key metrics."""
    print("🔍 Running quick validation...")
    
    # Initialize client
    config = SchwabConfig.from_env()
    config.app_key = "ER0kVS2P0U9WMMlRRt7Mw4ELCmVRwTB5"
    config.app_secret = "3mJejG1MBpISgcjj"
    
    client = RealBrokerClient(
        app_key=config.app_key,
        app_secret=config.app_secret,
        redirect_uri=config.redirect_uri,
        token_path=config.token_path
    )
    
    # Get current data
    result = run_once(client, include_technicals=True)
    snapshot = result['snapshot']
    technicals_data = result['data'].get('technicals', {})
    
    print(f"✅ Successfully retrieved data at {snapshot.generated_at}")
    print(f"   Total Account Value: ${result['total_account_value']:,.2f}")
    print(f"   Positions: {len(snapshot.stocks)} stocks, {len(snapshot.options)} options")
    
    # Check P&L bounds for short options
    violations = []
    for option in snapshot.options:
        if option.qty < 0:  # Short position
            premium_received = float(option.avg_cost)
            current_cost = float(option.market_price)
            
            if premium_received > 0:
                current_pnl_pct = ((premium_received - current_cost) / premium_received) * 100
                
                if current_pnl_pct > 100:
                    violations.append(f"{option.contract_symbol}: {current_pnl_pct:.1f}% P&L")
                    
                # Also check technical analysis P&L
                if option.contract_symbol in technicals_data.get('options', {}):
                    tech_data = technicals_data['options'][option.contract_symbol]
                    tech_pnl_pct = tech_data.get('position_data', {}).get('pnl_pct', 0)
                    
                    if tech_pnl_pct > 100:
                        violations.append(f"{option.contract_symbol} (tech): {tech_pnl_pct:.1f}% P&L")
    
    if violations:
        print("❌ P&L VIOLATIONS FOUND:")
        for violation in violations:
            print(f"   {violation}")
        return False
    else:
        print("✅ All short option P&L values within bounds (≤100%)")
    
    # Check technical indicators
    unreasonable_indicators = []
    for symbol, data in technicals_data.get('stocks', {}).items():
        if 'technical_indicators' in data:
            indicators = data['technical_indicators']
            
            # Check RSI bounds
            rsi = indicators.get('rsi', 50)
            if not (0 <= rsi <= 100):
                unreasonable_indicators.append(f"{symbol} RSI: {rsi}")
            
            # Check that MAs are positive
            for ma_type in ['sma_5', 'sma_10', 'sma_20', 'ema_10', 'ema_20', 'ema_50']:
                ma_value = indicators.get(ma_type, 0)
                if ma_value <= 0:
                    unreasonable_indicators.append(f"{symbol} {ma_type}: {ma_value}")
    
    if unreasonable_indicators:
        print("❌ UNREASONABLE INDICATORS FOUND:")
        for indicator in unreasonable_indicators:
            print(f"   {indicator}")
        return False
    else:
        print("✅ All technical indicators within reasonable ranges")
    
    # Check account value reasonableness
    total_value = result['total_account_value']
    if not (1000 < total_value < 10_000_000):
        print(f"❌ Account value seems unreasonable: ${total_value:,.2f}")
        return False
    else:
        print(f"✅ Account value reasonable: ${total_value:,.2f}")
    
    # Verify cash secured put collateral calculation
    expected_collateral = Decimal("0.00")
    for option in snapshot.options:
        if option.put_call.upper() == 'PUT' and option.qty < 0:
            collateral = abs(option.qty) * option.strike * 100
            expected_collateral += collateral
    
    print(f"✅ Cash secured put collateral: ${expected_collateral:,.2f}")
    
    print("🎉 All validations passed!")
    return True


if __name__ == "__main__":
    success = quick_validation()
    sys.exit(0 if success else 1)