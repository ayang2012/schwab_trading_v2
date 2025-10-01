#!/usr/bin/env python3
"""
Test script for the new get_technicals_for_symbol function.
Demonstrates how to get technical analysis for any stock or option symbol.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from analysis.technicals import get_technicals_for_symbol
import json


def test_stock_technicals():
    """Test getting technicals for a stock symbol."""
    print("=" * 60)
    print("Testing Stock Technical Analysis")
    print("=" * 60)
    
    symbols = ['AAPL', 'MSFT', 'TSLA', 'AAL']
    
    for symbol in symbols:
        print(f"\n📊 Getting technicals for {symbol}...")
        try:
            technicals = get_technicals_for_symbol(symbol)
            
            print(f"Symbol: {technicals.get('symbol', 'N/A')}")
            print(f"Type: {technicals.get('type', 'N/A')}")
            print(f"RSI: {technicals.get('rsi', 'N/A')}")
            print(f"SMA 20: {technicals.get('sma_20', 'N/A')}")
            print(f"SMA 50: {technicals.get('sma_50', 'N/A')}")
            print(f"MACD: {technicals.get('macd', 'N/A')}")
            print(f"Bollinger Bands: {technicals.get('bollinger_bands', 'N/A')}")
            
            if 'signals' in technicals:
                print(f"Signals: {technicals['signals']}")
            
            if 'error' in technicals:
                print(f"⚠️  Error: {technicals['error']}")
                
        except Exception as e:
            print(f"❌ Error testing {symbol}: {e}")
        
        print("-" * 40)


def test_option_technicals():
    """Test getting technicals for option symbols."""
    print("\n" + "=" * 60)
    print("Testing Option Technical Analysis")
    print("=" * 60)
    
    # Sample option symbols (these might not be real/active)
    option_symbols = [
        'AAPL  241220C00150000',  # AAPL Dec 20 2024 $150 Call
        'MSFT  241220P00300000',  # MSFT Dec 20 2024 $300 Put
        'TSLA  241220C00200000'   # TSLA Dec 20 2024 $200 Call
    ]
    
    for symbol in option_symbols:
        print(f"\n📈 Getting technicals for {symbol}...")
        try:
            technicals = get_technicals_for_symbol(symbol)
            
            print(f"Symbol: {technicals.get('symbol', 'N/A')}")
            print(f"Type: {technicals.get('type', 'N/A')}")
            print(f"Underlying: {technicals.get('underlying', 'N/A')}")
            print(f"Strike: {technicals.get('strike', 'N/A')}")
            print(f"Option Type: {technicals.get('option_type', 'N/A')}")
            print(f"Expiry: {technicals.get('expiry', 'N/A')}")
            print(f"Days to Expiration: {technicals.get('days_to_expiration', 'N/A')}")
            print(f"Delta: {technicals.get('delta', 'N/A')}")
            print(f"Gamma: {technicals.get('gamma', 'N/A')}")
            print(f"Theta: {technicals.get('theta', 'N/A')}")
            print(f"Vega: {technicals.get('vega', 'N/A')}")
            print(f"IV: {technicals.get('implied_volatility', 'N/A')}")
            
            if 'error' in technicals:
                print(f"⚠️  Error: {technicals['error']}")
                
        except Exception as e:
            print(f"❌ Error testing {symbol}: {e}")
        
        print("-" * 40)


def interactive_test():
    """Interactive mode - user can enter any symbol."""
    print("\n" + "=" * 60)
    print("Interactive Technical Analysis")
    print("=" * 60)
    print("Enter stock symbols (e.g., AAPL) or option symbols (e.g., AAPL  241220C00150000)")
    print("Type 'quit' to exit")
    
    while True:
        try:
            symbol = input("\nEnter symbol: ").strip()
            
            if symbol.lower() in ['quit', 'exit', 'q']:
                break
                
            if not symbol:
                continue
                
            print(f"\n🔍 Analyzing {symbol}...")
            technicals = get_technicals_for_symbol(symbol)
            
            # Pretty print the results
            print(json.dumps(technicals, indent=2, default=str))
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    """Main test function."""
    print("🚀 Testing Technical Analysis Functions")
    print("This script demonstrates the new get_technicals_for_symbol() function")
    print("which can analyze ANY stock or option symbol.")
    
    # Test stocks
    test_stock_technicals()
    
    # Test options
    test_option_technicals()
    
    # Interactive mode
    print(f"\n{'='*60}")
    response = input("Would you like to try interactive mode? (y/n): ").strip().lower()
    if response in ['y', 'yes']:
        interactive_test()
    
    print("\n✅ Testing complete!")


if __name__ == "__main__":
    main()