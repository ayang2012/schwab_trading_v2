#!/usr/bin/env python3
"""Test script for option selection strategies."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.client import RealBrokerClient
from strategies.put_selection import find_cash_secured_put_opportunities
from strategies.call_selection import find_covered_call_opportunities
from utils.logging import setup_logging

def main():
    """Test the option selection strategies."""
    setup_logging('INFO')
    
    # Initialize client
    client = RealBrokerClient()
    
    # Get account snapshot
    print("📊 Getting account snapshot...")
    snapshot = client.get_account_snapshot()
    
    print(f"✅ Found {len(snapshot.stocks)} stock positions")
    
    # Test covered call opportunities
    print("\n🔍 Analyzing covered call opportunities...")
    call_opportunities = find_covered_call_opportunities(client, snapshot, min_premium_pct=1.0)
    
    print(f"📈 Found covered call opportunities for {len(call_opportunities)} positions:")
    for symbol, data in call_opportunities.items():
        print(f"\n   🔸 {symbol}: {data['max_contracts']} contracts available")
        print(f"      Current: ${data['position_data']['current_price']:.2f} "
              f"(P&L: {data['position_data']['pnl_pct']:+.1f}%)")
        
        for i, call in enumerate(data['recommended_calls'][:2], 1):
            print(f"      {i}. ${call['strike_price']} strike, "
                  f"{call['days_to_expiry']}d: "
                  f"${call['premium']:.2f} premium "
                  f"({call['annualized_return_pct']:.1f}% annualized) "
                  f"[Score: {call['attractiveness_score']:.0f}]")
    
    # Test cash secured put opportunities
    print("\n🔍 Analyzing cash secured put opportunities...")
    watchlist_symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA']  # Example watchlist
    
    put_opportunities = find_cash_secured_put_opportunities(
        client, watchlist_symbols, snapshot, max_allocation_pct=3.0
    )
    
    print(f"📉 Found cash secured put opportunities for {len(put_opportunities)} symbols:")
    for symbol, data in put_opportunities.items():
        print(f"\n   🔸 {symbol}: ${data['current_price']:.2f} "
              f"(Current allocation: {data['current_allocation_pct']:.1f}%)")
        
        for i, put in enumerate(data['recommended_puts'][:2], 1):
            print(f"      {i}. ${put['strike_price']} strike, "
                  f"{put['days_to_expiry']}d: "
                  f"${put['premium']:.2f} premium "
                  f"({put['annualized_return_pct']:.1f}% annualized, "
                  f"{put['downside_protection_pct']:.1f}% protection) "
                  f"[Score: {put['attractiveness_score']:.0f}]")

if __name__ == "__main__":
    main()